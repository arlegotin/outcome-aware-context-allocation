"""Seal the authored, three-call feasibility experiment without task data."""
from dataclasses import asdict
from importlib import metadata
import os
from pathlib import Path
import platform
import shutil
import sys

from ..storage import content_hash
from ..followup.study import read, identity, publish
from ..followup.clock import boot_identity, clock_identity
from ..followup.runtime import sandbox_profile, stage_lock
from ..generation import render_prompt, prompt_identity
from ..schemas import Document
from .profile import load_config
from .assets import verify_manifest

CHECKOUT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parents[1]
ANSWER_SENTENCE = 'The access code for the violet cabinet is LARK-27.'
QUESTION = 'What is the access code for the violet cabinet?'
DENIED_MODULES = ('outcome_poc.data', 'outcome_poc.scoring',
    'outcome_poc.followup.preparation', 'outcome_poc.followup.scoring',
    'outcome_poc.citation_study.preparation', 'outcome_poc.citation_study.scoring',
    'outcome_poc.reader_study.preparation', 'outcome_poc.reader_study.scoring')


def environment_identity():
    return {'python': platform.python_version(), 'executable': str(Path(sys.executable).resolve()),
            'machine': platform.machine(), 'platform': platform.platform(),
            'packages': dict(sorted((d.metadata['Name'], d.version) for d in metadata.distributions()))}


def inventory(directory):
    directory = Path(directory)
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'symlink in sealed inventory: {path}')
        if path.is_file():
            result[str(path.relative_to(directory))] = identity(path)
    return result


def call_schedule(settings):
    decoding_hash = content_hash(settings)
    calls = []
    for shape, repetition in [('short', 1), ('short', 2), ('long', 1)]:
        call = {'shape': shape, 'repetition': repetition, 'role': 'answer',
                'decoding_hash': decoding_hash}
        calls.append({**call, 'call_id': content_hash(call)})
    return calls


def build_prompt(tokenizer, shape):
    if shape not in {'short', 'long'}:
        raise ValueError('unknown authored shape')
    sentences = [ANSWER_SENTENCE]
    for number in range(10000):
        document = Document('authored-reader-probe', 'Authored reader probe',
                            list(sentences), sum(map(len, sentences)))
        prompt = render_prompt(QUESTION, [document], {'D0': document.doc_id}, tokenizer)
        tokens = list(tokenizer.encode(prompt, add_special_tokens=False))
        if shape == 'short' or 7800 <= len(tokens) <= 7936:
            if len(tokens) + 256 > 8192:
                raise ValueError('authored prompt exceeds context allowance')
            return {'prompt': prompt, 'prompt_token_ids': tokens,
                    'prompt_hash': prompt_identity(prompt, tokenizer),
                    'rendered_identity': content_hash({'prompt': prompt, 'tokens': tokens,
                        'template': tokenizer.chat_template, 'enable_thinking': False}),
                    'document': asdict(document), 'aliases': {'D0': document.doc_id}}
        if len(tokens) > 7936:
            raise ValueError('whole-sentence long prompt cannot reach prescribed token range')
        sentences.append(f'Irrelevant note {number + 1:04d}: A paper triangle rests beside a plain wooden box.')
    raise ValueError('long prompt construction did not converge')


def _probes(denied, root):
    probes = []
    for directory in denied:
        path = Path(directory)
        # Inspect names/stat only; never read historical or annotation contents.
        if path.is_file():
            probes.append(str(path))
            continue
        for parent, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not (Path(parent)/d).resolve().is_relative_to(root))
            candidates = sorted(Path(parent)/name for name in files)
            chosen = next((p for p in candidates if p.is_file() and not p.is_symlink()), None)
            if chosen:
                probes.append(str(chosen.resolve()))
                break
    if not probes:
        raise ValueError('no existing files available for real denial probes')
    return probes


def prepare(root: Path, config_path: Path, assets_path: Path) -> dict:
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with stage_lock(root):
        if (root/'plan.json').exists():
            return verify(root)
        config = load_config(config_path)
        assets = read(assets_path)
        verify_manifest(assets, config)
        for entry in assets['assets'].values():
            if Path(entry['local_path']).resolve().is_relative_to(root):
                raise ValueError('model assets must remain outside the run/source snapshot')
        for name, source in [('config.json', config_path), ('assets.json', assets_path),
                             ('requirements.lock', CHECKOUT/'requirements.lock')]:
            target = root/name
            if target.exists() and identity(target) != identity(source):
                raise ValueError(f'existing preparation file differs: {name}')
            if not target.exists():
                shutil.copyfile(source, target)
        snapshot = root/'source/src/outcome_poc'
        if snapshot.exists():
            raise ValueError('partial preparation source already exists; preserve and inspect it')
        shutil.copytree(SOURCE, snapshot, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        denied = [str((CHECKOUT/'data'/name).resolve()) for name in ('raw','prepared','gold','index')]
        denied.append(str((CHECKOUT/'artifacts').resolve()))
        profile = sandbox_profile(root, denied)
        (root/'native.sb').write_text(profile)
        plan = {'version': 1, 'root': str(root), 'calls': call_schedule(config['reader']),
                'freeze': {'boot_id': boot_identity(), 'clock': clock_identity(),
                    'settings': config, 'environment': environment_identity(),
                    'denied_paths': denied, 'denied_probes': _probes(denied, root),
                    'denied_modules': list(DENIED_MODULES)},
                'inputs': {name: identity(root/name) for name in
                    ('config.json','assets.json','requirements.lock','native.sb')},
                'source': inventory(root/'source')}
        plan['plan_hash'] = content_hash(plan)
        publish(root/'plan.json', plan)
        return verify(root)


def verify(root: Path) -> dict:
    root = Path(root).resolve()
    plan = read(root/'plan.json')
    if plan.get('plan_hash') != content_hash({k:v for k,v in plan.items() if k != 'plan_hash'}):
        raise ValueError('plan identity mismatch')
    if plan['root'] != str(root):
        raise ValueError('sealed run moved')
    for name, expected in plan['inputs'].items():
        if (root/name).is_symlink() or identity(root/name) != expected:
            raise ValueError(f'sealed input changed: {name}')
    if inventory(root/'source') != plan['source']:
        raise ValueError('sealed source inventory changed')
    config = load_config(root/'config.json')
    if plan['freeze']['settings'] != config or plan['calls'] != call_schedule(config['reader']):
        raise ValueError('sealed settings or call schedule changed')
    if plan['freeze']['denied_modules'] != list(DENIED_MODULES):
        raise ValueError('sealed import denials changed')
    if (root/'native.sb').read_text() != sandbox_profile(root, plan['freeze']['denied_paths']):
        raise ValueError('native profile differs from required isolation')
    if environment_identity() != plan['freeze']['environment']:
        raise ValueError('sealed environment changed')
    verify_manifest(read(root/'assets.json'), config)
    if (root/'closed.json').exists():
        from .runtime import validate_closed
        validate_closed(root, plan)
    return plan
