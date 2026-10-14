"""Local MLX reader and prerequisite smoke, with no scoring or gold dependency."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import inspect
import json
import os
from pathlib import Path
import socket
import threading
import time

from .assets import verify_assets, verify_asset_configuration, verify_configured_assets, file_identity
from .environment import discover, resource_gate
from .schemas import GenerationRequest, ReaderResult, validate_record
from .storage import atomic_json, content_hash


@contextmanager
def offline_network():
    """Deny Python socket connection attempts, in addition to Hub offline flags."""
    variables = {'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1'}
    previous = {key: os.environ.get(key) for key in variables}
    os.environ.update(variables)
    attempts = []
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    original_create = socket.create_connection
    def denied(*args, **kwargs):
        attempts.append(str(args[-1]) if args else 'connection')
        raise RuntimeError('offline inference: network connection denied')
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = denied
    try:
        yield attempts
    finally:
        socket.socket.connect, socket.socket.connect_ex = original_connect, original_connect_ex
        socket.create_connection = original_create
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def parse_citation_json(raw: str) -> tuple[str | None, list[tuple[str, int]], str]:
    """Only structural smoke parsing; evidence membership belongs to the QA wrapper."""
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('duplicate JSON key')
            obj[key] = value
        return obj
    def reject(value):
        raise ValueError(f'nonfinite JSON {value}')
    try:
        payload = json.loads(raw, object_pairs_hook=unique, parse_constant=reject)
        if type(payload) is not dict or set(payload) != {'answer', 'citations'}:
            raise ValueError('expected answer and citations only')
        if type(payload['answer']) is not str or type(payload['citations']) is not list:
            raise ValueError('wrong answer/citation types')
        citations = []
        for citation in payload['citations']:
            if (type(citation) is not dict or set(citation) != {'doc_id', 'sentence_index'} or
                    type(citation['doc_id']) is not str or not citation['doc_id'] or
                    type(citation['sentence_index']) is not int or citation['sentence_index'] < 0):
                raise ValueError('invalid citation shape')
            citations.append((citation['doc_id'], citation['sentence_index']))
        return payload['answer'], citations, 'ok' if payload['answer'].strip() else 'abstain'
    except (ValueError, TypeError):
        return None, [], 'parse_error'


class ReaderBackend:
    def __init__(self):
        self.settings = {}
        self.identity = None

    def load(self, snapshot: Path, config: dict) -> None:
        if not isinstance(snapshot, Path) or not snapshot.is_dir():
            raise ValueError('reader requires an existing local snapshot Path')
        identity = config.get('asset')
        if not identity or Path(identity.get('local_path', '')).resolve() != snapshot.resolve():
            raise ValueError('reader requires matching verified local asset identity')
        verify_assets({'required': ['reader'], 'assets': {'reader': identity}})
        from mlx_lm import load
        self.model, self.tokenizer = load(str(snapshot.resolve()), lazy=False,
                                         trust_remote_code=False,
                                         tokenizer_config={'trust_remote_code': False, 'local_files_only': True})
        self.identity = identity
        self.settings = config
        self.synchronize()

    def synchronize(self) -> None:
        import mlx.core as mx
        # Generation uses its own stream; synchronize all outstanding streams.
        mx.synchronize()
        from mlx_lm.generate import generation_stream
        mx.synchronize(generation_stream)

    def generate(self, prompt: str, request: GenerationRequest) -> ReaderResult:
        validate_record(request)
        if not self.identity or (request.model_revision, request.model_hash) != (
                self.identity['revision'], self.identity['snapshot_hash']):
            raise ValueError('generation model identity does not match loaded snapshot')
        if request.cache_mode != 'none':
            raise ValueError('initial native adapter supports only fresh no-reuse generation')
        prompt_ids = self.tokenizer.apply_chat_template(
            [{'role': 'user', 'content': prompt}], tokenize=True, add_generation_prompt=True)
        if len(prompt_ids) + request.max_new_tokens > request.max_context_tokens:
            return ReaderResult('', None, [], 'context_overflow', len(prompt_ids), 0,
                                prompt_ids, [], 'context_overflow')
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        start = time.perf_counter()
        text, token_ids, stop_reason = '', [], None
        def check_timeout(*args):
            if time.perf_counter() - start > request.timeout_seconds:
                raise TimeoutError('generation timeout at synchronized token/prefill boundary')
        iterator = stream_generate(self.model, self.tokenizer, prompt_ids,
                                   max_tokens=request.max_new_tokens, sampler=make_sampler(temp=0),
                                   draft_model=None, max_kv_size=None, kv_bits=None,
                                   prefill_step_size=self.settings.get('prefill_step_size', 512),
                                   prompt_progress_callback=check_timeout)
        try:
            for response in iterator:
                text += response.text
                token_ids.append(int(response.token))
                stop_reason = response.finish_reason
                check_timeout()
            answer, citations, status = parse_citation_json(text)
            if stop_reason != 'stop':
                status = 'budget_exhausted'
        except TimeoutError:
            answer, citations, status, stop_reason = None, [], 'timeout', 'timeout'
        finally:
            iterator.close()
            self.synchronize()
        result = ReaderResult(text, answer, citations, status, len(prompt_ids), len(token_ids),
                              prompt_ids, token_ids, stop_reason)
        validate_record(result)
        return result


def _native_smoke(config: dict, assets: dict, result: dict) -> None:
    output = Path(config['output_dir'])
    # Model-only verification cannot discharge an indispensable corpus prerequisite.
    roles = [role for role in ('reader', 'encoder', 'original_reader') if role in config]
    verify_configured_assets({role: config[role] for role in roles},
                             {'required': roles, 'assets': assets['assets']})
    environment = discover(output)
    result['environment'] = environment
    if not environment['native_supported'] or not environment['resource_gate']['passed']:
        raise ValueError('native resource prerequisite blocked')
    result['lock_identity'] = file_identity(Path('requirements.lock'))
    with offline_network() as attempts:
        import mlx.core as mx
        import psutil
        from mlx_lm import load, stream_generate
        from mlx_lm.sample_utils import make_sampler
        from mlx_lm.models.cache import make_prompt_cache
        from mlx_lm.generate import generate_step
        from .retrieval import EncoderBackend
        from sentence_transformers import SentenceTransformer
        result['api_signatures'] = {func.__name__: str(inspect.signature(func)) for func in
                                   (load, stream_generate, generate_step, make_sampler,
                                    make_prompt_cache, SentenceTransformer, SentenceTransformer.encode)}
        result['synchronization'] = 'mlx.core.synchronize() and synchronize(generation_stream)'
        rss_peak = [psutil.Process().memory_info().rss]
        monitoring = threading.Event()
        def monitor():
            while not monitoring.wait(.02):
                rss_peak[0] = max(rss_peak[0], psutil.Process().memory_info().rss)
        observer = threading.Thread(target=monitor, daemon=True)
        observer.start()
        swap_before = psutil.swap_memory().used
        mx.reset_peak_memory()
        try:
            reader = ReaderBackend()
            before_load = time.perf_counter()
            reader.load(Path(assets['assets']['reader']['local_path']),
                        {**config['reader'], 'asset': assets['assets']['reader']})
            result['reader_cold_load_seconds'] = time.perf_counter() - before_load
            before_load = time.perf_counter()
            encoder = EncoderBackend(Path(assets['assets']['encoder']['local_path']))
            result['encoder_cold_load_seconds'] = time.perf_counter() - before_load
            vectors = encoder.encode(['A blue kite is flying.', 'The kite is blue.'])
            result['encoder'] = {'shape': list(vectors.shape), 'dtype': str(vectors.dtype),
                                 'device': str(encoder.model.device),
                                 'norms': [float(norm) for norm in __import__('numpy').linalg.norm(vectors, axis=1)],
                                 'finite': bool(__import__('numpy').isfinite(vectors).all())}
            prompt = ('Use only the invented evidence below. Return exactly one JSON object with '
                      'keys "answer" and "citations". Each citation must have "doc_id" and '
                      '"sentence_index". No explanation or markdown. Question: What color is '
                      'the kite? Evidence: D0 | Kite\n[0] The kite is blue.')
            asset = assets['assets']['reader']
            request = GenerationRequest(asset['revision'], asset['snapshot_hash'], content_hash(prompt),
                                        content_hash(result['limits']), 'smoke',
                                        config['reader']['max_context_tokens'], config['reader']['max_new_tokens'],
                                        config['reader']['timeout_seconds'], 'none')
            generations = []
            for _ in range(2):
                before = time.perf_counter()
                generated = reader.generate(prompt, request)
                generations.append({'result': asdict(generated), 'elapsed_seconds': time.perf_counter() - before})
            result['generations'] = generations
            result['deterministic_token_parity'] = (generations[0]['result']['generated_token_ids'] ==
                                                     generations[1]['result']['generated_token_ids'])
            valid = all(g['result']['status'] == 'ok' and g['result']['answer'].strip().lower() == 'blue' and
                        g['result']['citations'] == [('D0', 0)] and g['result']['stop_reason'] == 'stop'
                        for g in generations)
            if not valid or not result['deterministic_token_parity']:
                raise ValueError('short citation JSON or deterministic token parity failed')
        finally:
            monitoring.set()
            observer.join()
            rss_peak[0] = max(rss_peak[0], psutil.Process().memory_info().rss)
            result['memory'] = {'rss_bytes': psutil.Process().memory_info().rss,
                                 'sampled_peak_rss_bytes': rss_peak[0], 'peak_mlx_bytes': mx.get_peak_memory(),
                                 'active_mlx_bytes': mx.get_active_memory(), 'swap_before_bytes': swap_before,
                                 'swap_after_bytes': psutil.swap_memory().used}
            result['memory']['swap_growth_bytes'] = result['memory']['swap_after_bytes'] - swap_before
            # RSS and MLX overlap in unified memory. Their sum is a conservative bound,
            # not a claim that these are disjoint allocations.
            result['resource_gate'] = resource_gate(environment['physical_memory_bytes'],
                                                    rss_peak[0] + result['memory']['peak_mlx_bytes'])
            result['resource_gate']['working_set_method'] = 'conservative peak RSS plus peak MLX; overlap possible'
            result['network_attempts'] = attempts
        if attempts or not result['resource_gate']['passed']:
            raise ValueError('offline/network or measured headroom gate failed')
        result['reader_encoder_passed'] = True


def smoke(config: dict, assets: dict) -> dict:
    output = Path(config['output_dir'])
    result = {'measured_utc': datetime.now(timezone.utc).isoformat(), 'wp0_passed': False,
              'status': 'blocked by prerequisites', 'reader_encoder_passed': False,
              'errors': [], 'asset_gate_passed': False, 'network_attempts': [],
              'config_hash': content_hash(config),
              'asset_manifest_hash': assets.get('manifest_hash') or content_hash(assets),
              'source_amendment': config.get('asset_source_amendment'),
              'limits': {key: config['reader'].get(key) for key in
                         ('max_context_tokens', 'max_new_tokens', 'timeout_seconds', 'prefill_step_size')}}
    start = time.perf_counter()
    configuration_passed = False
    try:
        verify_asset_configuration(config, assets)
        configuration_passed = True
        verify_assets(assets)
        result['asset_gate_passed'] = True
    except ValueError as error:
        result['errors'].append(str(error))
    # A failed asset download can still yield a separate native characterization.
    # A configuration/manifest disagreement cannot reach native model loading.
    if configuration_passed:
        try:
            _native_smoke(config, assets, result)
        except Exception as error:
            result['errors'].append(f'{type(error).__name__}: {error}')
    result['elapsed_seconds'] = time.perf_counter() - start
    result['wp0_passed'] = result['reader_encoder_passed'] and result['asset_gate_passed']
    if result['wp0_passed']:
        result['status'] = 'passed'
    result['next_command'] = 'python -m outcome_poc assets --config configs/base.json; python -m outcome_poc smoke --config configs/base.json'
    atomic_json(output / 'wp0.json', result)
    return result


def main(args) -> int:
    config = json.loads(Path(args.config).read_text())
    manifest = json.loads((Path(config['cache_dir']) / 'asset-manifest.json').read_text())
    result = smoke(config, manifest)
    print(json.dumps({key: result[key] for key in ('status', 'wp0_passed', 'reader_encoder_passed', 'errors', 'elapsed_seconds')}, indent=2))
    return 0 if result['wp0_passed'] else 1
