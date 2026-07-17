"""Import and enrich the small official IPO CZ ST.96 trademark release."""

from __future__ import annotations

from io import BytesIO

from PIL import Image
from sqlalchemy import select

from .config import get_settings
from .db import get_session_factory
from .models import SourceDefinition, Trademark, TrademarkFeature
from .retrieval import LocalModelRuntime, save_asset, vector_to_blob
from .sources import REGISTRY, IpoCzSt96Adapter, ensure_source_definitions, sync_source


def _png_bytes(content: bytes) -> bytes:
    output = BytesIO()
    with Image.open(BytesIO(content)) as image:
        image.convert("RGB").save(output, "PNG", optimize=True)
    return output.getvalue()


def main() -> None:
    settings = get_settings()
    adapter = REGISTRY.get("ipo-cz-st96-20260620")
    if not isinstance(adapter, IpoCzSt96Adapter):
        raise RuntimeError("IPO CZ ST.96 适配器未正确注册")
    ready, detail = adapter.health_check()
    if not ready:
        raise FileNotFoundError(f"真实数据样本不可用：{detail}；期望路径：{adapter.path}")

    runtime = LocalModelRuntime(settings)
    with get_session_factory()() as session:
        ensure_source_definitions(session)
        run = sync_source(session, adapter.source_key, page_size=100)
        source = session.scalar(
            select(SourceDefinition).where(SourceDefinition.source_key == adapter.source_key)
        )
        assert source is not None
        trademarks = list(
            session.scalars(select(Trademark).where(Trademark.source_id == source.id)).all()
        )

        images_created = 0
        image_vectors_created = 0
        for trademark in trademarks:
            member = trademark.raw_record.get("image_zip_member")
            if not member:
                continue
            try:
                asset = save_asset(session, _png_bytes(adapter.image_bytes(member)), member)
            except (KeyError, OSError, ValueError):
                continue
            trademark.image_asset_id = asset.id
            image_vector = runtime.embed_image(settings.upload_dir / asset.storage_key)
            if image_vector is not None:
                existing = session.scalar(
                    select(TrademarkFeature).where(
                        TrademarkFeature.trademark_id == trademark.id,
                        TrademarkFeature.feature_type == "image",
                        TrademarkFeature.model_name == settings.image_embedding_model,
                    )
                )
                if existing is None:
                    session.add(
                        TrademarkFeature(
                            trademark_id=trademark.id,
                            feature_type="image",
                            model_name=settings.image_embedding_model,
                            dimension=int(image_vector.size),
                            preprocess_version="rgb-exif-stripped-v1",
                            vector_blob=vector_to_blob(image_vector),
                        )
                    )
                    image_vectors_created += 1
            images_created += 1
        session.commit()

        missing_text = [
            trademark
            for trademark in trademarks
            if session.scalar(
                select(TrademarkFeature.id).where(
                    TrademarkFeature.trademark_id == trademark.id,
                    TrademarkFeature.feature_type == "text",
                    TrademarkFeature.model_name == settings.text_embedding_model,
                )
            )
            is None
        ]
        if missing_text:
            vectors = runtime.embed_texts([trademark.name for trademark in missing_text])
            for trademark, vector in zip(missing_text, vectors, strict=True):
                session.add(
                    TrademarkFeature(
                        trademark_id=trademark.id,
                        feature_type="text",
                        model_name=settings.text_embedding_model,
                        dimension=int(vector.size),
                        preprocess_version="nfkc-v1",
                        vector_blob=vector_to_blob(vector),
                    )
                )
            session.commit()

    print(
        "IPO CZ real-data import completed: "
        f"fetched={run.fetched_count}, created={run.created_count}, "
        f"updated={run.updated_count}, skipped={run.skipped_count}, failed={run.failed_count}, "
        f"images={images_created}, image_vectors={image_vectors_created}, "
        f"text_vectors={len(missing_text)}"
    )


if __name__ == "__main__":
    main()
