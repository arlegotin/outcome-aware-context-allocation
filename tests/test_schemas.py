from dataclasses import replace

import pytest

from outcome_poc.schemas import (
    CostEvent, Decision, Document, GenerationRequest, GoldRecord, PaidDraft,
    PairedActionRow, Prediction, RankedDocument, ReaderResult, ScoredTask, Task,
    validate_record,
)


def prediction():
    return Prediction(
        run_id="run", task_id="invented", policy_id="fixed-two",
        protocol_hash="protocol", job_id="job", attempt=1, repetition_id=0,
        evidence_ids=["doc"], raw_output='{"answer":"invented"}',
        answer="invented", citations=[("doc", 0)], status="ok",
        model_revision="revision", prompt_hash="prompt", decoding_hash="decode",
        elapsed_seconds=1.25, prompt_tokens=12, generated_tokens=3,
        generation_calls=1, event_ids=["event"],
    )


def event():
    return CostEvent(
        event_id="event", run_id="run", task_id="invented", policy_id="fixed-two",
        role="answer", start_ns=100, stop_ns=200, elapsed_seconds=0.0000001,
        prompt_tokens=12, output_tokens=3, cache_mode="none", source_event_id=None,
        peak_mlx_bytes=0, rss_bytes=1024, swap_used_bytes=0, attempt=1, status="ok",
    )


def test_required_records_accept_complete_invented_payloads():
    ranked = RankedDocument("doc", 0.5, 0, 9, 1, "Invented")
    result = ReaderResult("raw", "invented", [("doc", 0)], "ok", 12, 3,
                          [1] * 12, [2, 3, 4], "eos")
    records = [
        Task("invented", "fit", "Invented question?", ["doc"]),
        Document("doc", "Invented", ["Invented."], 9), ranked,
        Decision("fixed-two", 2, None, None, None, "fixed", "features"),
        GenerationRequest("revision", "model", "prompt", "decode", "answer", 8192,
                          256, 30.0, "none"),
        result, PaidDraft("event", result), prediction(), event(),
        ScoredTask("run", "invented", "fixed-two", "job", 0,
                   1, 1, 1, 1.0, 1.0, 1.0, 1.25, 2.0),
        PairedActionRow(
            task_id="invented", question="Invented question?",
            ranked_documents=[ranked], features={"gap": 0.5},
            small_prediction_id="small", full_prediction_id="full",
            small_joint_em=0, full_joint_em=1, small_answer_em=1, full_answer_em=1,
            small_event_ids=["small-event"], full_event_ids=["full-event"],
            small_cost_seconds=1.0, full_cost_seconds=2.0,
            small_status="ok", full_status="ok",
        ),
        GoldRecord("invented", "invented", [("Invented", 0)]),
    ]
    for record in records:
        validate_record(record)


@pytest.mark.parametrize("changes", [
    {"citations": [("doc", True)]}, {"citations": [("doc", -1)]},
    {"elapsed_seconds": -0.01}, {"elapsed_seconds": float("nan")},
    {"status": "unknown"}, {"prompt_tokens": True}, {"attempt": 0},
    {"citations": [("doc", "0")]}, {"evidence_ids": [42]},
])
def test_prediction_rejects_invalid_runtime_values(changes):
    with pytest.raises(ValueError):
        validate_record(replace(prediction(), **changes))


@pytest.mark.parametrize("changes", [
    {"stop_ns": 99}, {"elapsed_seconds": -1}, {"cache_mode": "free"},
    {"rss_bytes": True}, {"status": "unknown"}, {"output_tokens": -1},
])
def test_cost_event_rejects_invalid_accounting(changes):
    with pytest.raises(ValueError):
        validate_record(replace(event(), **changes))


@pytest.mark.parametrize("mode,threshold,action", [
    ("numeric", 0.25, 2), ("always_two", None, 2),
    ("always_ten", None, 10),
])
def test_learned_threshold_modes_are_valid(mode, threshold, action):
    validate_record(Decision("PRE-OUTCOME-GBM", action, 0.1, mode,
                             threshold, "threshold", "features"))


@pytest.mark.parametrize("mode,threshold,action", [
    (None, None, 2), ("numeric", None, 2), ("numeric", float("inf"), 2),
    ("always_two", 0.5, 2), ("always_two", None, 10),
    ("always_ten", None, 2), ("invented", None, 2),
])
def test_learned_threshold_modes_reject_invalid_combinations(mode, threshold, action):
    with pytest.raises(ValueError):
        validate_record(Decision("PRE-OUTCOME-GBM", action, 0.1, mode,
                                 threshold, "threshold", "features"))


def test_non_threshold_policy_requires_null_threshold():
    with pytest.raises(ValueError):
        validate_record(Decision("fixed-two", 2, None, None, 0.5, "fixed", "features"))


def test_negative_integer_score_delta_and_threshold_are_finite_numbers():
    validate_record(RankedDocument("d", -1, 0, 2, 1, "Invented"))
    validate_record(Decision("PRE-OUTCOME-GBM", 2, -1, "numeric", -1,
                             "threshold", "features"))


@pytest.mark.parametrize("policy", ["PRE-LINEAR", "PRE-RF", "POST-OUTCOME",
                                   "QUERY-ONLY", "PROXY-LABEL"])
def test_all_learned_families_require_threshold_mode(policy):
    with pytest.raises(ValueError):
        validate_record(Decision(policy, 2, 0.1, None, None, "learned", "features"))


def test_primary_learned_policy_rejects_nonprimary_action():
    with pytest.raises(ValueError):
        validate_record(Decision("PRE-OUTCOME-GBM", 3, 0.1, "numeric", 0.2,
                                 "learned", "features"))


def test_generation_request_retains_distinct_model_hash_and_revision():
    request = GenerationRequest(
        model_revision="revision", model_hash="artifact-hash", prompt_hash="prompt",
        decoding_hash="decode", role="answer", max_context_tokens=8192,
        max_new_tokens=256, timeout_seconds=30, cache_mode="none",
    )
    validate_record(request)
    assert request.model_hash == "artifact-hash"
    assert request.model_revision == "revision"


@pytest.mark.parametrize("record", [
    Task("t", "fit", "Invented?", [True]),
    Document("d", "Invented", [42], 2),
    RankedDocument("d", float("inf"), 0, 2, 1, "Invented"),
    GenerationRequest("r", "m", "p", "d", "answer", 8192, 256, -1, "none"),
    ReaderResult("raw", "answer", [("d", True)], "ok", 0, 0, [], [], None),
    PaidDraft("", ReaderResult("raw", None, [], "parse_error", 0, 0, [], [], None)),
    GoldRecord("t", "answer", [("Invented", True)]),
    ScoredTask("r", "t", "p", "j", 0, 1, 0, 1, 1.1, 0.0, 0.0, 1, 2),
])
def test_other_records_reject_invalid_fields(record):
    with pytest.raises(ValueError):
        validate_record(record)


def test_unknown_record_is_rejected():
    with pytest.raises(ValueError):
        validate_record({"status": "ok"})
