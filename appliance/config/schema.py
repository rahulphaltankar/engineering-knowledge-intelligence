"""Configuration as code.

Every customer-specific setting lives here, never in code. A new customer
deployment needs a different config file, not a different image.

Configuration holds secret REFERENCES only - an environment variable name, never
a value. `config.redacted()` is safe to log and is what the UI and health
endpoint display.
"""
from __future__ import annotations

import os

import yaml
from pydantic import BaseModel, Field

from ..core.errors import ConfigurationError


class ModelConfig(BaseModel):
    provider: str = "none"          # none | anthropic | litellm
    model: str = ""
    api_key_env: str = ""           # NAME of the env var, never the value
    base_url_env: str = ""
    max_tokens: int = 1500


class ConnectorConfig(BaseModel):
    connector_id: str
    enabled: bool = False
    settings: dict = Field(default_factory=dict)


class ApplianceConfig(BaseModel):
    profile: str = "demo"
    simulation_mode: bool = True
    model: ModelConfig = Field(default_factory=ModelConfig)
    connectors: list[ConnectorConfig] = Field(default_factory=list)
    agent_packs: list[str] = Field(default_factory=list)
    traversal_depth: int = 2
    # The product surface a new client sees first (a domain profile name).
    default_domain: str = ""
    enabled_outputs: list[str] = Field(default_factory=list)
    telemetry_enabled: bool = False

    def redacted(self) -> dict:
        data = self.model_dump()
        data["model"]["api_key_env"] = self.model.api_key_env or "(not set)"
        data["model"]["api_key_present"] = bool(
            self.model.api_key_env and os.environ.get(self.model.api_key_env))
        return data

    def resolved_model(self) -> dict:
        base_url = os.environ.get(self.model.base_url_env) if self.model.base_url_env else None
        return {"provider": self.model.provider, "model": self.model.model,
                "api_key_env": self.model.api_key_env, "base_url": base_url}


DEFAULT_PATHS = ("config/appliance.yaml", "config/profiles/demo.yaml")


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_config(path: str | None = None) -> ApplianceConfig:
    # Default paths resolve against the working directory first, then the
    # repository root, so the appliance behaves the same wherever it is started.
    candidates = [path] if path else (list(DEFAULT_PATHS)
                                      + [os.path.join(ROOT, p) for p in DEFAULT_PATHS])
    env_path = os.environ.get("APPLIANCE_CONFIG")
    if env_path:
        candidates.insert(0, env_path)
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            try:
                return ApplianceConfig(**raw)
            except Exception as exc:
                raise ConfigurationError(
                    f"Invalid configuration in {candidate}: {exc}") from exc
    return ApplianceConfig()
