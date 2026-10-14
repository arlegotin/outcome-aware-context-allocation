"""Fit-only analysis of separately scored, closed paired acquisition."""
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import pickle
import time
import sklearn

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge

from .features import build_features, feature_schema
from .policies import training_thresholds
from .schemas import GoldRecord, PairedActionRow, RankedDocument, ScoredTask, validate_record
from .storage import atomic_json, content_hash, read_jsonl

GBM_PARAMS = dict(loss='squared_error', n_estimators=100, learning_rate=.1,
                  max_depth=3, min_samples_leaf=8, subsample=.8, random_state=1729)
RF_PARAMS = dict(n_estimators=300, min_samples_leaf=8, max_features=1., random_state=1729)
RIDGE_ALPHAS = (.1, 1, 10, 100)
FEATURE_NAMES = [f['name'] for f in feature_schema()['features']]


def outcome_targets(rows):
    if not rows or len({r.task_id for r in rows}) != len(rows):
        raise ValueError('nonempty unique fit rows required')
    for row in rows:
        validate_record(row)
        for action in ('small', 'full'):
            status = getattr(row, action+'_status')
            if status == 'infra_error':
                raise ValueError('missing infrastructure blocks training')
            if not getattr(row, action+'_event_ids') or not getattr(row, action+'_prediction_id'):
                raise ValueError('missing acquisition provenance')
            if status != 'ok' and getattr(row, action+'_joint_em'):
                raise ValueError('failed semantic action must have zero success')
    return np.array([r.full_joint_em-r.small_joint_em for r in rows], dtype=np.int64)


def feature_matrix(rows):
    outcome_targets(rows)
    values = []
    for row in rows:
        expected = build_features(row.question, row.ranked_documents)
        if set(row.features) != set(FEATURE_NAMES):
            raise ValueError('bound features schema mismatch')
        actual = np.array([row.features[name] for name in FEATURE_NAMES], dtype=np.float64)
        if not np.array_equal(actual, expected):
            raise ValueError('bound observable features changed')
        values.append(actual)
    return np.array(values, dtype=np.float64)


def proxy_targets(rows, training_gold):
    if set(training_gold) != {r.task_id for r in rows}:
        raise ValueError('gold must contain exactly fit IDs; no tune/protected labels')
    targets = []
    for row in rows:
        gold = training_gold[row.task_id]
        validate_record(gold)
        if gold.task_id != row.task_id: raise ValueError('fit gold identity mismatch')
        selected = {d.title: d.sentence_count for d in row.ranked_documents[:2]}
        targets.append(int(any(doc not in selected or sentence >= selected[doc]
                               for doc, sentence in gold.supporting_facts)))
    return np.array(targets, dtype=np.int64)


class StandardizedRidge:
    """Persist fit-only population statistics along with the ridge estimator."""
    def __init__(self, alpha): self.alpha = alpha
    def fit(self, values, target):
        self.mean_ = values.mean(axis=0)
        self.scale_ = values.std(axis=0, ddof=0)
        self.scale_[self.scale_ == 0] = 1.
        self.n_features_in_ = values.shape[1]
        self.estimator = Ridge(alpha=self.alpha).fit((values-self.mean_)/self.scale_, target)
        return self
    def predict(self, values): return self.estimator.predict((values-self.mean_)/self.scale_)
    def get_params(self): return {**self.estimator.get_params(), 'standardization': 'fit_population_ddof0_zero_to_one'}


