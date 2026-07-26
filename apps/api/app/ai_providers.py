"""Transient, user-supplied model providers.

Credentials in this module are deliberately request-scoped.  They are never
written to an ORM model, audit payload, task metadata, or application log.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

import httpx


class AIConfigurationError(ValueError):
    """The browser supplied an incomplete or unsafe transient AI configuration."""


class AIProviderError(RuntimeError):
    """A remote provider did not return the expected response shape."""


ProviderKind = Literal["server_default", "openai_compatible", "anthropic"]
ImageStrategy = Literal["vector", "model"]


@dataclass(frozen=True, repr=False)
class AIRequestConfig:
    provider: ProviderKind = "server_default"
    model: str = ""
    api_key: str = ""
    base_url: str | None = None
    image_strategy: ImageStrategy = "vector"
    vision_enabled: bool = False

    @property
    def uses_user_key(self) -> bool:
        return self.provider != "server_default"

    @property
    def can_review_images(self) -> bool:
        return self.uses_user_key and self.image_strategy == "model" and self.vision_enabled

    @property
    def generation_mode(self) -> str:
        return "user_anthropic" if self.provider == "anthropic" else "user_openai_compatible"

    @classmethod
    def from_headers(cls, headers: Any) -> AIRequestConfig:
        provider = str(headers.get("X-Marklens-AI-Provider", "server_default")).strip()
        if provider not in {"server_default", "openai_compatible", "anthropic"}:
            raise AIConfigurationError("暂不支持该模型接口格式。")
        model = str(headers.get("X-Marklens-AI-Model", "")).strip()
        api_key = str(headers.get("X-Marklens-AI-Key", "")).strip()
        base_url = str(headers.get("X-Marklens-AI-Base-Url", "")).strip() or None
        strategy = str(headers.get("X-Marklens-Image-Strategy", "vector")).strip()
        vision_enabled = str(headers.get("X-Marklens-Vision-Enabled", "false")).lower() == "true"
        if strategy not in {"vector", "model"}:
            raise AIConfigurationError("图片比对方式无效。")
        if provider == "server_default":
            return cls()
        if not model or not api_key:
            raise AIConfigurationError("请选择模型并填写 API Key，或切换回服务端默认模型。")
        if len(api_key) > 512 or len(model) > 160:
            raise AIConfigurationError("模型配置长度超出允许范围。")
        if provider == "openai_compatible":
            normalized_url = _normalize_openai_base_url(base_url)
        else:
            if base_url:
                raise AIConfigurationError(
                    "Anthropic 格式使用官方 Messages API，不需要填写自定义地址。"
                )
            normalized_url = None
        if strategy == "model" and not vision_enabled:
            raise AIConfigurationError("请先确认所选模型支持图片输入，再启用模型图样复核。")
        return cls(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            api_key=api_key,
            base_url=normalized_url,
            image_strategy=strategy,  # type: ignore[arg-type]
            vision_enabled=vision_enabled,
        )


def _normalize_openai_base_url(value: str | None) -> str:
    url = (value or "https://api.openai.com/v1").rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise AIConfigurationError("兼容接口地址必须是 HTTPS 地址。")
    return url


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIProviderError("模型没有返回可验证的 JSON 结果。") from exc
    if not isinstance(value, dict):
        raise AIProviderError("模型返回的数据格式不正确。")
    return value


def _openai_content(
    text: str, images: list[tuple[bytes, str]] | None = None
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for data, mime_type in images or []:
        encoded = base64.b64encode(data).decode("ascii")
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}}
        )
    return content


def _anthropic_content(
    text: str, images: list[tuple[bytes, str]] | None = None
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    for data, mime_type in images or []:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": base64.b64encode(data).decode("ascii"),
                },
            }
        )
    content.append({"type": "text", "text": text})
    return content


def generate_json(
    config: AIRequestConfig,
    *,
    instruction: str,
    images: list[tuple[bytes, str]] | None = None,
) -> dict[str, Any]:
    """Call an opted-in provider once and return only a JSON object.

    The caller owns schema validation. Error messages intentionally do not
    echo an endpoint, key, request body, or provider response.
    """
    if not config.uses_user_key:
        raise AIProviderError("当前没有启用用户模型配置。")
    json_instruction = f"{instruction}\n只输出一个合法 JSON 对象，不要使用 Markdown 代码块。"
    try:
        with httpx.Client(
            timeout=httpx.Timeout(35.0, connect=10.0), follow_redirects=False
        ) as client:
            if config.provider == "openai_compatible":
                response = client.post(
                    f"{config.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {config.api_key}"},
                    json={
                        "model": config.model,
                        "messages": [
                            {"role": "user", "content": _openai_content(json_instruction, images)}
                        ],
                        "temperature": 0.1,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                text = payload["choices"][0]["message"]["content"]
            else:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": config.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": config.model,
                        "max_tokens": 1400,
                        "temperature": 0.1,
                        "messages": [
                            {
                                "role": "user",
                                "content": _anthropic_content(json_instruction, images),
                            }
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                text = "".join(
                    str(block.get("text", ""))
                    for block in payload.get("content", [])
                    if block.get("type") == "text"
                )
        return _extract_json(str(text))
    except (KeyError, TypeError, ValueError, httpx.HTTPError) as exc:
        raise AIProviderError("模型服务暂时不可用，或该模型不支持当前请求格式。") from exc
