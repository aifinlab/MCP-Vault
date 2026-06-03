"""AAAAPI OpenAI-compatible LLM provider."""
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Type, Union

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel as PydanticBaseModel
from pydantic_core import from_json

from mcpuniverse.common.config import BaseConfig
from mcpuniverse.common.context import Context

from .base import BaseLLM

load_dotenv()

AAAAPI_API_KEY_ENV = "AAAAPI_API_KEY"
AAAAPI_BASE_URL_ENV = "AAAAPI_BASE_URL"
DEFAULT_AAAAPI_BASE_URL = "https://api.aaaapi.com/v1"


@dataclass
class AAAAPIConfig(BaseConfig):
    """Configuration for AAAAPI models through its OpenAI-compatible API."""

    model_name: str = "gpt-4o-mini"
    api_key: str = os.getenv(AAAAPI_API_KEY_ENV, "")
    base_url: str = os.getenv(AAAAPI_BASE_URL_ENV, DEFAULT_AAAAPI_BASE_URL)
    temperature: float = 1.0
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_completion_tokens: int = 2048
    seed: int = 12345


class AAAAPIModel(BaseLLM):
    """OpenAI-compatible AAAAPI model wrapper."""

    config_class = AAAAPIConfig
    alias = "aaaapi"
    env_vars = [AAAAPI_API_KEY_ENV]

    def __init__(self, config: Optional[Union[Dict, str]] = None):
        super().__init__()
        self.config = AAAAPIConfig.load(config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)

    def _generate(
            self,
            messages: List[dict[str, str]],
            response_format: Type[PydanticBaseModel] = None,
            **kwargs
    ):
        self._validate_config()
        client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        api_params = {
            "messages": messages,
            "model": self.config.model_name,
            "temperature": self.config.temperature,
            "timeout": int(kwargs.get("timeout", 60)),
            "top_p": self.config.top_p,
            "frequency_penalty": self.config.frequency_penalty,
            "presence_penalty": self.config.presence_penalty,
            "seed": self.config.seed,
            "max_tokens": self.config.max_completion_tokens,
            **kwargs,
        }
        if response_format is not None:
            api_params["response_format"] = {"type": "json_object"}

        chat = client.chat.completions.create(**api_params)
        content = chat.choices[0].message.content
        if response_format is None:
            return content

        try:
            return response_format.model_validate(from_json(content))
        except Exception:
            self.logger.error("Failed to parse the output:\n%s", str(content))
            return None

    def set_context(self, context: Context):
        """Set context, e.g. environment variables."""
        super().set_context(context)
        self.config.api_key = context.env.get(AAAAPI_API_KEY_ENV, self.config.api_key)
        self.config.base_url = context.env.get(AAAAPI_BASE_URL_ENV, self.config.base_url)

    def _validate_config(self) -> None:
        if not self.config.api_key or not self.config.api_key.strip():
            raise ValueError(f"{AAAAPI_API_KEY_ENV} is required for AAAAPIModel")
        if not self.config.base_url or not self.config.base_url.strip():
            raise ValueError(f"{AAAAPI_BASE_URL_ENV} or config.base_url is required for AAAAPIModel")
