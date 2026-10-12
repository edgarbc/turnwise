"""Environment-backed provider configuration."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

ProviderName = Literal["jev", "openai"]


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: ProviderName
    model: str
    api_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class Settings:
    typesafe_api_key: str | None = field(default=None, repr=False)
    openai_api_key: str | None = field(default=None, repr=False)
    jev_model: str = "jev-latest"
    openai_model: str | None = None

    @classmethod
    def load(cls, env_file: str | Path = ".env") -> "Settings":
        """Load settings from the environment and an optional dotenv file.

        Values already present in the process environment take precedence.
        """
        load_dotenv(dotenv_path=env_file, override=False)
        return cls(
            typesafe_api_key=os.getenv("TYPESAFE_API_KEY") or None,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            jev_model=os.getenv("JEV_MODEL", "jev-latest").strip() or "jev-latest",
            openai_model=os.getenv("OPENAI_MODEL", "").strip() or None,
        )

    def for_provider(self, name: ProviderName) -> ProviderConfig:
        """Return validated credentials and model selection for a provider."""
        if name == "jev":
            api_key = self.typesafe_api_key
            model = self.jev_model
            key_name = "TYPESAFE_API_KEY"
        elif name == "openai":
            api_key = self.openai_api_key
            model = self.openai_model
            key_name = "OPENAI_API_KEY"
        else:
            raise ValueError(f"Unsupported provider: {name}")

        if not api_key:
            raise ValueError(f"{key_name} is required to use the {name} provider.")
        if not model:
            model_name = "JEV_MODEL" if name == "jev" else "OPENAI_MODEL"
            raise ValueError(f"{model_name} is required to use the {name} provider.")

        return ProviderConfig(name=name, model=model, api_key=api_key)