"""Deterministic multimodal retrieval primitives and scoring engine."""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import imagehash
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pypinyin import Style, lazy_pinyin
from rapidfuzz.fuzz import WRatio
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .errors import AppError
from .models import ImageAsset, SourceDefinition, Trademark, TrademarkFeature

CHANNEL_WEIGHTS = {
    "visual": 0.30,
    "text": 0.30,
    "phonetic": 0.15,
    "semantic": 0.15,
    "category": 0.10,
}
HIGH_RISK_THRESHOLD = 0.75
MEDIUM_RISK_THRESHOLD = 0.50
ALLOWED_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", normalized)


def phonetic_text(value: str) -> str:
    return "".join(lazy_pinyin(normalize_text(value), style=Style.NORMAL, errors="ignore"))


def text_similarity(left: str, right: str) -> float:
    if not normalize_text(left) or not normalize_text(right):
        return 0.0
    return round(WRatio(normalize_text(left), normalize_text(right)) / 100, 6)


def phonetic_similarity(left: str, right: str) -> float:
    left_pinyin, right_pinyin = phonetic_text(left), phonetic_text(right)
    if not left_pinyin or not right_pinyin:
        return 0.0
    return round(WRatio(left_pinyin, right_pinyin) / 100, 6)


def char_ngram_vector(text: str, dimensions: int = 512) -> np.ndarray:
    """Deterministic CI fallback; production uses FastEmbed BGE."""
    normalized = f"  {normalize_text(text)}  "
    vector = np.zeros(dimensions, dtype="<f4")
    for size in (1, 2, 3):
        for index in range(max(0, len(normalized) - size + 1)):
            token = normalized[index : index + size].encode("utf-8")
            digest = hashlib.blake2b(token, digest_size=8).digest()
            slot = int.from_bytes(digest, "little") % dimensions
            vector[slot] += 1.0
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def vector_to_blob(vector: Iterable[float]) -> bytes:
    return np.asarray(list(vector), dtype="<f4").tobytes(order="C")


def blob_to_vector(blob: bytes, dimension: int | None = None) -> np.ndarray:
    vector = np.frombuffer(blob, dtype="<f4")
    if dimension is not None and vector.size != dimension:
        raise ValueError(f"向量维度不一致：期望 {dimension}，实际 {vector.size}")
    return vector.copy()


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator == 0 or left.shape != right.shape:
        return 0.0
    return float(np.clip(np.dot(left, right) / denominator, 0.0, 1.0))


def normalized_weights(scores: dict[str, float | None]) -> dict[str, float]:
    available = {
        key: weight for key, weight in CHANNEL_WEIGHTS.items() if scores.get(key) is not None
    }
    total = sum(available.values())
    if total == 0:
        return {}
    return {key: round(weight / total, 6) for key, weight in available.items()}


def weighted_score(scores: dict[str, float | None]) -> tuple[float, dict[str, float]]:
    weights = normalized_weights(scores)
    score = sum(float(scores[key] or 0) * weight for key, weight in weights.items())
    return round(score, 6), weights


def risk_level(score: float, has_evidence: bool = True) -> str:
    if not has_evidence:
        return "insufficient_evidence"
    if score >= HIGH_RISK_THRESHOLD:
        return "high"
    if score >= MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"


def phash_similarity(left: str | None, right: str | None) -> float | None:
    if not left or not right:
        return None
    left_hash, right_hash = imagehash.hex_to_hash(left), imagehash.hex_to_hash(right)
    return round(1 - (left_hash - right_hash) / len(left_hash.hash) ** 2, 6)


def visual_similarity(embedding_score: float | None, phash_score: float | None) -> float | None:
    if embedding_score is not None and phash_score is not None:
        return round(0.65 * embedding_score + 0.35 * phash_score, 6)
    return embedding_score if embedding_score is not None else phash_score


@dataclass
class ProcessedImage:
    content: bytes
    mime_type: str
    extension: str
    width: int
    height: int
    sha256: str
    phash: str