def _digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fit_gates(rows: list[PairedActionRow], training_gold: dict[str, GoldRecord], output_dir: Path) -> dict:
    target = outcome_targets(rows)
    proxy = proxy_targets(rows, training_gold)
    matrix = feature_matrix(rows)
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root/'fit-origin.json').exists(): raise ValueError('fit artifacts already exist; immutable local origin')
    start = time.perf_counter()
    shuffled = np.random.default_rng(271828).permutation(target)
    definitions = [('PRE-OUTCOME-GBM', GradientBoostingRegressor(**GBM_PARAMS), matrix, target),
                   ('PRE-RF', RandomForestRegressor(**RF_PARAMS), matrix, target),
                   ('QUERY-ONLY', GradientBoostingRegressor(**GBM_PARAMS), matrix[:, :7], target),
                   ('PROXY-LABEL', GradientBoostingRegressor(**GBM_PARAMS), matrix, proxy),
                   ('SHUFFLED-LABEL-GBM', GradientBoostingRegressor(**GBM_PARAMS), matrix, shuffled)]
    definitions += [(f'PRE-LINEAR-{alpha}', StandardizedRidge(alpha), matrix, target) for alpha in RIDGE_ALPHAS]
    origin = {'kind': 'locally_created_fit_only', 'fit_ids': [r.task_id for r in rows],
              'rows_hash': content_hash([asdict(r) for r in rows]),
              'feature_schema_hash': feature_schema()['hash'], 'models': {}}
    for family, estimator, inputs, labels in definitions:
        trained_start = time.perf_counter()
        estimator.fit(inputs, labels)
        prediction = np.clip(estimator.predict(inputs), 0 if family == 'PROXY-LABEL' else -1, 1)
        artifact = root/(family+'.pkl')
        artifact.write_bytes(pickle.dumps(estimator, protocol=5))
        manifest = {'family': family, 'artifact_file': artifact.name, 'artifact_root': str(root),
                    'artifact_sha256': _digest(artifact), 'artifact_bytes': artifact.stat().st_size,
                    'feature_schema_hash': origin['feature_schema_hash'], 'fit_ids': origin['fit_ids'],
                    'training_rows_hash': origin['rows_hash'], 'parameters': estimator.get_params(),
                    'schema_version': 'local_gate_v1', 'sklearn_version': sklearn.__version__, 'numpy_version': np.__version__,
                    'input_feature_names': FEATURE_NAMES[:7] if family == 'QUERY-ONLY' else FEATURE_NAMES,
                    'target_definition': 'missing_gold_support_from_top_two' if family == 'PROXY-LABEL' else 'full_joint_em-small_joint_em',
                    'clipping': [0 if family == 'PROXY-LABEL' else -1, 1], 'feature_count': inputs.shape[1],
                    'training_predictions': prediction.tolist(), 'thresholds': training_thresholds(prediction),
                    'training_seconds': time.perf_counter()-trained_start, 'origin': origin['kind']}
        if isinstance(estimator, StandardizedRidge):
            manifest['standardization'] = {'mean': estimator.mean_.tolist(), 'scale': estimator.scale_.tolist(), 'ddof': 0}
        origin['models'][family] = manifest
    origin.update(training_seconds=time.perf_counter()-start, shuffled_targets=shuffled.tolist(),
                  target_distribution={str(v): int(np.sum(target == v)) for v in (-1, 0, 1)},
                  proxy_distribution={str(v): int(np.sum(proxy == v)) for v in (0, 1)})
    atomic_json(root/'fit-origin.json', origin)
    return origin


_LOCAL_PICKLE_CLASSES = {
    ('outcome_poc.train', 'StandardizedRidge'),
    ('numpy', 'ndarray'), ('numpy', 'dtype'),
    ('numpy._core.numeric', '_frombuffer'),
    ('numpy._core.multiarray', '_reconstruct'), ('numpy._core.multiarray', 'scalar'),
    ('numpy.random._pickle', '__randomstate_ctor'), ('numpy.random._pickle', '__bit_generator_ctor'),
    ('numpy.random._mt19937', 'MT19937'),
    ('sklearn.ensemble._gb', 'GradientBoostingRegressor'),
    ('sklearn.ensemble._forest', 'RandomForestRegressor'),
    ('sklearn.linear_model._ridge', 'Ridge'), ('sklearn.dummy', 'DummyRegressor'),
    ('sklearn.tree._classes', 'DecisionTreeRegressor'), ('sklearn.tree._tree', 'Tree'),
    ('sklearn._loss.loss', 'HalfSquaredError'), ('sklearn._loss._loss', 'CyHalfSquaredError'),
    ('sklearn._loss.link', 'IdentityLink'), ('sklearn._loss.link', 'Interval'),
}


