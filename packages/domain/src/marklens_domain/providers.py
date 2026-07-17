"""Provider ports.

Concrete providers belong to infrastructure modules. These protocols deliberately
contain no vendor names, credentials, model files, or network configuration.
"""

from collections.abc import Mapping, Sequence
from typing import Protocol, TypedDict


class OCRResult(TypedDict):
    text: str
    confidence: float | None
    provider: str
    model_version: str


class GeneratedText(TypedDict):
    text: str
    provider: str
    model_version: str


class VectorMatch(TypedDict):
    id: str
    score: float
    metadata: Mapping[str, object]


class OCRProvider(Protocol):
    def recognize(self, image: bytes, *, mime_type: str) -> OCRResult: ...


class TextEmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


class ImageEmbeddingProvider(Protocol):
    def embed(self, images: Sequence[bytes]) -> Sequence[Sequence[float]]: ...


class VectorStoreProvider(Protocol):
    def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        filters: Mapping[str, object] | None = None,
    ) -> Sequence[VectorMatch]: ...


class LLMProvider(Protocol):
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        context: Sequence[Mapping[str, object]],
    ) -> GeneratedText: ...


class ObjectStorageProvider(Protocol):
    def put(self, *, key: str, content: bytes, content_type: str) -> str: ...

    def get(self, *, key: str) -> bytes: ...
