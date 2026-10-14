"""Initial local, CPU-only float32 BGE encoder adapter."""
from pathlib import Path
import numpy as np


def validate_vectors(values: np.ndarray, rows: int) -> np.ndarray:
    if not isinstance(values, np.ndarray) or values.shape != (rows, 384):
        raise ValueError('encoder must produce 384-dimensional rows')
    if values.dtype != np.float32 or not np.isfinite(values).all():
        raise ValueError('encoder rows must be finite float32')
    if not np.allclose(np.linalg.norm(values, axis=1), 1.0, atol=1e-5):
        raise ValueError('encoder rows must be normalized')
    return values


class EncoderBackend:
    def __init__(self, snapshot: Path):
        if not isinstance(snapshot, Path) or not snapshot.is_dir():
            raise ValueError('encoder requires an existing local snapshot Path')
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(str(snapshot.resolve()), device='cpu', local_files_only=True,
                                         trust_remote_code=False, model_kwargs={'use_safetensors': True})
        self.model.float()
        self.model.eval()

    def encode(self, texts: list[str]) -> np.ndarray:
        if type(texts) is not list or any(type(text) is not str for text in texts):
            raise ValueError('encoder expects list[str]')
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        values = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True,
                                   precision='float32', device='cpu', show_progress_bar=False)
        return validate_vectors(values, len(texts))