class _LocalGateUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) not in _LOCAL_PICKLE_CLASSES:
            raise ValueError('external pickle constructor rejected')
        return super().find_class(module, name)


def load_gate(manifest: dict) -> object:
    required = {'artifact_root', 'artifact_file', 'artifact_sha256', 'family', 'origin'}
    if not required <= set(manifest) or manifest['origin'] != 'locally_created_fit_only':
        raise ValueError('gate requires a locally created fit origin')
    root = Path(manifest['artifact_root']).resolve()
    if Path(manifest['artifact_file']).name != manifest['artifact_file']:
        raise ValueError('external artifact path rejected')
    origin = json.loads((root/'fit-origin.json').read_text())
    if origin['kind'] != 'locally_created_fit_only' or origin['models'].get(manifest['family']) != manifest:
        raise ValueError('gate does not match persisted training origin')
    if manifest['feature_schema_hash'] != feature_schema()['hash'] or manifest['fit_ids'] != origin['fit_ids']:
        raise ValueError('gate feature/training origin mismatch')
    artifact = root/manifest['artifact_file']
    if root.is_symlink() or artifact.is_symlink() or _digest(artifact) != manifest['artifact_sha256']:
        raise ValueError('local gate checksum mismatch')
    if manifest['sklearn_version'] != sklearn.__version__ or manifest['numpy_version'] != np.__version__:
        raise ValueError('local estimator dependency identity mismatch')
    model = _LocalGateUnpickler(io.BytesIO(artifact.read_bytes())).load()
    if model.n_features_in_ != manifest['feature_count'] or model.get_params() != manifest['parameters']:
        raise ValueError('local gate resolved parameters/features mismatch')
    return model


