"""Owned private compatibility API v1, pinned to the historical implementation.

Only generic transaction, supervision and session helpers are reused. The authored
warmup intentionally retains the historical decoding identity; its actual settings
match the study, but it is separately charged and never an assigned observation.
The source snapshot seals these dependencies along with this adapter.
"""
from pathlib import Path
import hashlib
DEPENDENCIES = {'followup/runtime.py': 'c6534c95cca00cd28f36eb15bfa68ca9e2b55da7ab282e62d0e0fc5cda8fff67', 'followup/supervisor.py': '345da795616e55c551a4d9901defa4ce9fe1b8f2e3a267b6e38de72b6e42ea57', 'followup/clock.py': 'a594504d5b64e34b6e1cd61bcc4a6fc885aa7bc43a8d00e941aa6a96260a03ef', 'followup/study.py': '20e35a0c4e324b998ae7dfb3832044c625d0a3c28e3446d5b0a0f7ae744d274a'}
for _name, _sha in DEPENDENCIES.items():
    if hashlib.sha256((Path(__file__).parents[1]/_name).read_bytes()).hexdigest()!=_sha:
        raise RuntimeError('citation compatibility v1 dependency changed: '+_name)
from ..followup.runtime import (completion as base_completion, _commit as commit,
    _empty as empty_result, ResourceMonitor, resource_check, warmup,
    session_accounting, reconcile_sessions, _worker_identity_unknown as worker_identity_unknown,
    stage_lock, sandbox_profile, probe_denials, verify_import_origins as base_verify_import_origins,
    IsolatedReaderFactory as BaseIsolatedReaderFactory)
from ..followup.supervisor import ContinuousBackend, CleanupFailure
from ..followup.clock import continuous_ns, boot_identity
from ..followup.study import verify_index
