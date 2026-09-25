import os
from typing import Any

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient, normalize_content

_PASSTHROUGH_KWARGS = (
    "timeout", "max_retries", "api_key", "reasoning_effort", "temperature",
    "callbacks", "http_client", "http_async_client",
)


def _azure_v1_base_url(endpoint: str) -> str:
    """Return an Azure OpenAI-compatible v1 endpoint URL."""
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/openai/v1"):
        return normalized
    if normalized.endswith("/openai"):
        return f"{normalized}/v1"
    return f"{normalized}/openai/v1"


class NormalizedAzureChatOpenAI(ChatOpenAI):
    """ChatOpenAI with normalized content output for Azure v1 endpoints."""

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        payload.pop("reasoning", None)
        payload["reasoning_effort"] = "none"
        return payload

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


class AzureOpenAIClient(BaseLLMClient):
    """Client for Azure OpenAI deployments.

    Requires environment variables:
        AZURE_OPENAI_API_KEY: API key
        AZURE_OPENAI_ENDPOINT: OpenAI-compatible v1 URL
        AZURE_OPENAI_DEPLOYMENT_NAME: Deployment name
    """

    def __init__(self, model: str, base_url: str | None = None, **kwargs):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return a ChatOpenAI instance configured for Azure's v1 API."""
        self.warn_if_unknown_model()

        endpoint = self.base_url or os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is required for the azure provider")
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY is required for the azure provider")

        llm_kwargs = {
            "model": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", self.model),
            "base_url": _azure_v1_base_url(endpoint),
            "api_key": api_key,
        }

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # Azure v1 rejects reasoning_effort with function tools on
        # chat/completions. The graph relies on this endpoint for tool calls.
        llm_kwargs.pop("reasoning_effort", None)

        return NormalizedAzureChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Azure accepts any deployed model name."""
        return True
