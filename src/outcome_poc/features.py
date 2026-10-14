"""Versioned allocation features built solely from observable rank metadata."""

import math
import re

import numpy as np

from .schemas import RankedDocument, validate_record
from .storage import content_hash


def feature_schema() -> dict:
    """Return a fresh canonical schema; its hash excludes the hash field itself."""
    features = [
        {'name': 'question_log_characters', 'formula': 'log1p(len(question))'},
        {'name': 'question_log_words', 'formula': 'log1p(len(question.split()))'},
    ]
    patterns = [
        ('auxiliary', r'^(is|are|was|were|do|does|did|has|have|had|can|could|will|would)\b'),
        ('date', r'^when\b|\b(what year|which year|what date|which date)\b'),
        ('count', r'^how many\b|\bnumber of\b'),
        ('who', r'^who\b'),
        ('other', 'no preceding pattern matches'),
    ]
    features.extend({'name': f'question_{name}', 'formula': formula} for name, formula in patterns)
    features.extend({'name': f'score_{i}', 'formula': f'padded_scores[{i}]'} for i in range(10))
    features.extend({'name': f'gap_{i}', 'formula': f'scores[{i}]-scores[{i+1}] if {i+1}<m else 0'} for i in range(9))
    features.extend([
        {'name': 'score_mean', 'formula': 'mean(padded_scores)'},
        {'name': 'score_std', 'formula': 'population_std(padded_scores,ddof=0)'},
        {'name': 'score_entropy', 'formula': '-sum(p*log(p)); p=softmax((padded_scores-max(padded_scores))/0.1); zero terms=0'},
        {'name': 'first_two_log_characters', 'formula': 'log1p(sum(ranked[:2].character_count))'},
        {'name': 'all_log_characters', 'formula': 'log1p(sum(ranked[:10].character_count))'},
        {'name': 'document_count', 'formula': 'm'},
    ])
    features.extend({'name': f'rank_mask_{i}', 'formula': f'1 if {i}<m else 0'} for i in range(10))
    schema = {'version': 'features_v1', 'dtype': 'float64', 'features': features,
              'padding': 'for 1<=m<10 pad scores to ten with observed minimum; real-real gaps only; zero masks for padding',
              'question_patterns': 'casefold, collapse whitespace; first matching pattern in listed order',
              'characters': 'Unicode Python length; metadata is len(title)+sum(len(sentence)); no joining separators',
              'empty_packet': 'budget_exhausted before prediction; no features'}
    return {**schema, 'hash': content_hash(schema)}


def validate_ranking(ranked: list[RankedDocument]) -> None:
    """Require a nonempty, at-most-ten descending, zero-based shared ranking."""
    if type(ranked) is not list or not 1 <= len(ranked) <= 10:
        raise ValueError('ranking must contain one to ten documents')
    ids = set()
    previous = math.inf
    for index, document in enumerate(ranked):
        if type(document) is not RankedDocument:
            raise ValueError('ranking must contain RankedDocument records')
        validate_record(document)
        if document.rank != index or document.score > previous or document.doc_id in ids:
            raise ValueError('ranking must have unique IDs, descending scores and zero-based ranks')
        ids.add(document.doc_id)
        previous = document.score


def build_features(question: str, ranked: list[RankedDocument]) -> np.ndarray:
    """Build the fixed 42-vector without loading evidence or annotations."""
    if type(question) is not str:
        raise ValueError('question must be a string')
    validate_ranking(ranked)
    normalized = ' '.join(question.casefold().split())
    patterns = feature_schema()['features'][2:6]
    category = next((i for i, pattern in enumerate(patterns)
                     if re.search(pattern['formula'], normalized)), 4)
    scores = np.array([doc.score for doc in ranked], dtype=np.float64)
    padded = np.pad(scores, (0, 10-len(scores)), constant_values=scores[-1])
    # Center before division, and scale SD before squaring to avoid finite-score overflow.
    with np.errstate(over='ignore', under='ignore'):
        weights = np.exp((padded - padded.max()) / .1)
    probabilities = weights / weights.sum()
    positive = probabilities > 0
    entropy = -np.sum(probabilities[positive] * np.log(probabilities[positive]), dtype=np.float64)
    scale = float(np.max(np.abs(padded)))
    mean = float(np.mean(padded / scale) * scale) if scale else 0.
    std = float(np.std(padded / scale, ddof=0) * scale) if scale else 0.
    values = [math.log1p(len(question)), math.log1p(len(question.split()))]
    values.extend(int(i == category) for i in range(5))
    values.extend(padded)
    values.extend(scores[i]-scores[i+1] if i+1 < len(scores) else 0. for i in range(9))
    values.extend([mean, std, float(entropy), math.log1p(sum(doc.character_count for doc in ranked[:2])),
                   math.log1p(sum(doc.character_count for doc in ranked)), len(ranked)])
    values.extend(int(i < len(ranked)) for i in range(10))
    result = np.array(values, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError('nonfinite allocation features')
    return result


def post_feature_schema() -> dict:
    schema = {'version': 'post_features_v1', 'base_feature_schema_hash': feature_schema()['hash'],
              'features': feature_schema()['features'] + [
                  {'name':'log1p_raw_draft_characters','formula':'log1p(len(raw_output))'},
                  {'name':'draft_contract_valid','formula':'status in (ok, abstain)'},
                  {'name':'empty_answer','formula':'not (answer or empty).strip()'},
                  {'name':'unique_valid_citation_sentences','formula':'unique citations if contract valid else zero'}],
              'feature_count':46}
    return {**schema, 'hash':content_hash(schema)}


def post_features(question: str, ranked: list[RankedDocument], draft) -> np.ndarray:
    from .schemas import PaidDraft
    if type(draft) is not PaidDraft:
        raise ValueError('POST requires an event-backed paid draft')
    validate_record(draft)
    result = draft.reader_result
    valid = result.status in {'ok','abstain'}
    return np.concatenate((build_features(question, ranked), [math.log1p(len(result.raw_output)),
        float(valid), float(not (result.answer or '').strip()),
        float(len(set(result.citations))) if valid else 0.]))
