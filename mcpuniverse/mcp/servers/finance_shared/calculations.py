"""Deterministic finance calculations shared by local MCP servers."""
import copy
import math
from typing import Any

from .data_loader import (
    get_active_world_date,
    get_account,
    get_account_client_context,
    get_client_profile,
    get_company_fundamentals,
    get_compliance_rules,
    get_enriched_holdings,
    get_policy_reference,
    get_market_price,
    get_research_report,
    get_restricted_security,
    get_risk_model,
    get_stress_scenario,
    get_ticker_risk,
    has_task_material,
    is_live_data_mode,
    list_audit_events,
    search_research_reports,
)
from .errors import FinanceDataError
from .normalizers import normalize_account_id, normalize_optional_date, normalize_ticker, round_money
from .schema import data_source_key, normalize_data_source

DEFAULT_CONFIDENCE_LEVEL = 0.95
DEFAULT_ORDER_TYPE = "market"
BUY_SIDE = "BUY"
SELL_SIDE = "SELL"
SUPPORTED_ORDER_SIDES = {BUY_SIDE, SELL_SIDE}
MONEY_TOLERANCE = 0.000001
DEFAULT_SINGLE_NAME_LIMIT = 0.25
DEFAULT_SECTOR_CONCENTRATION_LIMIT = 0.40
BLOCK_SEVERITY = "block"
REVIEW_SEVERITY = "review"


def _append_data_source(data_sources: list[dict[str, Any]], data_source: dict[str, Any]) -> None:
    normalized_data_source = normalize_data_source(data_source)
    if any(data_source_key(source) == data_source_key(normalized_data_source) for source in data_sources):
        return
    data_sources.append(normalized_data_source)


def _collect_data_sources(*payloads: dict[str, Any]) -> list[dict[str, Any]]:
    data_sources = []
    for payload in payloads:
        if payload.get("data_source"):
            _append_data_source(data_sources, payload["data_source"])
        for data_source in payload.get("data_sources", []):
            _append_data_source(data_sources, data_source)
    return data_sources


def _attach_data_sources(result: dict[str, Any], *payloads: dict[str, Any]) -> None:
    data_sources = _collect_data_sources(*payloads)
    if not data_sources:
        return
    result["data_sources"] = data_sources
    if len(data_sources) == 1:
        result["data_source"] = copy.deepcopy(data_sources[0])


def normalize_order_side(side: str) -> str:
    """Normalize and validate order side."""
    if not side or not side.strip():
        raise ValueError("side is required")
    normalized_side = side.strip().upper()
    if normalized_side not in SUPPORTED_ORDER_SIDES:
        raise ValueError(f"side must be one of {sorted(SUPPORTED_ORDER_SIDES)}")
    return normalized_side


def normalize_quantity(quantity: float) -> float:
    """Normalize and validate order quantity."""
    normalized_quantity = float(quantity)
    if normalized_quantity <= 0:
        raise ValueError("quantity must be positive")
    return normalized_quantity


def normalize_product_type(product_type: str) -> str:
    """Normalize and validate product type."""
    if not product_type or not product_type.strip():
        raise ValueError("product_type is required")
    return product_type.strip().lower()


def _policy_issue(policy_code: str, severity: str, message: str, **extra_values) -> dict[str, Any]:
    issue = {
        "policy_code": policy_code,
        "severity": severity,
        "message": message,
    }
    issue.update(extra_values)
    return issue


def _append_unique_issue(issues: list[dict[str, Any]], issue: dict[str, Any]) -> None:
    policy_code = issue["policy_code"]
    if any(existing_issue["policy_code"] == policy_code for existing_issue in issues):
        return
    issues.append(issue)


def _risk_rank(rules: dict[str, Any], risk_level: str) -> int:
    return int(rules.get("risk_level_rank", {}).get(risk_level, 0))


def _required_disclosures(client: dict[str, Any], instrument: dict[str, Any] | None = None) -> list[str]:
    disclosures = set(client.get("required_disclosures", []))
    if instrument and instrument.get("conflict_disclosure_required"):
        disclosures.add("banking_conflict_disclosure")
    return sorted(disclosures)


