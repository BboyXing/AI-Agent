from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from llm_gateway.core.config import ConfigError


class PromptRegistry:
    def __init__(self, prompts_dir: Path, prompt_names: set[str]) -> None:
        self.environment = Environment(
            loader=FileSystemLoader(prompts_dir),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )
        self._templates: dict[str, Any] = {}
        for name in sorted(prompt_names):
            try:
                self._templates[name] = self.environment.get_template(f"{name}.j2")
            except TemplateNotFound as exc:
                raise ConfigError(f"prompt template not found: {name}.j2") from exc

    def render(self, name: str, variables: dict[str, object]) -> str:
        try:
            template = self._templates[name]
        except KeyError as exc:
            raise ConfigError(f"unknown prompt template: {name}") from exc
        return template.render(**variables).strip()
