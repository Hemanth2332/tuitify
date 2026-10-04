from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable
from typing import Any


class EmbeddingEncoder:
    """Local embedding encoder with an optional SentenceTransformer backend."""

    def __init__(
        self,
        dimension: int = 384,
        model_name: str = "all-MiniLM-L6-v2",
        onnx_model: bool = False,
    ) -> None:
        self.dimension = dimension
        self.model_name = model_name
        self.onnx_model = onnx_model

        if self.onnx_model:
            self._model = self._load_onnx_model()
        else:
            self._model = self._load_transformer_model()

    def encode_track(self, track: dict[str, Any]) -> list[float]:
        return self.encode_text(self.build_track_text(track))

    def encode_text(self, text: str) -> list[float]:
        cleaned = text.strip()
        if not cleaned:
            return [0.0] * self.dimension

        if self._model is not None:
            vector = self._model.encode(cleaned, normalize_embeddings=True)
            return [float(value) for value in vector]

        return self._hash_embed(cleaned)

    def build_track_text(self, track: dict[str, Any]) -> str:
        title = str(track.get("title") or "").strip()
        artist = str(track.get("artist_name") or "").strip()
        tags = track.get("tags") or []
        if isinstance(tags, str):
            tag_text = tags
        else:
            tag_text = " ".join(str(tag).strip() for tag in tags if str(tag).strip())

        parts = [f"Title: {title}" if title else "", f"Artist: {artist}" if artist else ""]
        if tag_text:
            parts.append(f"Tags: {tag_text}")
        return "\n".join(part for part in parts if part)

    @staticmethod
    def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
        left_values = list(left)
        right_values = list(right)
        if not left_values or not right_values or len(left_values) != len(right_values):
            return 0.0

        dot = sum(a * b for a, b in zip(left_values, right_values, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left_values))
        right_norm = math.sqrt(sum(b * b for b in right_values))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _hash_embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = self._tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimension
            sign = 1.0 if digest[8] % 2 == 0 else -1.0
            weight = 1.0 + (digest[9] / 255.0)
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        lowered = text.lower()
        return [token for token in re.split(r"[^\w]+", lowered, flags=re.UNICODE) if token]

    @staticmethod
    def _load_transformer_model() -> Any | None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception:
            return None

        try:
            return SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
        except Exception:
            return None

    @staticmethod
    def _load_onnx_model() -> Any | None:
        try:
            from light_embed import TextEmbedding
        except Exception:
            return None

        try:
            model_path = "sentence-transformers/all-MiniLM-L6-v2"
            return TextEmbedding(model_path)
        except Exception:
            return None
