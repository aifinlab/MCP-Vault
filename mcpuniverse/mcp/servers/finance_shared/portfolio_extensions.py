"""Benchmark-world portfolio extension data for wealth workflows."""
from __future__ import annotations

import copy
from typing import Any

from .data_loader import get_account, has_active_world
from .errors import FinanceRecordNotFoundError
from .normalizers import normalize_account_id, normalize_ticker, round_money
from .world_records import business_state, with_source

DATASET = "accounts"


def get_tax_lots(account_id: str, ticker: str = "") -> dict[str, Any]:
    """Return tax lots for an account."""
    account, payload = _account(account_id)
    normalized_ticker = normalize_ticker(ticker) if ticker else ""
    lots = [
        copy.deepcopy(lot)
        for lot in account.get("tax_lots", [])
        if not normalized_ticker or normalize_ticker(lot.get("ticker", "")) == normalized_ticker
    ]
    result = {"account_id": account["account_id"], "tax_lots": lots}
    return with_source(result, payload, DATASET, "tax_lots", account["account_id"], account, "trusted_internal_system")


def find_tax_loss_harvesting_candidates(account_id: str, min_loss_amount: float = 0.0) -> dict[str, Any]:
    """Find tax lots with unrealized losses."""
    lots_payload = get_tax_lots(account_id)
    candidates = [
        lot for lot in lots_payload["tax_lots"]
        if float(lot.get("unrealized_gain_loss", 0.0)) < -abs(float(min_loss_amount))
    ]
    result = {
        "account_id": lots_payload["account_id"],
        "min_loss_amount": min_loss_amount,
        "candidates": candidates,
    }
    result["world_id"] = lots_payload["world_id"]
    result["data_source"] = lots_payload["data_source"]
    result["evidence"] = lots_payload["evidence"]
    return result


def check_wash_sale_window(account_id: str, ticker: str, as_of_date: str = "") -> dict[str, Any]:
    """Check recent trades for potential wash-sale conflicts."""
    account, payload = _account(account_id)
    normalized_ticker = normalize_ticker(ticker)
    trades = [
        copy.deepcopy(trade)
        for trade in account.get("recent_trades", [])
        if normalize_ticker(trade.get("ticker", "")) == normalized_ticker
    ]
    conflict_trades = [trade for trade in trades if trade.get("wash_sale_relevant")]
    result = {
        "account_id": account["account_id"],
        "ticker": normalized_ticker,
        "as_of_date": as_of_date,
        "wash_sale_conflict": bool(conflict_trades),
        "conflict_trades": conflict_trades,
    }
    return with_source(result, payload, DATASET, "wash_sale_window", account["account_id"], account, "trusted_internal_system")


def get_model_portfolio(account_id: str) -> dict[str, Any]:
    """Return the target allocation model for an account."""
    account, payload = _account(account_id)
    model = copy.deepcopy(account.get("model_portfolio", {}))
    if not model:
        raise FinanceRecordNotFoundError(f"No model portfolio configured for account_id {account['account_id']}")
    model["account_id"] = account["account_id"]
    return with_source(model, payload, DATASET, "model_portfolio", account["account_id"], account, "trusted_internal_system")


def generate_rebalance_proposal(account_id: str, as_of_date: str = "") -> dict[str, Any]:
    """Generate a draft rebalance proposal against account target weights."""
    account, payload = _account(account_id)
    model = account.get("model_portfolio", {})
    targets = model.get("target_allocations", {})
    if not targets:
        raise FinanceRecordNotFoundError(f"No target allocations configured for account_id {account['account_id']}")
    total_market_value = float(account.get("total_market_value", 0.0))
    if total_market_value <= 0:
        total_market_value = float(account.get("cash", 0.0)) + sum(
            float(holding.get("market_value", 0.0))
            for holding in account.get("holdings", [])
        )
    current_values = {normalize_ticker(item.get("ticker", "")): float(item.get("market_value", 0.0)) for item in account.get("holdings", [])}
    proposals = []
    for ticker, target_weight in targets.items():
        normalized_ticker = normalize_ticker(ticker)
        target_value = total_market_value * float(target_weight)
        current_value = current_values.get(normalized_ticker, 0.0)
        delta = round_money(target_value - current_value)
        if abs(delta) < 1.0:
            continue
        proposals.append({
            "ticker": normalized_ticker,
            "side": "BUY" if delta > 0 else "SELL",
            "estimated_trade_value": abs(delta),
            "current_value": round_money(current_value),
            "target_value": round_money(target_value),
            "status": "draft_not_submitted",
        })
    result = {
        "account_id": account["account_id"],
        "as_of_date": as_of_date,
        "total_market_value": round_money(total_market_value),
        "proposal_status": "draft_not_submitted",
        "trades": proposals,
    }
    return with_source(result, payload, DATASET, "rebalance_proposal", account["account_id"], account, "trusted_internal_system")


def _account(account_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_account_id = normalize_account_id(account_id)
    if has_active_world():
        payload = business_state(DATASET)
        for account in payload.get("accounts", []):
            if normalize_account_id(account.get("account_id", "")) == normalized_account_id:
                return copy.deepcopy(account), payload
        raise FinanceRecordNotFoundError(f"No account found for account_id {normalized_account_id}")
    legacy_account = get_account(account_id)
    return legacy_account, {
        "world_id": legacy_account["world_id"],
        "payload_sha256": "",
        "world_id": legacy_account["world_id"],
    }