def get_portfolio_state(account_id: str, as_of_date: str | None = None) -> dict[str, Any]:
    """Return account totals and enriched position weights."""
    account = get_account(account_id)
    holdings_payload = get_enriched_holdings(account_id=account_id, as_of_date=as_of_date)
    invested_market_value = sum(float(holding["market_value"]) for holding in holdings_payload["holdings"])
    cash = float(account.get("cash", 0.0))
    total_market_value = invested_market_value + cash
    if total_market_value <= 0:
        raise ValueError(f"Account {account['account_id']} has non-positive total market value")

    positions = []
    for holding in holdings_payload["holdings"]:
        market_value = float(holding["market_value"])
        company = get_company_fundamentals(holding["ticker"])
        position = copy.deepcopy(holding)
        position["sector"] = company["sector"]
        position["portfolio_weight"] = round(market_value / total_market_value, 6)
        positions.append(position)

    result = {
        "account": account,
        "account_id": account["account_id"],
        "client_id": account["client_id"],
        "world_id": holdings_payload["world_id"],
        "as_of_date": holdings_payload["as_of_date"],
        "base_currency": holdings_payload["base_currency"],
        "cash": round_money(cash),
        "invested_market_value": round_money(invested_market_value),
        "total_market_value": round_money(total_market_value),
        "positions": positions,
    }
    _attach_data_sources(result, holdings_payload)
    return result


def calculate_parametric_var(
        account_id: str,
        as_of_date: str | None = None,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
) -> dict[str, Any]:
    """Calculate one-day parametric VaR from deterministic ticker volatilities."""
    portfolio = get_portfolio_state(account_id=account_id, as_of_date=as_of_date)
    risk_model = get_risk_model()
    confidence_key = f"{float(confidence_level):.2f}"
    z_score = risk_model.get("confidence_z_scores", {}).get(confidence_key)
    if z_score is None:
        raise ValueError(f"Unsupported confidence_level {confidence_level}")

    weighted_annual_volatility = 0.0
    position_risks = []
    for position in portfolio["positions"]:
        ticker_risk = get_ticker_risk(position["ticker"])
        weighted_volatility = float(position["portfolio_weight"]) * float(ticker_risk["annual_volatility"])
        weighted_annual_volatility += weighted_volatility
        position_risks.append({
            "ticker": position["ticker"],
            "portfolio_weight": position["portfolio_weight"],
            "annual_volatility": ticker_risk["annual_volatility"],
            "weighted_annual_volatility": round(weighted_volatility, 6),
        })

    trading_days = int(risk_model["trading_days_per_year"])
    daily_volatility = weighted_annual_volatility / math.sqrt(trading_days)
    var_percentage = float(z_score) * daily_volatility
    var_amount = round_money(var_percentage * float(portfolio["total_market_value"]))
    result = {
        "account_id": portfolio["account_id"],
        "world_id": portfolio["world_id"],
        "as_of_date": portfolio["as_of_date"],
        "confidence_level": float(confidence_level),
        "z_score": z_score,
        "portfolio_market_value": portfolio["total_market_value"],
        "weighted_annual_volatility": round(weighted_annual_volatility, 6),
        "daily_volatility": round(daily_volatility, 6),
        "var_percentage": round(var_percentage, 6),
        "var_amount": var_amount,
        "position_risks": position_risks,
    }
    _attach_data_sources(result, portfolio)
    return result


def run_stress_scenario(
        account_id: str,
        scenario_name: str,
        as_of_date: str | None = None
) -> dict[str, Any]:
    """Apply deterministic sector shocks to current account holdings."""
    portfolio = get_portfolio_state(account_id=account_id, as_of_date=as_of_date)
    scenario = get_stress_scenario(scenario_name)
    sector_shocks = scenario.get("sector_shocks", {})
    cash_shock = float(scenario.get("cash_shock", 0.0))
    position_impacts = []
    total_position_loss = 0.0

    for position in portfolio["positions"]:
        market_value = float(position["market_value"])
        shock = float(sector_shocks.get(position["sector"], 0.0))
        stressed_market_value = market_value * (1.0 + shock)
        loss_amount = market_value - stressed_market_value
        total_position_loss += loss_amount
        position_impacts.append({
            "ticker": position["ticker"],
            "sector": position["sector"],
            "shock": shock,
            "market_value": round_money(market_value),
            "stressed_market_value": round_money(stressed_market_value),
            "loss_amount": round_money(loss_amount),
        })

    cash = float(portfolio["cash"])
    stressed_cash = cash * (1.0 + cash_shock)
    cash_loss = cash - stressed_cash
    stress_loss = round_money(total_position_loss + cash_loss)
    stressed_market_value = round_money(float(portfolio["total_market_value"]) - stress_loss)
    loss_percentage = stress_loss / float(portfolio["total_market_value"])
    result = {
        "account_id": portfolio["account_id"],
        "world_id": portfolio["world_id"],
        "as_of_date": portfolio["as_of_date"],
        "scenario_name": scenario["scenario_name"],
        "description": scenario["description"],
        "portfolio_market_value": portfolio["total_market_value"],
        "stress_loss": stress_loss,
        "loss_percentage": round(loss_percentage, 6),
        "stressed_market_value": stressed_market_value,
        "position_impacts": position_impacts,
    }
    _attach_data_sources(result, portfolio)
    return result


