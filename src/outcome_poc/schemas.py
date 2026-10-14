"""Shared records with explicit, strict runtime validation."""

from dataclasses import field, dataclass, fields
from functools import lru_cache
import math
import types
from typing import Union, get_args, get_origin, get_type_hints


STATUSES = frozenset({
    "ok", "abstain", "parse_error", "invalid_citation", "context_overflow",
    "timeout", "budget_exhausted", "infra_error",
})
CACHE_MODES = frozenset({"none", "within_query_prefix", "development_replay"})
LEARNED_POLICY_FAMILIES = frozenset({
    "PRE-OUTCOME-GBM", "PRE-LINEAR", "PRE-RF", "POST-OUTCOME",
    "QUERY-ONLY", "PROXY-LABEL", "SHUFFLED-LABEL-GBM",
})


@dataclass(frozen=True)
class Task:
    task_id: str
    split: str
    question: str
    candidate_ids: list[str]


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    sentences: list[str]
    character_count: int


@dataclass(frozen=True)
class RankedDocument:
    doc_id: str
    score: float
    rank: int
    character_count: int
    sentence_count: int
    title: str


@dataclass(frozen=True)
class Decision:
    policy_id: str
    action_k: int
    predicted_delta: float | None
    threshold_mode: str | None
    threshold: float | None
    reason: str
    feature_schema_hash: str
    requested_budget: int | None = None
    effective_budget: int | None = None


@dataclass(frozen=True)
class GenerationRequest:
    model_revision: str
    model_hash: str
    prompt_hash: str
    decoding_hash: str
    role: str
    max_context_tokens: int
    max_new_tokens: int
    timeout_seconds: float
    cache_mode: str


@dataclass(frozen=True)
class ReaderResult:
    raw_output: str
    answer: str | None
    citations: list[tuple[str, int]]
    status: str
    prompt_tokens: int
    generated_tokens: int
    prompt_token_ids: list[int]
    generated_token_ids: list[int]
    stop_reason: str | None
    telemetry: dict[str, float | str | int | None | list[float]] = field(default_factory=dict)


@dataclass(frozen=True)
class PaidDraft:
    generation_event_id: str
    reader_result: ReaderResult


@dataclass(frozen=True)
class Prediction:
    run_id: str
    task_id: str
    policy_id: str
    protocol_hash: str
    job_id: str
    attempt: int
    repetition_id: int | str
    evidence_ids: list[str]
    raw_output: str
    answer: str | None
    citations: list[tuple[str, int]]
    status: str
    model_revision: str
    prompt_hash: str
    decoding_hash: str
    elapsed_seconds: float
    prompt_tokens: int
    generated_tokens: int
    generation_calls: int
    event_ids: list[str]


@dataclass(frozen=True)
class CostEvent:
    event_id: str
    run_id: str
    task_id: str
    policy_id: str
    role: str
    start_ns: int
    stop_ns: int
    elapsed_seconds: float
    prompt_tokens: int
    output_tokens: int
    cache_mode: str
    source_event_id: str | None
    peak_mlx_bytes: int | None
    rss_bytes: int | None
    swap_used_bytes: int | None
    attempt: int
    status: str
    clean_prefill_seconds: float = 0.


@dataclass(frozen=True)
class ScoredTask:
    run_id: str
    task_id: str
    policy_id: str
    job_id: str
    repetition_id: int | str
    answer_em: int
    support_em: int
    joint_em: int
    answer_f1: float
    support_f1: float
    joint_f1: float
    total_serving_seconds: float
    total_experiment_seconds: float


@dataclass(frozen=True)
class PairedActionRow:
    task_id: str
    question: str
    ranked_documents: list[RankedDocument]
    features: dict[str, float]
    small_prediction_id: str
    full_prediction_id: str
    small_joint_em: int
    full_joint_em: int
    small_answer_em: int
    full_answer_em: int
    small_event_ids: list[str]
    full_event_ids: list[str]
    small_cost_seconds: float
    full_cost_seconds: float
    small_status: str
    full_status: str


@dataclass(frozen=True)
class GoldRecord:
    task_id: str
    answer: str
    supporting_facts: list[tuple[str, int]]


_RECORD_TYPES = frozenset({
    Task, Document, RankedDocument, Decision, GenerationRequest, ReaderResult,
    PaidDraft, Prediction, CostEvent, ScoredTask, PairedActionRow, GoldRecord,
})


@lru_cache(maxsize=None)
def _hints(record_type: type) -> dict:
    return get_type_hints(record_type)