def process_image(
    content: bytes, filename: str | None, settings: Settings | None = None
) -> ProcessedImage:
    settings = settings or get_settings()
    if not content:
        raise AppError(400, "EMPTY_FILE", "上传文件为空。")
    if len(content) > settings.max_upload_bytes:
        raise AppError(413, "FILE_TOO_LARGE", "商标图样不能超过 5 MB。")
    try:
        with Image.open(io.BytesIO(content)) as opened:
            opened.verify()
        with Image.open(io.BytesIO(content)) as opened:
            image_format = opened.format
            if image_format not in ALLOWED_FORMATS:
                raise AppError(415, "UNSUPPORTED_IMAGE_TYPE", "仅支持 PNG、JPEG 和 WebP。")
            if opened.width * opened.height > settings.max_image_pixels:
                raise AppError(413, "IMAGE_TOO_LARGE", "图片像素总量超过安全上限。")
            image = ImageOps.exif_transpose(opened).convert("RGB")
            width, height = image.size
            output = io.BytesIO()
            target_format = "PNG" if image_format == "PNG" else "JPEG"
            image.save(output, format=target_format, optimize=True, quality=92)
            clean_content = output.getvalue()
            mime_type = ALLOWED_FORMATS[target_format]
            extension = ".png" if target_format == "PNG" else ".jpg"
            perceptual_hash = str(imagehash.phash(image))
    except AppError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise AppError(415, "INVALID_IMAGE", "文件头或图像解码结果无效。") from exc
    return ProcessedImage(
        content=clean_content,
        mime_type=mime_type,
        extension=extension,
        width=width,
        height=height,
        sha256=hashlib.sha256(clean_content).hexdigest(),
        phash=perceptual_hash,
    )