def get_factor_exposure(account_id: str, as_of_date: str | None = None) -> dict[str, Any]:
    """Calculate portfolio factor exposures from deterministic ticker factors."""
    portfolio = get_portfolio_state(account_id=account_id, as_of_date=as_of_date)
    factor_totals: dict[str, float] = {}
    position_factors = []
    for position in portfolio["positions"]:
        ticker_risk = get_ticker_risk(position["ticker"])
        factors = ticker_risk.get("factors", {})
        for factor_name, factor_value in factors.items():
            weighted_factor = float(position["portfolio_weight"]) * float(factor_value)
            factor_totals[factor_name] = factor_totals.get(factor_name, 0.0) + weighted_factor
        position_factors.append({
            "ticker": position["ticker"],
            "portfolio_weight": position["portfolio_weight"],
            "factors": copy.deepcopy(factors),
        })

    factor_exposures = {
        factor_name: round(factor_value, 6)
        for factor_name, factor_value in sorted(factor_totals.items())
    }
    result = {
        "account_id": portfolio["account_id"],
        "world_id": portfolio["world_id"],
        "as_of_date": portfolio["as_of_date"],
        "factor_exposures": factor_exposures,
        "market_beta": factor_exposures.get("market_beta", 0.0),
        "position_factors": position_factors,
    }
    _attach_data_sources(result, portfolio)
    return result


def check_concentration_risk(account_id: str, as_of_date: str | None = None) -> dict[str, Any]:
    """Evaluate concentration using account state and live market values."""
    portfolio = get_portfolio_state(account_id=account_id, as_of_date=as_of_date)
    single_name_limit = DEFAULT_SINGLE_NAME_LIMIT
    sector_totals: dict[str, float] = {}
    single_name_breaches = []

    for position in portfolio["positions"]:
        market_value = float(position["market_value"])
        portfolio_weight = float(position["portfolio_weight"])
        sector_totals[position["sector"]] = sector_totals.get(position["sector"], 0.0) + market_value
        if portfolio_weight > single_name_limit:
            single_name_breaches.append({
                "ticker": position["ticker"],
                "portfolio_weight": position["portfolio_weight"],
                "limit": single_name_limit,
            })

    sector_breaches = []
    for sector, market_value in sorted(sector_totals.items()):
        sector_weight = market_value / float(portfolio["total_market_value"])
        if sector_weight > DEFAULT_SECTOR_CONCENTRATION_LIMIT:
            sector_breaches.append({
                "sector": sector,
                "portfolio_weight": round(sector_weight, 6),
                "limit": DEFAULT_SECTOR_CONCENTRATION_LIMIT,
            })

    result = {
        "account_id": portfolio["account_id"],
        "world_id": portfolio["world_id"],
        "as_of_date": portfolio["as_of_date"],
        "single_name_limit": single_name_limit,
        "sector_limit": DEFAULT_SECTOR_CONCENTRATION_LIMIT,
        "single_name_breaches": single_name_breaches,
        "sector_breaches": sector_breaches,
        "breached": bool(single_name_breaches or sector_breaches),
    }
    _attach_data_sources(result, portfolio)
    return result