def _check_type(value: object, expected: object, field: str) -> None:
    origin = get_origin(expected)
    args = get_args(expected)
    if origin in (Union, types.UnionType):
        for choice in args:
            try:
                _check_type(value, choice, field)
                return
            except ValueError:
                pass
        raise ValueError(f"{field}: unexpected value or type")
    if expected is float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{field}: expected finite number")
    elif expected in (str, int, type(None)):
        if type(value) is not expected:
            raise ValueError(f"{field}: expected {expected.__name__}")
    elif origin is list:
        if type(value) is not list:
            raise ValueError(f"{field}: expected list")
        for index, item in enumerate(value):
            _check_type(item, args[0], f"{field}[{index}]")
    elif origin is tuple:
        if type(value) is not tuple or len(value) != len(args):
            raise ValueError(f"{field}: expected {len(args)}-element tuple")
        for index, (item, item_type) in enumerate(zip(value, args)):
            _check_type(item, item_type, f"{field}[{index}]")
    elif origin is dict:
        if type(value) is not dict:
            raise ValueError(f"{field}: expected dict")
        for key, item in value.items():
            _check_type(key, args[0], field)
            _check_type(item, args[1], f"{field}.{key}")
    elif expected in _RECORD_TYPES and type(value) is expected:
        validate_record(value)
    else:
        raise ValueError(f"{field}: unexpected value or type")


def validate_record(record: object) -> None:
    """Reject invalid field types, numerics and record-specific invariants."""
    if type(record) not in _RECORD_TYPES:
        raise ValueError(f"Unsupported record type: {type(record).__name__}")
    for field in fields(record):
        name = field.name
        value = getattr(record, name)
        _check_type(value, _hints(type(record))[name], name)
        if isinstance(value, str) and name not in {"raw_output", "answer"} and not value:
            raise ValueError(f"{name}: must not be empty")
        if type(value) is int and value < 0 and name not in {"score", "predicted_delta", "threshold"}:
            raise ValueError(f"{name}: must be nonnegative")
        if name.endswith("_seconds") and value < 0:
            raise ValueError(f"{name}: must be nonnegative")
        if name.endswith("status") and value not in STATUSES:
            raise ValueError(f"{name}: unknown status {value!r}")
        if name == "cache_mode" and value not in CACHE_MODES:
            raise ValueError(f"{name}: unknown cache mode {value!r}")
        if name.endswith("_em") and value not in (0, 1):
            raise ValueError(f"{name}: expected binary exact-match value")
        if name.endswith("_f1") and not 0 <= value <= 1:
            raise ValueError(f"{name}: expected score in [0, 1]")
    if isinstance(record, (ReaderResult, Prediction, GoldRecord)):
        citations = record.supporting_facts if isinstance(record, GoldRecord) else record.citations
        if any(not title or index < 0 for title, index in citations):
            raise ValueError("citations: expected nonempty identity and nonnegative index")
    if isinstance(record, ReaderResult):
        if any(token < 0 for token in record.prompt_token_ids + record.generated_token_ids):
            raise ValueError("token IDs: must be nonnegative")
    if isinstance(record, (Prediction, CostEvent)) and record.attempt < 1:
        raise ValueError("attempt: must be at least one")
    if isinstance(record, CostEvent) and record.stop_ns < record.start_ns:
        raise ValueError("stop_ns: precedes start_ns")
    if isinstance(record, GenerationRequest):
        if min(record.max_context_tokens, record.max_new_tokens, record.timeout_seconds) <= 0:
            raise ValueError("generation limits and timeout must be positive")
    if isinstance(record, Decision):
        mode, threshold = record.threshold_mode, record.threshold
        policy_id = record.policy_id.upper()
        learned = any(policy_id == family or policy_id.startswith(family + "-")
                      for family in LEARNED_POLICY_FAMILIES)
        no_context = record.policy_id == "NO-CONTEXT-DIAGNOSTIC"
        if no_context:
            if (record.action_k, record.requested_budget, record.effective_budget) != (0, 0, 0) or mode is not None or threshold is not None or record.predicted_delta is not None:
                raise ValueError("no-context diagnostic requires explicit zero budgets and null threshold metadata")
            return
        if record.action_k < 1:
            raise ValueError("action_k: must be positive")
        if learned and record.action_k not in {2, 10}:
            raise ValueError("learned action_k: expected two or ten")
        if not learned and (mode is not None or threshold is not None):
            raise ValueError("non-threshold policies require null threshold mode and threshold")
        if mode is None:
            if threshold is not None or learned:
                raise ValueError("learned policies require a threshold mode; null mode requires null threshold")
        elif mode == "numeric":
            if threshold is None:
                raise ValueError("numeric threshold mode requires a finite threshold")
        elif mode in {"always_two", "always_ten"}:
            expected_action = 2 if mode == "always_two" else 10
            if threshold is not None or record.action_k != expected_action:
                raise ValueError("endpoint threshold mode requires null threshold and its fixed action")
        else:
            raise ValueError("unknown threshold mode")