def collect_pairs(tasks: list, runtime: object, config: dict) -> list[PairedActionRow]:
    """Merge closed raw acquisition with an independently produced scorer receipt."""
    from .runner import _prediction, validate_closed_accounting, action_signature, job_id
    root = Path(config['run_dir'])
    seal = json.loads((root/'collection.closed.json').read_text())
    for name, digest in seal['hashes'].items():
        if _digest(root/name) != digest: raise ValueError('collection closure digest mismatch')
    predictions = [_prediction(r) for r in read_jsonl(root/'predictions.jsonl')]
    validate_closed_accounting(root, predictions)
    observed = list(read_jsonl(root/'observables.jsonl'))
    bound_config = json.loads((root/'schedule.json').read_text())['runtime_config']
    score_path = Path(config['scores_path'])
    receipt = json.loads(score_path.with_suffix(score_path.suffix+'.closed.json').read_text())
    if (receipt.get('kind') != 'separate_closed_run_scorer' or receipt.get('timing_kind') != 'complete_ledger'
        or receipt.get('scores_sha256') != _digest(score_path)
        or receipt.get('prediction_sha256') != _digest(root/'predictions.jsonl')
        or receipt.get('prediction_closure_sha256') != _digest(root/'predictions.closed.json')):
        raise ValueError('scorer receipt does not match closed acquisition')
    scores = [ScoredTask(**r) for r in read_jsonl(score_path)]
    if receipt['record_count'] != len(predictions) or len(scores) != len(predictions) or len({s.job_id for s in scores}) != len(scores):
        raise ValueError('missing or duplicate separately scored outcomes')
    scored = {s.job_id: s for s in scores}
    by_id = {p.job_id: p for p in predictions}
    assigned = [t.task_id for t in tasks]
    if assigned != seal['assigned_ids'] or len(observed) != 2*len(tasks): raise ValueError('fit assignment mismatch')
    pairs = []
    for task in tasks:
        actions = {o['k']: o for o in observed if o['task_id'] == task.task_id}
        if set(actions) != {2, 10}: raise ValueError('incomplete paired collection')
        small, full = [by_id[actions[k]['job_id']] for k in (2, 10)]
        for k, prediction in ((2, small), (10, full)):
            signature = action_signature(task, bound_config, task.candidate_ids, f'fit:k={k}', 'none')
            if job_id(signature, 'direct:fit-pair', 0) != prediction.job_id:
                raise ValueError('bound task or runtime identity mismatch')
            decision_path = root/'jobs'/prediction.job_id/f'attempt-{prediction.attempt}'/'decision.json'
            decision = json.loads(decision_path.read_text())
            if actions[k]['action_signature'] != decision['action_signature'] or actions[k]['runtime_config_hash'] != content_hash(bound_config):
                raise ValueError('bound task action signature mismatch')
            if prediction.evidence_ids != [r['doc_id'] for r in actions[k]['ranking'][:k]]:
                raise ValueError('bound task evidence/ranking mismatch')
        ss, fs = [scored[p.job_id] for p in (small, full)]
        for prediction, score in ((small, ss), (full, fs)):
            validate_record(score)
            if (score.task_id, score.run_id, score.policy_id, score.repetition_id) != (prediction.task_id, prediction.run_id, prediction.policy_id, prediction.repetition_id):
                raise ValueError('scored source identity mismatch')
        if actions[2]['ranking'] != actions[10]['ranking'] or actions[2]['features'] != actions[10]['features']:
            raise ValueError('paired actions changed observable rankings')
        ranking = [RankedDocument(**r) for r in actions[2]['ranking']]
        pairs.append(PairedActionRow(task.task_id, task.question, ranking, actions[2]['features'],
                    small.job_id, full.job_id, ss.joint_em, fs.joint_em, ss.answer_em, fs.answer_em,
                    small.event_ids, full.event_ids, ss.total_serving_seconds, fs.total_serving_seconds,
                    small.status, full.status))
    feature_matrix(pairs)
    return pairs


def learning_curve(nested_rows: list[list[PairedActionRow]]) -> list[dict]:
    previous, results = [], []
    for rows in nested_rows:
        ids = [r.task_id for r in rows]
        if ids[:len(previous)] != previous or (previous and len(ids) != 2*len(previous)):
            raise ValueError('learning curve requires nested doubling prefixes')
        values, target = feature_matrix(rows), outcome_targets(rows)
        start = time.perf_counter()
        model = GradientBoostingRegressor(**GBM_PARAMS).fit(values, target)
        predictions = np.clip(model.predict(values), -1, 1)
        results.append({'n': len(rows), 'evaluation': 'diagnostic_resubstitution',
                        'mse': float(np.mean((predictions-target)**2)), 'training_seconds': time.perf_counter()-start})
        previous = ids
    return results


def paid_draft_inputs(prediction: dict) -> list[float]:
    """Four observable inputs from a paid fixed-two prediction receipt."""
    valid = prediction['status'] in ('ok', 'abstain')
    count = len({(c['doc_id'], c['sentence_index']) for c in prediction['citations']}) if valid else 0
    return [float(np.log1p(len(prediction['raw_output']))), float(valid),
            float(not (prediction['answer'] or '').strip()), float(count)]


def load_fit_gold(path: Path, fit_ids: list[str]) -> dict[str, GoldRecord]:
    """Require the scorer's explicit fit-only projection, with no extra labels."""
    result = {}
    for item in read_jsonl(Path(path)):
        if item['task_id'] not in fit_ids or item['task_id'] in result:
            raise ValueError('training gold must contain unique fit IDs only')
        item['supporting_facts'] = [tuple(pair) for pair in item['supporting_facts']]
        record = GoldRecord(**item)
        validate_record(record)
        result[record.task_id] = record
    if set(result) != set(fit_ids): raise ValueError('missing fit gold records')
    return result