def get_order_impact(
        account_id: str,
        ticker: str,
        side: str,
        quantity: float,
        as_of_date: str | None = None,
        limit_price: float = 0.0
) -> dict[str, Any]:
    """Estimate deterministic account impact for an unsubmitted order."""
    account_id = normalize_account_id(account_id)
    ticker = normalize_ticker(ticker)
    side = normalize_order_side(side)
    quantity = normalize_quantity(quantity)
    portfolio = get_portfolio_state(account_id=account_id, as_of_date=as_of_date)
    price_record = get_market_price(ticker=ticker, as_of_date=as_of_date)
    price_currency = price_record.get("currency", portfolio["base_currency"])
    if price_currency != portfolio["base_currency"]:
        raise FinanceDataError(
            f"Currency mismatch for order {ticker}: "
            f"portfolio base_currency={portfolio['base_currency']}, price currency={price_currency}"
        )
    limit_price = float(limit_price or 0.0)
    estimated_price = limit_price if limit_price > 0 else float(price_record["close"])
    estimated_notional = round_money(quantity * estimated_price)

    current_position_value = 0.0
    for position in portfolio["positions"]:
        if position["ticker"] == ticker:
            current_position_value = float(position["market_value"])
            break

    signed_notional = estimated_notional if side == BUY_SIDE else -estimated_notional
    projected_position_value = current_position_value + signed_notional
    projected_cash = float(portfolio["cash"]) - signed_notional
    projected_weight = projected_position_value / float(portfolio["total_market_value"])
    current_weight = current_position_value / float(portfolio["total_market_value"])
    result = {
        "account_id": account_id,
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "estimated_price": round_money(estimated_price),
        "estimated_notional": estimated_notional,
        "price_date": price_record["date"],
        "current_position_value": round_money(current_position_value),
        "projected_position_value": round_money(projected_position_value),
        "current_weight": round(current_weight, 6),
        "projected_weight": round(projected_weight, 6),
        "cash_before_order": portfolio["cash"],
        "projected_cash": round_money(projected_cash),
        "portfolio_market_value": portfolio["total_market_value"],
        "world_id": portfolio["world_id"],
        "as_of_date": portfolio["as_of_date"],
    }
    _attach_data_sources(result, portfolio, price_record)
    return result


def screen_restricted_security(account_id: str, ticker: str) -> dict[str, Any]:
    """Screen a ticker against deterministic restricted-security rules."""
    account = get_account(account_id)
    ticker = normalize_ticker(ticker)
    restricted_security = get_restricted_security(ticker)
    if not restricted_security:
        return {
            "account_id": account["account_id"],
            "ticker": ticker,
            "world_id": account["world_id"],
            "restricted": False,
            "allowed": True,
            "policy_code": "",
            "reason": "",
            "allowed_sides": [BUY_SIDE, SELL_SIDE],
        }
    return {
        "account_id": account["account_id"],
        "ticker": ticker,
        "world_id": restricted_security["world_id"],
        "restricted": True,
        "allowed": False,
        "policy_code": restricted_security["policy_code"],
        "reason": restricted_security["reason"],
        "allowed_sides": restricted_security.get("allowed_sides", []),
    }