class LocalModelRuntime:
    """Lazy local OCR and embedding runtime. Model files are never loaded at import time."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._text_model: Any = None
        self._image_model: Any = None
        self._ocr: Any = None

    def embed_texts(self, texts: list[str]) -> list[np.ndarray]:
        if not self.settings.model_runtime_enabled:
            return [char_ngram_vector(text) for text in texts]
        if self._text_model is None:
            from fastembed import TextEmbedding

            self._text_model = TextEmbedding(
                model_name=self.settings.text_embedding_model,
                cache_dir=str(self.settings.model_cache_dir),
            )
        return [np.asarray(item, dtype="<f4") for item in self._text_model.embed(texts)]

    def embed_image(self, path: Path) -> np.ndarray | None:
        if not self.settings.model_runtime_enabled:
            return None
        try:
            if self._image_model is None:
                from fastembed import ImageEmbedding

                self._image_model = ImageEmbedding(
                    model_name=self.settings.image_embedding_model,
                    cache_dir=str(self.settings.model_cache_dir),
                )
            return np.asarray(next(iter(self._image_model.embed([str(path)]))), dtype="<f4")
        except (ImportError, StopIteration, RuntimeError, ValueError):
            return None

    def ocr(self, path: Path) -> tuple[str | None, float | None, str]:
        if not self.settings.model_runtime_enabled:
            return None, None, "disabled"
        try:
            if self._ocr is None:
                from rapidocr import RapidOCR

                self._ocr = RapidOCR()
            result = self._ocr(str(path))
            texts: list[str] = []
            scores: list[float] = []
            # RapidOCR 3.x returns an object; older versions returned tuple-like results.
            rows = getattr(result, "txts", None)
            confidences = getattr(result, "scores", None)
            if rows:
                texts = [str(item) for item in rows]
                scores = [float(item) for item in (confidences or [])]
            elif isinstance(result, tuple) and result and result[0]:
                texts = [str(item[1]) for item in result[0]]
                scores = [float(item[2]) for item in result[0]]
            confidence = sum(scores) / len(scores) if scores else None
            return " ".join(texts).strip() or None, confidence, "rapidocr"
        except (ImportError, RuntimeError, ValueError, OSError):
            return None, None, "unavailable"


def save_asset(session: Session, content: bytes, filename: str | None) -> ImageAsset:
    settings = get_settings()
    processed = process_image(content, filename, settings)
    duplicate = session.scalar(select(ImageAsset).where(ImageAsset.sha256 == processed.sha256))
    if duplicate:
        return duplicate
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid4().hex}{processed.extension}"
    path = settings.upload_dir / storage_key
    path.write_bytes(processed.content)
    runtime = LocalModelRuntime(settings)
    ocr_text, ocr_confidence, ocr_model = runtime.ocr(path)
    asset = ImageAsset(
        storage_key=storage_key,
        original_filename=(filename or "upload")[:255],
        mime_type=processed.mime_type,
        sha256=processed.sha256,
        byte_size=len(processed.content),
        width=processed.width,
        height=processed.height,
        ocr_text=ocr_text,
        ocr_confidence=ocr_confidence,
        ocr_model=ocr_model,
        phash=processed.phash,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def _class_similarity(query_classes: list[int], candidate_classes: list[int]) -> float:
    if not query_classes:
        return 0.0
    query, candidate = set(query_classes), set(candidate_classes)
    return 1.0 if query & candidate else 0.0


def _reasons(scores: dict[str, float | None], candidate: Trademark) -> list[str]:
    reasons: list[str] = []
    labels = {
        "visual": "整体图形视觉印象接近",
        "text": "商标文字构成接近",
        "phonetic": "主要文字读音接近",
        "semantic": "文字语义向量接近",
        "category": "指定商品或服务类别重合",
    }
    for key, label in labels.items():
        if scores.get(key) is not None and float(scores[key] or 0) >= 0.7:
            reasons.append(label)
    jurisdiction = str(candidate.raw_record.get("jurisdiction") or "CN")
    if jurisdiction not in {"CN", "DEMO"}:
        reasons.append(f"{jurisdiction} 境外记录仅用于相似度参考，不构成中国在先权利结论")
    elif candidate.status in {"已注册", "初步审定", "有效"}:
        reasons.append("候选商标当前状态可能形成在先权利障碍")
    return reasons or ["多通道综合分数进入候选范围，建议人工复核"]


def search_trademarks(session: Session, case: Any, top_k: int = 10) -> list[dict[str, Any]]:
    settings = get_settings()
    runtime = LocalModelRuntime(settings)
    candidates = list(session.scalars(select(Trademark)).all())
    if not candidates:
        return []
    query_text = " ".join(filter(None, [case.trademark_name, case.confirmed_ocr_text]))
    query_embedding = runtime.embed_texts([query_text])[0]
    stored_text_rows = session.scalars(
        select(TrademarkFeature).where(
            TrademarkFeature.trademark_id.in_([item.id for item in candidates]),
            TrademarkFeature.feature_type == "text",
            TrademarkFeature.model_name == settings.text_embedding_model,
        )
    ).all()
    stored_text = {item.trademark_id: item for item in stored_text_rows}
    missing = [item for item in candidates if item.id not in stored_text]
    generated = dict(
        zip(
            [item.id for item in missing],
            runtime.embed_texts([item.name for item in missing]),
            strict=True,
        )
    )
    candidate_embeddings = [
        (
            blob_to_vector(stored_text[item.id].vector_blob, stored_text[item.id].dimension)
            if item.id in stored_text
            else generated[item.id]
        )
        for item in candidates
    ]

    query_asset = session.get(ImageAsset, case.image_asset_id) if case.image_asset_id else None
    query_image_embedding: np.ndarray | None = None
    if query_asset:
        query_image_embedding = runtime.embed_image(settings.upload_dir / query_asset.storage_key)

    source_ids = {item.source_id for item in candidates}
    sources = {
        item.id: item
        for item in session.scalars(
            select(SourceDefinition).where(SourceDefinition.id.in_(source_ids))
        ).all()
    }
    candidate_feature_rows = session.scalars(
        select(TrademarkFeature).where(
            TrademarkFeature.trademark_id.in_([item.id for item in candidates]),
            TrademarkFeature.feature_type == "image",
        )
    ).all()
    image_features = {item.trademark_id: item for item in candidate_feature_rows}

    ranked: list[dict[str, Any]] = []
    for candidate, semantic_vector in zip(candidates, candidate_embeddings, strict=True):
        visual_embedding_score: float | None = None
        candidate_feature = image_features.get(candidate.id)
        if query_image_embedding is not None and candidate_feature:
            visual_embedding_score = cosine_similarity(
                query_image_embedding,
                blob_to_vector(candidate_feature.vector_blob, candidate_feature.dimension),
            )
        candidate_asset = (
            session.get(ImageAsset, candidate.image_asset_id) if candidate.image_asset_id else None
        )
        visual_score = visual_similarity(
            visual_embedding_score,
            phash_similarity(
                query_asset.phash if query_asset else None,
                candidate_asset.phash if candidate_asset else None,
            ),
        )
        scores: dict[str, float | None] = {
            "visual": visual_score,
            "text": text_similarity(query_text, candidate.name),
            "phonetic": phonetic_similarity(query_text, candidate.name),
            "semantic": round(cosine_similarity(query_embedding, semantic_vector), 6),
            "category": _class_similarity(case.nice_classes, candidate.nice_classes),
        }
        overall, applied_weights = weighted_score(scores)
        source = sources[candidate.source_id]
        ranked.append(
            {
                "trademark": candidate,
                "source": source,
                "scores": {**scores, "overall": overall, "applied_weights": applied_weights},
                "reasons": _reasons(scores, candidate),
            }
        )
    recalled_ids: set[str] = set()
    for channel in CHANNEL_WEIGHTS:
        channel_ranked = sorted(
            (item for item in ranked if item["scores"].get(channel) is not None),
            key=lambda item: item["scores"][channel],
            reverse=True,
        )[:30]
        recalled_ids.update(item["trademark"].id for item in channel_ranked)
    merged = [item for item in ranked if item["trademark"].id in recalled_ids]
    merged.sort(key=lambda item: item["scores"]["overall"], reverse=True)
    return merged[:top_k]