def validate_estimator_config(settings: dict) -> None:
    expected = {'gbm': GradientBoostingRegressor(**GBM_PARAMS).get_params(),
                'rf': RandomForestRegressor(**RF_PARAMS).get_params(),
                'ridge_alphas':list(RIDGE_ALPHAS), 'ridge_defaults':Ridge(alpha=1).get_params()}
    if settings != expected:
        raise ValueError('resolved estimator defaults differ from prespecified locked config')


def main(args):
    from .collection import load_fit_inputs
    config = json.loads(Path(args.config).read_text())
    start = time.perf_counter()
    validate_estimator_config(config['training']['estimators'])
    tasks, _ = load_fit_inputs(config)
    settings = config['collection']
    rows = collect_pairs(tasks, None, {**settings, 'scores_path': str(Path(settings['run_dir'])/'scores.jsonl')})
    gold = load_fit_gold(Path(config['training']['gold_path']), [t.task_id for t in tasks])
    score_receipt = json.loads((Path(settings['run_dir'])/'scores.jsonl.closed.json').read_text())
    if _digest(Path(config['training']['gold_path'])) != score_receipt['gold_projection_sha256']:
        raise ValueError('fit-only gold projection checksum mismatch')
    fit = fit_gates(rows, gold, Path(config['training']['output_dir']))
    provenance = {'collection_seal_sha256': _digest(Path(settings['run_dir'])/'collection.closed.json'),
                  'scorer_receipt_sha256': _digest(Path(settings['run_dir'])/'scores.jsonl.closed.json'),
                  'training_gold_sha256': score_receipt['gold_projection_sha256'],
                  'frozen_runtime': json.loads((Path(settings['run_dir'])/'schedule.json').read_text())['runtime_config'],
                  'source_code_hashes': {path.name: _digest(path) for path in Path(__file__).parent.glob('*.py')},
                  'resolved_development_config_hash': content_hash(config)}
    fit['acquisition_provenance'] = provenance
    for manifest in fit['models'].values(): manifest['acquisition_provenance_hash'] = content_hash(provenance)
    atomic_json(Path(config['training']['output_dir'])/'fit-origin.json',fit)
    atomic_json(Path(config['training']['output_dir'])/'paired-rows.json', [asdict(r) for r in rows])
    predictions = {r['job_id']: r for r in read_jsonl(Path(settings['run_dir'])/'predictions.jsonl')}
    post = []
    for row in rows:
        p = predictions[row.small_prediction_id]
        post.append({'task_id': row.task_id, 'source_prediction_id': row.small_prediction_id,
                     'source_event_ids': row.small_event_ids, 'base_features': row.features,
                     'draft_features': paid_draft_inputs(p)})
    atomic_json(Path(config['training']['output_dir'])/'paid-draft-features.json', post)
    atomic_json(Path(config['training']['output_dir'])/'paid-draft-schema.json',
                {'base_feature_schema_hash':feature_schema()['hash'], 'feature_count':46,
                 'draft_features':['log1p_raw_draft_characters','draft_contract_valid','empty_answer','unique_valid_citation_sentences'],
                 'source':'existing paid small prediction receipts; no additional generation or judge calls'})
    atomic_json(Path(config['training']['output_dir'])/'acquisition-analysis.json',
                {'analysis_seconds': time.perf_counter()-start, 'training_seconds': fit['training_seconds'],
                 'run_closure_sha256': _digest(Path(settings['run_dir'])/'predictions.closed.json'),
                 'scores_sha256': _digest(Path(settings['run_dir'])/'scores.jsonl'), 'fit_count': len(rows),
                 'extension_decision': 'no extension: initial fit preserved; sparse development outcomes require reserved tune evaluation, no search for favorable labels'})
    print(json.dumps({'fit_count':len(rows), 'models':len(fit['models']), 'target_distribution':fit['target_distribution'], 'training_seconds':fit['training_seconds']}))
    return 0
