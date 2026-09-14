"""Model provider abstraction and BYOK.

Nothing above this module may import a provider SDK. `tests/test_import_boundaries.py`
enforces that, because provider neutrality is a commercial claim and has to be
architecturally real rather than asserted.

Execution modes
---------------
MODEL          a real LLM call happened, via the configured provider
DETERMINISTIC  no credentials configured; the appliance ran graph-derived
               analysis only, and says so

DETERMINISTIC is not a fake model. It produces no invented narrative at all: the
specialists fall back to reasoning that is computed from the engineering graph and
classified DERIVED rather than INFERRED. The distinction is recorded in the run
record and displayed in the UI, so a demonstration can never imply a model call
happened when it did not.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

from ..core.errors import ModelError, ModelNotConfiguredError

MODE_MODEL = "model"
MODE_DETERMINISTIC = "deterministic"


class SecretRef:
    """A credential reference that cannot be interpolated into a prompt or log.

    Leakage is prevented by type rather than by code review: __str__, __repr__
    and __format__ all refuse to yield the value.
    """

    __slots__ = ("_env_var",)

    def __init__(self, env_var: str) -> None:
        self._env_var = env_var

    @property
    def env_var(self) -> str:
        return self._env_var

    def resolve(self) -> str | None:
        return os.environ.get(self._env_var)

    def is_available(self) -> bool:
        return bool(self.resolve())

    def __str__(self) -> str:
        raise RuntimeError(
            f"SecretRef({self._env_var}) must never be rendered into a string. "
            "Use .resolve() at the point of use only.")

    __repr__ = __str__

    def __format__(self, spec: str) -> str:
        raise RuntimeError(f"SecretRef({self._env_var}) must never be formatted.")


class ModelProvider(ABC):
    execution_mode: str = MODE_MODEL
    provider_name: str = "abstract"
    model_id: str = "abstract"

    @abstractmethod
    def complete(self, system: str, prompt: str, max_tokens: int = 2000) -> str: ...

    @abstractmethod
    def capabilities(self) -> dict: ...

    def describe(self) -> dict:
        return {"execution_mode": self.execution_mode, "provider": self.provider_name,
                "model": self.model_id, **self.capabilities()}


class DeterministicProvider(ModelProvider):
    """No model configured. Narrative generation is refused, not simulated."""

    execution_mode = MODE_DETERMINISTIC
    provider_name = "none"
    model_id = "deterministic"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def complete(self, system: str, prompt: str, max_tokens: int = 2000) -> str:
        raise ModelNotConfiguredError(
            "No model provider is configured; narrative generation is unavailable. "
            "Deterministic graph analysis is unaffected.", reason=self.reason)

    def capabilities(self) -> dict:
        return {"structured_output": False, "tool_calling": False,
                "streaming": False, "context_window": 0,
                "reason_unavailable": self.reason}


class AnthropicProvider(ModelProvider):
    """BYOK Anthropic. The key is read from the configured env var at call time
    and never held as an attribute."""

    execution_mode = MODE_MODEL
    provider_name = "anthropic"

    def __init__(self, model_id: str, secret: SecretRef, base_url: str | None = None):
        self.model_id = model_id
        self._secret = secret
        self._base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic  # local import keeps the boundary clean
            except ImportError as exc:
                raise ModelError("anthropic SDK is not installed") from exc
            key = self._secret.resolve()
            if not key:
                raise ModelNotConfiguredError(
                    f"Environment variable {self._secret.env_var} is not set")
            kwargs: dict[str, Any] = {"api_key": key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def complete(self, system: str, prompt: str, max_tokens: int = 2000) -> str:
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self.model_id, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": prompt}])
        except Exception as exc:
            raise ModelError(f"Model call failed: {exc}") from exc
        return "".join(getattr(b, "text", "") for b in response.content)

    def capabilities(self) -> dict:
        return {"structured_output": True, "tool_calling": True,
                "streaming": True, "context_window": 200000}


class LiteLLMProvider(ModelProvider):
    """Multi-provider access via LiteLLM. Optional dependency."""

    execution_mode = MODE_MODEL
    provider_name = "litellm"

    def __init__(self, model_id: str, secret: SecretRef, base_url: str | None = None):
        self.model_id = model_id
        self._secret = secret
        self._base_url = base_url

    def complete(self, system: str, prompt: str, max_tokens: int = 2000) -> str:
        try:
            import litellm
        except ImportError as exc:
            raise ModelError("litellm is not installed") from exc
        key = self._secret.resolve()
        if not key:
            raise ModelNotConfiguredError(
                f"Environment variable {self._secret.env_var} is not set")
        try:
            response = litellm.completion(
                model=self.model_id, api_key=key, api_base=self._base_url,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompt}])
        except Exception as exc:
            raise ModelError(f"Model call failed: {exc}") from exc
        return response["choices"][0]["message"]["content"]

    def capabilities(self) -> dict:
        return {"structured_output": True, "tool_calling": True,
                "streaming": True, "context_window": 128000}


def build_provider(config: dict) -> ModelProvider:
    """Construct the provider from configuration alone.

    No provider name, model id, endpoint or credential is hardcoded anywhere.
    If credentials are absent we degrade to DETERMINISTIC and record why - we
    never substitute a canned response for a model call.
    """
    provider = (config.get("provider") or "").lower()
    model_id = config.get("model") or ""
    env_var = config.get("api_key_env") or ""
    base_url = config.get("base_url") or None

    if not provider or provider == "none":
        return DeterministicProvider("No model provider configured in appliance config.")
    if not env_var:
        return DeterministicProvider(
            f"Provider '{provider}' configured but no api_key_env was declared.")

    secret = SecretRef(env_var)
    if not secret.is_available():
        return DeterministicProvider(
            f"Provider '{provider}' configured but environment variable "
            f"{env_var} is not set.")

    if provider == "anthropic":
        return AnthropicProvider(model_id, secret, base_url)
    if provider == "litellm":
        return LiteLLMProvider(model_id, secret, base_url)
    return DeterministicProvider(f"Unknown provider '{provider}'.")
