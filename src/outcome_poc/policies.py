"""Deterministic pre-answer policies with explicit robustness and caller limits."""

import logging
import math

import numpy as np

from .features import build_features, feature_schema, validate_ranking
from .schemas import Decision, LEARNED_POLICY_FAMILIES, PaidDraft, RankedDocument, validate_record


logger = logging.getLogger(__name__)
_SCHEMA_HASH = feature_schema()['hash']


def _preconditions(paid_draft: PaidDraft | None, caller_cap: int) -> None:
    if paid_draft is not None:
        validate_record(paid_draft)
        raise ValueError('pre-answer policy rejects a paid draft')
    if type(caller_cap) is not int or not 0 <= caller_cap <= 10:
        raise ValueError('caller_cap must be an integer in [0,10]')


def _decision(policy_id: str, requested: int, count: int, caller_cap: int,
              reason: str, prediction: float | None = None,
              mode: str | None = None, threshold: float | None = None) -> Decision:
    effective = min(requested, count)
    if effective == 0 or effective > caller_cap:
        effective, reason = 0, 'budget_exhausted'
    decision = Decision(policy_id, requested, prediction, mode, threshold, reason,
                        _SCHEMA_HASH, requested, effective)
    validate_record(decision)
    return decision


class FixedPolicy:
    def __init__(self, k: int):
        if type(k) is not int or not 1 <= k <= 10:
            raise ValueError('fixed budget must be an integer in [1,10]')
        self.k, self.policy_id = k, f'FIXED-{k}'

    def choose(self, question: str, ranked: list[RankedDocument], paid_draft: PaidDraft | None = None,
               *, caller_cap: int = 10) -> Decision:
        _preconditions(paid_draft, caller_cap)
        if ranked:
            validate_ranking(ranked)
        return _decision(self.policy_id, self.k, len(ranked), caller_cap, 'fixed')


class AdaptiveKPolicy:
    def __init__(self, buffer: int, *, variant: str | None = None):
        if type(buffer) is not int or not 0 <= buffer <= 5:
            raise ValueError('adaptive buffer must be an integer in [0,5]')
        variant = variant or ('published' if buffer == 5 else 'tuned')
        if variant not in {'published', 'tuned'} or (variant == 'published' and buffer != 5):
            raise ValueError('published Adaptive-k uses buffer five')
        self.buffer = buffer
        self.policy_id = f'ADAPTIVE-k-{variant}-B{buffer}'

    def choose(self, question: str, ranked: list[RankedDocument], paid_draft: PaidDraft | None = None,
               *, caller_cap: int = 10) -> Decision:
        _preconditions(paid_draft, caller_cap)
        if not ranked:
            return _decision(self.policy_id, 1, 0, caller_cap, 'budget_exhausted')
        validate_ranking(ranked)
        count = len(ranked)
        searchable = math.ceil(.9*count)
        if searchable < 2:
            requested = 1
        else:
            gaps = [ranked[j].score-ranked[j+1].score for j in range(searchable-1)]
            j = int(np.argmax(gaps))  # NumPy returns the first exact maximum.
            requested = min(count, j+1+self.buffer)
        return _decision(self.policy_id, requested, count, caller_cap, 'largest_gap')


class ThresholdPolicy:
    def __init__(self, model: object, config: dict):
        self.model = model
        self.config = dict(config)
        self.policy_id = self.config.get('policy_id', 'PRE-OUTCOME-GBM')
        if not any(self.policy_id == family or self.policy_id.startswith(family+'-')
                   for family in LEARNED_POLICY_FAMILIES - {'POST-OUTCOME'}):
            raise ValueError('unknown pre-answer learned family')
        self.mode = self.config.get('threshold_mode')
        self.threshold = self.config.get('threshold')
        # Reuse the shared strict finite/null endpoint validation.
        _decision(self.policy_id, 2 if self.mode == 'always_two' else 10, 10, 10,
                  'configuration', mode=self.mode, threshold=self.threshold)

    def choose(self, question: str, ranked: list[RankedDocument], paid_draft: PaidDraft | None = None,
               *, caller_cap: int = 10) -> Decision:
        _preconditions(paid_draft, caller_cap)
        mode, threshold = self.mode, self.threshold
        requested = 2 if mode == 'always_two' else 10
        if not ranked or min(2, len(ranked)) > caller_cap:
            return _decision(self.policy_id, requested, len(ranked), caller_cap,
                             'budget_exhausted', mode=mode, threshold=threshold)
        prediction = None
        try:
            if self.config.get('feature_schema_hash', _SCHEMA_HASH) != _SCHEMA_HASH:
                raise ValueError('feature schema mismatch')
            validate_ranking(ranked)
            if mode == 'numeric':
                values = build_features(question, ranked)
                if values.shape != (42,) or not np.isfinite(values).all():
                    raise ValueError('invalid feature vector')
                query_only = self.policy_id == 'QUERY-ONLY' or self.policy_id.startswith('QUERY-ONLY-')
                values = values[:7] if query_only else values
                if getattr(self.model, 'n_features_in_', len(values)) != len(values):
                    raise ValueError('model feature schema mismatch')
                predicted = np.asarray(self.model.predict(values.reshape(1, -1)), dtype=np.float64)
                if predicted.shape != (1,) or not np.isfinite(predicted).all():
                    raise ValueError('invalid model prediction')
                proxy = self.policy_id == 'PROXY-LABEL' or self.policy_id.startswith('PROXY-LABEL-')
                prediction = float(np.clip(predicted[0], 0 if proxy else -1, 1))
                requested = 2 if prediction <= threshold else 10
            return _decision(self.policy_id, requested, len(ranked), caller_cap,
                             'threshold' if mode == 'numeric' else mode, prediction, mode, threshold)
        except Exception as error:
            logger.warning('policy %s full fallback: %s', self.policy_id, error)
            # Endpoint validation still requires its matching action when falling back.
            fallback_mode = 'always_ten' if mode != 'numeric' else mode
            return _decision(self.policy_id, 10, len(ranked), caller_cap,
                             'full_fallback', mode=fallback_mode, threshold=threshold)


def training_thresholds(predictions: np.ndarray) -> list[dict]:
    """Quantile configs from already-clipped finite training predictions only."""
    values = np.asarray(predictions, dtype=np.float64)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all():
        raise ValueError('training predictions must be a nonempty finite vector')
    thresholds = np.unique(np.quantile(values, np.arange(21)/20, method='linear'))
    return ([{'threshold_mode': 'always_ten', 'threshold': None}]
            + [{'threshold_mode': 'numeric', 'threshold': float(value)} for value in thresholds]
            + [{'threshold_mode': 'always_two', 'threshold': None}])
