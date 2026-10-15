"""Immutable sole-candidate settings and a local nonthinking tokenizer facade."""
from dataclasses import dataclass
import copy
import json
from pathlib import Path

from ..storage import content_hash


# Covers the entire public profile, including inventories and inspected provenance.
CONFIG_HASH = '416d88e56dbc9007d64e54ff5a60ae609f17711c58e29fb91b0ce7369c740732'
READER = {
    'repo_id': 'mlx-community/Qwen3-14B-4bit',
    'revision': 'a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4',
    'max_context_tokens': 8192, 'max_new_tokens': 256,
    'timeout_seconds': 120, 'prefill_step_size': 512,
    'enable_thinking': False, 'temperature': 0, 'batch_size': 1,
    'cache_mode': 'none', 'kv_cache': 'default', 'result_reuse': False,
    'repairs': 0, 'semantic_retries': 0,
}


def load_config(path: Path) -> dict:
    """Reject any deviation from the pinned public profile before acquisition."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate profile setting: {key}')
            result[key] = value
        return result
    config = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)
    if content_hash(config) != CONFIG_HASH:
        raise ValueError('reader profile settings, pin or inventory differs from prescribed profile')
    return config


class NonThinkingTokenizer:
    """Forward the installed tokenizer API while fixing the chat-template mode.

    The installed template stays intact. The wrapper is picklable whenever its
    tokenizer is picklable, and __getattr__ avoids recursion during unpickling.
    """
    def __init__(self, tokenizer):
        self._tokenizer = tokenizer

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_tokenizer'), name)

    def apply_chat_template(self, *args, **kwargs):
        if 'enable_thinking' in kwargs and kwargs['enable_thinking'] is not False:
            raise ValueError('reader profile requires enable_thinking=False')
        return self._tokenizer.apply_chat_template(*args, **{**kwargs, 'enable_thinking': False})


@dataclass(frozen=True)
class ProfileFactory:
    """Compose NativeReaderFactory using its existing backend-settings interface.

    Pass {**load_config(path)['reader'], 'asset': manifest['assets']['reader']}.
    No model stack imports occur until this callable loads its own backend.
    """
    snapshot: Path
    config: dict

    def __call__(self):
        from ..generation import NativeReaderFactory
        settings = {key: value for key, value in self.config.items() if key != 'asset'}
        # Canonical identity distinguishes booleans from integer lookalikes.
        if content_hash(settings) != content_hash(READER):
            raise ValueError('native reader settings differ from prescribed profile')
        asset = self.config.get('asset', {})
        if any(asset.get(key) != READER[key] for key in ('repo_id', 'revision')):
            raise ValueError('native reader asset differs from prescribed pin')
        backend = NativeReaderFactory(self.snapshot, copy.deepcopy(self.config))()
        backend.tokenizer = NonThinkingTokenizer(backend.tokenizer)
        return backend