def check_product_distribution(account_id: str, ticker: str) -> dict[str, Any]:
    """Check task-local distribution constraints for an account and ticker."""
    account = get_account(account_id)
    client = get_client_profile(account["client_id"])
    rules = get_compliance_rules()
    ticker = normalize_ticker(ticker)
    instrument_rules = rules.get("instruments", {}).get(ticker, {})
    product_type = normalize_product_type(instrument_rules.get("product_type", "equity"))
    violations = []
    warnings = []

    approved_product_types = rules.get("client_approved_product_types", {}).get(client["client_id"], [])
    restricted_product_types = rules.get("client_restricted_product_types", {}).get(client["client_id"], [])
    if product_type in restricted_product_types:
        violations.append(_policy_issue(
            "CLIENT_PRODUCT_RESTRICTED",
            BLOCK_SEVERITY,
            f"{product_type} is restricted for client {client['client_id']}.",
            product_type=product_type,
        ))
    if approved_product_types and product_type not in approved_product_types:
        violations.append(_policy_issue(
            "PRODUCT_NOT_APPROVED_FOR_CLIENT",
            BLOCK_SEVERITY,
            f"{product_type} is not approved for client {client['client_id']}.",
            product_type=product_type,
        ))

    eligible_account_types = instrument_rules.get("eligible_account_types", [])
    if eligible_account_types and account.get("account_type") not in eligible_account_types:
        violations.append(_policy_issue(
            "ACCOUNT_TYPE_NOT_ELIGIBLE",
            BLOCK_SEVERITY,
            f"{ticker} is not eligible for {account.get('account_type')} accounts.",
            account_type=account.get("account_type"),
        ))

    distribution_status = instrument_rules.get("distribution_status", "eligible")
    restricted_security = get_restricted_security(ticker)
    if distribution_status == "restricted":
        policy_code = restricted_security["policy_code"] if restricted_security else "PRODUCT_DISTRIBUTION_RESTRICTED"
        message = restricted_security["reason"] if restricted_security else "Product distribution is restricted."
        violations.append(_policy_issue(policy_code, BLOCK_SEVERITY, message))
    elif distribution_status == "supervisory_review_required":
        warnings.append(_policy_issue(
            "SUPERVISORY_REVIEW_REQUIRED",
            REVIEW_SEVERITY,
            "Product distribution requires supervisory review.",
            required_approval=instrument_rules.get("required_approval", ""),
        ))
    elif distribution_status == "professional_or_accredited_only":
        if not client.get("professional_client") and not client.get("accredited_investor"):
            violations.append(_policy_issue(
                "COMPLEX_PRODUCT_CLIENT_INELIGIBLE",
                BLOCK_SEVERITY,
                "Product is limited to professional or accredited clients.",
                distribution_status=distribution_status,
            ))

    minimum_risk_profile = instrument_rules.get("suitability_minimum_risk_profile")
    if minimum_risk_profile and _risk_rank(rules, account["risk_profile"]) < _risk_rank(rules, minimum_risk_profile):
        violations.append(_policy_issue(
            "PRODUCT_RISK_EXCEEDS_PROFILE",
            BLOCK_SEVERITY,
            f"{ticker} requires at least a {minimum_risk_profile} risk profile.",
            account_risk_profile=account["risk_profile"],
            minimum_risk_profile=minimum_risk_profile,
        ))

    return {
        "account_id": account["account_id"],
        "client_id": client["client_id"],
        "world_id": rules["world_id"],
        "ticker": ticker,
        "product_type": product_type,
        "distribution_status": distribution_status,
        "allowed": not violations,
        "requires_review": bool(warnings),
        "violations": violations,
        "warnings": warnings,
        "required_disclosures": sorted(set(client.get("required_disclosures", []))),
    }


def check_account_suitability(
        account_id: str,
        product_type: str,
        risk_level: str | None = None
) -> dict[str, Any]:
    """Check deterministic product suitability for an account."""
    account = get_account(account_id)
    client = get_client_profile(account["client_id"])
    product_type = normalize_product_type(product_type)
    rules = get_compliance_rules()
    product_risk_level = risk_level.strip().lower() if risk_level else rules.get("product_risk_levels", {}).get(product_type)
    if not product_risk_level:
        raise ValueError(f"No product risk level found for product_type {product_type}")

    suitability = rules["suitability"].get(account["risk_profile"])
    if not suitability:
        raise ValueError(f"No suitability rule found for risk profile {account['risk_profile']}")

    risk_rank = rules["risk_level_rank"]
    allowed_products = suitability.get("allowed_product_types", [])
    max_risk_level = suitability["max_product_risk_level"]
    violations = []
    restricted_product_types = rules.get("client_restricted_product_types", {}).get(client["client_id"], [])
    approved_product_types = rules.get("client_approved_product_types", {}).get(client["client_id"], [])
    if product_type in restricted_product_types:
        violations.append({
            "policy_code": "CLIENT_PRODUCT_RESTRICTED",
            "severity": BLOCK_SEVERITY,
            "message": f"{product_type} is restricted for client {client['client_id']}.",
        })
    if approved_product_types and product_type not in approved_product_types:
        violations.append({
            "policy_code": "PRODUCT_NOT_APPROVED_FOR_CLIENT",
            "severity": BLOCK_SEVERITY,
            "message": f"{product_type} is not approved for client {client['client_id']}.",
        })
    if product_type not in allowed_products:
        violations.append({
            "policy_code": "PRODUCT_NOT_ALLOWED_FOR_PROFILE",
            "severity": BLOCK_SEVERITY,
            "message": f"{product_type} is not allowed for {account['risk_profile']} accounts.",
        })
    if risk_rank[product_risk_level] > risk_rank[max_risk_level]:
        violations.append({
            "policy_code": "PRODUCT_RISK_EXCEEDS_PROFILE",
            "severity": BLOCK_SEVERITY,
            "message": f"{product_risk_level} risk exceeds the {max_risk_level} account limit.",
        })

    return {
        "account_id": account["account_id"],
        "world_id": rules["world_id"],
        "client_id": client["client_id"],
        "product_type": product_type,
        "account_risk_profile": account["risk_profile"],
        "product_risk_level": product_risk_level,
        "max_product_risk_level": max_risk_level,
        "suitable": not violations,
        "violations": violations,
    }


