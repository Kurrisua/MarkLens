"""Explicit local model pre-download command."""

from pathlib import Path

from PIL import Image

from .config import get_settings
from .retrieval import LocalModelRuntime


def main() -> None:
    settings = get_settings()
    settings.model_cache_dir.mkdir(parents=True, exist_ok=True)
    runtime = LocalModelRuntime(settings)
    runtime.embed_texts(["商标近似检索模型预热"])
    temporary = settings.model_cache_dir / "marklens-model-probe.png"
    Image.new("RGB", (64, 64), "white").save(temporary)
    runtime.embed_image(Path(temporary))
    runtime.ocr(Path(temporary))
    temporary.unlink(missing_ok=True)
    print("Text embedding, image embedding and OCR models are ready.")


if __name__ == "__main__":
    main()
