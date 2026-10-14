"""Deterministic injected retrieval dependencies; no public model loads."""
import re
import numpy as np
from outcome_poc.schemas import Document
from outcome_poc.storage import content_hash, canonical_bytes


class Tokenizer:
    model_max_length = 512
    truncation_side = 'right'
    padding_side = 'right'

    def __call__(self, text, add_special_tokens=True, return_offsets_mapping=False,
                 truncation=False, max_length=None, **kwargs):
        offsets = [(m.start(), m.end()) for m in re.finditer(r'\S+', text)]
        ids = [int(content_hash(text[a:b])[:6], 16) for a, b in offsets]
        if truncation and max_length is not None:
            ids = ids[:max_length - (2 if add_special_tokens else 0)]
            offsets = offsets[:len(ids)]
        if add_special_tokens:
            ids = [101] + ids + [102]
            offsets = [(0, 0)] + offsets + [(0, 0)]
        result = {'input_ids': ids}
        if return_offsets_mapping:
            result['offset_mapping'] = offsets
        return result


class Encoder:
    tokenizer = Tokenizer()
    identity = {'revision': 'fixture', 'snapshot_hash': 'fixture'}
    batch_size = 2
    query_max_tokens = 512
    batch_measurements = []

    def __init__(self, coordinates=None):
        self.coordinates = coordinates or {}
        self.texts = []

    def encode(self, texts):
        self.texts.extend(texts)
        result = np.zeros((len(texts), 384), dtype=np.float32)
        for i, text in enumerate(texts):
            result[i, self.coordinates.get(text, 0)] = 1
        return result


def document(title, sentences):
    return Document(content_hash([title, sentences]), title, sentences, sum(map(len, sentences)))


def store(tmp_path, documents):
    from outcome_poc.data_runtime import DocumentStore
    path = tmp_path / 'documents.jsonl'
    path.write_bytes(b''.join(canonical_bytes(d) + b'\n' for d in documents))
    return DocumentStore(path)