def check_order_restrictions(
        account_id: str,
        ticker: str,
        side: str,
        quantity: float,
        order_type: str = DEFAULT_ORDER_TYPE,
        as_of_date: str | None = None
) -> dict[str, Any]:
    """Check deterministic order restrictions without submitting an order."""
    account = get_account(account_id)
    side = normalize_order_side(side)
    order_type = (order_type or DEFAULT_ORDER_TYPE).strip().lower()
    impact = get_order_impact(
        account_id=account["account_id"],
        ticker=ticker,
        side=side,
        quantity=quantity,
        as_of_date=as_of_date,
    )
    distribution = check_product_distribution(account["account_id"], impact["ticker"])
    product_type = normalize_product_type(distribution["product_type"])
    rules = get_compliance_rules()
    violations = []
    warnings = []

    restricted_security = get_restricted_security(impact["ticker"])
    if restricted_security and side not in restricted_security.get("allowed_sides", []):
        violations.append({
            "policy_code": restricted_security["policy_code"],
            "severity": "block",
            "message": restricted_security["reason"],
        })

    for issue in distribution["violations"]:
        _append_unique_issue(violations, issue)
    for issue in distribution["warnings"]:
        _append_unique_issue(warnings, issue)

    if side == BUY_SIDE and impact["projected_cash"] < -MONEY_TOLERANCE:
        violations.append({
            "policy_code": "INSUFFICIENT_CASH",
            "severity": BLOCK_SEVERITY,
            "message": "Projected cash would be negative after the order.",
        })

    for restriction_code in account.get("restrictions", []):
        rule = rules["account_restriction_rules"].get(restriction_code)
        if not rule:
            continue
        if product_type in rule.get("product_types", []):
            target = warnings if rule["severity"] == "review" else violations
            target.append({
                "policy_code": rule["policy_code"],
                "severity": rule["severity"],
                "message": rule["message"],
            })
        if side in rule.get("applies_to_sides", []) and "max_weight" in rule:
            if impact["projected_weight"] > float(rule["max_weight"]):
                violations.append({
                    "policy_code": rule["policy_code"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "limit": rule["max_weight"],
                    "current_weight": impact["current_weight"],
                    "projected_weight": impact["projected_weight"],
                })

    return {
        "account_id": account["account_id"],
        "world_id": rules["world_id"],
        "ticker": impact["ticker"],
        "side": side,
        "quantity": impact["quantity"],
        "order_type": order_type,
        "product_type": product_type,
        "estimated_price": impact["estimated_price"],
        "estimated_notional": impact["estimated_notional"],
        "current_weight": impact["current_weight"],
        "projected_weight": impact["projected_weight"],
        "projected_cash": impact["projected_cash"],
        "distribution_allowed": distribution["allowed"],
        "allowed": not violations,
        "requires_review": bool(warnings),
        "violations": violations,
        "warnings": warnings,
        "blocking_policy_codes": [
            issue["policy_code"] for issue in violations if issue.get("severity") == BLOCK_SEVERITY
        ],
        "required_disclosures": distribution["required_disclosures"],
    }


def check_research_distribution(account_id: str, report_id: str) -> dict[str, Any]:
    """Check whether a research report may be used for client-facing advice."""
    account = get_account(account_id)
    client = get_client_profile(account["client_id"])
    report = get_research_report(report_id, include_untrusted_excerpt=True)
    violations = []
    warnings = []

    if report.get("publication_status") != "approved" or not report.get("allowed_for_client_distribution"):
        violations.append(_policy_issue(
            "DRAFT_RESEARCH_NOT_DISTRIBUTABLE",
            BLOCK_SEVERITY,
            "Draft or unapproved research cannot be used for client-facing advice.",
            publication_status=report.get("publication_status", ""),
            source_trust_level=report.get("source_trust_level", ""),
        ))
    conflict_required = (
        "banking_conflict_disclosure" in report.get("required_disclosures", [])
        or any("investment banking" in disclosure.lower() for disclosure in report.get("conflict_disclosures", []))
        or any("lending services" in disclosure.lower() for disclosure in report.get("conflict_disclosures", []))
    )
    if conflict_required:
        warnings.append(_policy_issue(
            "RESEARCH_CONFLICT_DISCLOSURE_REQUIRED",
            REVIEW_SEVERITY,
            "Research contains conflict disclosures that must be presented.",
        ))

    return {
        "account_id": account["account_id"],
        "client_id": client["client_id"],
        "world_id": report["world_id"],
        "report_id": report["report_id"],
        "ticker": report["ticker"],
        "publication_status": report["publication_status"],
        "source_trust_level": report["source_trust_level"],
        "allowed": not violations,
        "requires_review": bool(warnings),
        "untrusted_source_present": bool(report.get("untrusted_source_excerpt")),
        "violations": violations,
        "warnings": warnings,
        "required_disclosures": sorted(set(client.get("required_disclosures", []) + report.get("required_disclosures", []))),
    }


def run_pre_trade_risk_check(
        account_id: str,
        ticker: str,
        side: str,
        quantity: float,
        as_of_date: str | None = None,
        limit_price: float = 0.0
) -> dict[str, Any]:
    """Run deterministic pre-trade risk checks for an unsubmitted order."""
    impact = get_order_impact(
        account_id=account_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        as_of_date=as_of_date,
        limit_price=limit_price,
    )
    concentration = check_concentration_risk(account_id=impact["account_id"], as_of_date=as_of_date)
    warnings = []
    violations = []

    if impact["projected_weight"] > concentration["single_name_limit"]:
        violations.append(_policy_issue(
            "NO_SINGLE_NAME_GT_25",
            BLOCK_SEVERITY,
            "Projected single-name concentration exceeds the account limit.",
            projected_weight=impact["projected_weight"],
            limit=concentration["single_name_limit"],
        ))
    result = {
        "account_id": impact["account_id"],
        "world_id": impact["world_id"],
        "as_of_date": impact["as_of_date"],
        "ticker": impact["ticker"],
        "side": impact["side"],
        "quantity": impact["quantity"],
        "projected_weight": impact["projected_weight"],
        "risk_acceptable": not violations,
        "violations": violations,
        "warnings": warnings,
        "blocking_policy_codes": [
            issue["policy_code"] for issue in violations if issue.get("severity") == BLOCK_SEVERITY
        ],
        "concentration": concentration,
    }
    _attach_data_sources(result, impact, concentration)
    return result


def preview_order_impact(
        account_id: str,
        ticker: str,
        side: str,
        quantity: float,
        as_of_date: str | None = None
) -> dict[str, Any]:
    """Preview order impact and compliance status without creating a draft."""
    impact = get_order_impact(
        account_id=account_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        as_of_date=as_of_date,
    )
    compliance = check_order_restrictions(
        account_id=account_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        as_of_date=as_of_date,
    )
    result = copy.deepcopy(impact)
    result["compliance_allowed"] = compliance["allowed"]
    result["violation_count"] = len(compliance["violations"])
    result["violations"] = compliance["violations"]
    result["blocking_policy_codes"] = compliance["blocking_policy_codes"]
    return result


def create_order_draft(
        account_id: str,
        ticker: str,
        side: str,
        quantity: float,
        order_type: str = DEFAULT_ORDER_TYPE,
        limit_price: float = 0.0,
        as_of_date: str | None = None,
        rationale: str = ""
) -> dict[str, Any]:
    """Create a deterministic unsubmitted order draft."""
    impact = get_order_impact(
        account_id=account_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        as_of_date=as_of_date,
        limit_price=limit_price,
    )
    compliance = check_order_restrictions(
        account_id=account_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        order_type=order_type,
        as_of_date=as_of_date,
    )
    risk = run_pre_trade_risk_check(
        account_id=account_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        as_of_date=as_of_date,
        limit_price=limit_price,
    )
    research_summary = _research_summary_for_ticker(impact["ticker"])
    normalized_date = normalize_optional_date(as_of_date) or get_active_world_date()
    quantity_token = str(int(impact["quantity"])) if impact["quantity"].is_integer() else str(impact["quantity"])
    draft_id = (
        f"DRAFT-{impact['account_id']}-{impact['ticker']}-{impact['side']}-"
        f"{quantity_token}-{normalized_date.replace('-', '')}"
    )
    result = {
        "draft_id": draft_id,
        "account_id": impact["account_id"],
        "world_id": impact["world_id"],
        "as_of_date": impact["as_of_date"],
        "ticker": impact["ticker"],
        "side": impact["side"],
        "quantity": impact["quantity"],
        "order_type": (order_type or DEFAULT_ORDER_TYPE).strip().lower(),
        "limit_price": float(limit_price or 0.0),
        "estimated_price": impact["estimated_price"],
        "estimated_notional": impact["estimated_notional"],
        "execution_status": "not_submitted",
        "rationale": rationale,
        "impact": impact,
        "compliance_summary": {
            "allowed": compliance["allowed"],
            "requires_review": compliance["requires_review"],
            "violation_count": len(compliance["violations"]),
            "violations": compliance["violations"],
            "warnings": compliance["warnings"],
        },
        "pre_trade_checks": {
            "compliance": compliance,
            "risk": risk,
            "research": research_summary,
        },
        "blocking_policy_codes": sorted(set(compliance["blocking_policy_codes"] + risk["blocking_policy_codes"])),
        "required_disclosures": compliance["required_disclosures"],
        "research_warnings": research_summary["warnings"],
    }
    _attach_data_sources(result, impact, risk)
    return result


def explain_decision_context(account_id: str, ticker: str = "", policy_code: str = "") -> dict[str, Any]:
    """Explain the deterministic evidence chain for a policy decision."""
    context = get_account_client_context(account_id)
    normalized_policy_code = policy_code.strip().upper() if policy_code else ""
    normalized_ticker = normalize_ticker(ticker) if ticker else ""
    policy_reference = get_policy_reference(normalized_policy_code) if normalized_policy_code else {}
    matching_events = []
    for event in list_audit_events(account_id=context["account_id"], limit=50)["events"]:
        if normalized_policy_code and normalized_policy_code not in event.get("policy_codes", []):
            continue
        if normalized_ticker and normalized_ticker not in [normalize_ticker(item) for item in event.get("related_tickers", [])]:
            continue
        matching_events.append(event)

    evidence_chain = [
        {
            "source": "account_profile",
            "summary": f"Account {context['account_id']} has risk profile {context['risk_profile']}.",
        },
        {
            "source": "client_profile",
            "summary": f"Client {context['client_id']} has product approvals {context['approved_product_types']}.",
        },
    ]
    if policy_reference:
        evidence_chain.append({
            "source": "policy_reference",
            "summary": policy_reference["description"],
        })

    return {
        "account_id": context["account_id"],
        "client_id": context["client_id"],
        "ticker": normalized_ticker,
        "policy_code": normalized_policy_code,
        "policy_reference": policy_reference,
        "matching_audit_events": matching_events,
        "evidence_chain": evidence_chain,
        "decision_basis": "task_policy_contract_and_business_state",
    }


def _research_summary_for_ticker(ticker: str) -> dict[str, Any]:
    normalized_ticker = normalize_ticker(ticker)
    if is_live_data_mode() and not has_task_material():
        return {
            "ticker": normalized_ticker,
            "approved_report_ids": [],
            "warnings": [],
            "source": "task_material_not_configured",
        }
    reports = search_research_reports(ticker=ticker, include_untrusted_excerpt=False)["reports"]
    warnings = []
    approved_report_ids = []
    for report in reports:
        if report.get("publication_status") == "approved" and report.get("allowed_for_client_distribution"):
            approved_report_ids.append(report["report_id"])
            continue
        warnings.append(_policy_issue(
            "DRAFT_RESEARCH_NOT_DISTRIBUTABLE",
            BLOCK_SEVERITY,
            f"Research report {report['report_id']} is not approved for client-facing use.",
            report_id=report["report_id"],
        ))
    return {
        "ticker": normalized_ticker,
        "approved_report_ids": approved_report_ids,
        "warnings": warnings,
    }
