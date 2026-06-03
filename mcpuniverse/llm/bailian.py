"""Bailian OpenAI-compatible LLM provider."""
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


@dataclass
class BailianConfig(BaseConfig):
    """Configuration for Bailian models through DashScope compatible mode."""

    model_name: str = "qwen-plus"
    api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    temperature: float = 1.0
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_completion_tokens: int = 2048
    seed: int = 12345


class BailianModel(BaseLLM):
    """OpenAI-compatible Bailian model wrapper."""

    config_class = BailianConfig
    alias = "bailian"
    env_vars = ["DASHSCOPE_API_KEY"]

    def __init__(self, config: Optional[Union[Dict, str]] = None):
        super().__init__()
        self.config = BailianConfig.load(config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)

    def _generate(
            self,
            messages: List[dict[str, str]],
            response_format: Type[PydanticBaseModel] = None,
            **kwargs
    ):
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
        self.config.api_key = context.env.get("DASHSCOPE_API_KEY", self.config.api_key)
