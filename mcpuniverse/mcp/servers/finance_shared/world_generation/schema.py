"""Validated config schema for deterministic finance benchmark worlds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictConfigModel(BaseModel):
    """Base model that rejects misspelled config fields."""

    model_config = ConfigDict(extra="forbid")


class CountConfig(StrictConfigModel):
    count: int = Field(ge=0)


class AccountConfig(StrictConfigModel):
    count: int = Field(ge=1)
    cash_range: tuple[float, float]

    @field_validator("cash_range")
    @classmethod
    def validate_cash_range(cls, value: tuple[float, float]) -> tuple[float, float]:
        if len(value) != 2 or value[0] < 0 or value[1] < value[0]:
            raise ValueError("cash_range must contain two ascending non-negative values")
        return value


class HoldingsConfig(StrictConfigModel):
    tickers: dict[str, list[str]]
    holdings_per_account: tuple[int, int]

    @field_validator("holdings_per_account")
    @classmethod
    def validate_holding_range(cls, value: tuple[int, int]) -> tuple[int, int]:
        if len(value) != 2 or value[0] < 0 or value[1] < value[0]:
            raise ValueError("holdings_per_account must contain two ascending non-negative values")
        return value

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        flattened = [ticker for group in value.values() for ticker in group]
        if not flattened:
            raise ValueError("at least one ticker is required")
        if any(not ticker or not ticker.strip() for ticker in flattened):
            raise ValueError("tickers must be non-empty strings")
        return value


class OrdersConfig(StrictConfigModel):
    draft_count: int = Field(ge=0)
    historical_count: int = Field(ge=0)


class DocumentsConfig(StrictConfigModel):
    research_count: int = Field(ge=0)
    filing_count: int = Field(ge=0)
    email_count: int = Field(ge=0)
    gp_package_count: int = Field(ge=0)


class TransactionsConfig(StrictConfigModel):
    precedent_deal_count: int = Field(ge=0)


class FixedIncomeConfig(StrictConfigModel):
    bonds: int = Field(ge=0)
    curves: int = Field(ge=0)


class FxConfig(StrictConfigModel):
    currency_pairs: list[str]

    @field_validator("currency_pairs")
    @classmethod
    def validate_pairs(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("at least one currency pair is required")
        if any(len(pair.strip()) != 6 for pair in value):
            raise ValueError("currency pairs must use six-letter symbols such as USDJPY")
        return value


class DerivativesConfig(StrictConfigModel):
    option_templates: int = Field(ge=0)
    vol_surfaces: int = Field(ge=0)


class WorldConfig(StrictConfigModel):
    world_id: str
    seed: int
    as_of_date: str
    base_currency: str
    description: str = "Deterministic financial-services benchmark world for P0/P1 MCP capability coverage."
    clients: CountConfig
    accounts: AccountConfig
    holdings: HoldingsConfig
    orders: OrdersConfig
    documents: DocumentsConfig
    transactions: TransactionsConfig
    fixed_income: FixedIncomeConfig
    fx: FxConfig
    derivatives: DerivativesConfig

    @field_validator("world_id")
    @classmethod
    def validate_world_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("world_id is required")
        if "/" in normalized or "\\" in normalized:
            raise ValueError("world_id must be a directory name, not a path")
        return normalized

    @field_validator("base_currency")
    @classmethod
    def validate_base_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3:
            raise ValueError("base_currency must be an ISO-style three-letter code")
        return normalized


def load_world_config(path: str | Path) -> WorldConfig:
    """Load and validate a benchmark world config file."""
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        payload: Any = yaml.safe_load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"World config must be a YAML object: {config_path}")
    return WorldConfig.model_validate(payload)
