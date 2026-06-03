"""Read-only synthetic enterprise data for financial-services MCP workflows."""
import copy
from typing import Any

from .data_loader import get_client_profile, load_business_state_path, load_task_material
from .errors import FinanceDataError, FinanceRecordNotFoundError
from .schema import (
    TRUSTED_INTERNAL_SYSTEM,
    collect_evidence,
    make_business_evidence_record,
    make_world_data_source,
    make_world_evidence_record,
)


def search_clients(query: str = "", segment: str = "", advisor_id: str = "") -> dict[str, Any]:
    """Search CRM client records."""
    crm = _load_enterprise_payload("crm/crm_records.json")
    normalized_query = query.strip().lower()
    normalized_segment = segment.strip().lower()
    normalized_advisor_id = advisor_id.strip().upper()
    records = []
    for client in crm.get("clients", []):
        if normalized_segment and client.get("segment", "").lower() != normalized_segment:
            continue
        if normalized_advisor_id and client.get("advisor_id", "").upper() != normalized_advisor_id:
            continue
        if normalized_query and normalized_query not in _record_text(client):
            continue
        records.append(copy.deepcopy(client))
    return {"world_id": crm["world_id"], "clients": records}


def get_client_record(client_id: str) -> dict[str, Any]:
    """Return a CRM client record joined to the core client profile."""
    normalized_client_id = _required_identifier(client_id, "client_id")
    crm = _load_enterprise_payload("crm/crm_records.json")
    for client in crm.get("clients", []):
        if client["client_id"].upper() == normalized_client_id:
            result = copy.deepcopy(client)
            result["world_id"] = crm["world_id"]
            result["client_profile"] = get_client_profile(client_id)
            result["evidence"] = _internal_evidence(crm["world_id"], "crm_client", client["client_id"])
            return result
    raise FinanceRecordNotFoundError(f"No CRM client record found for client_id {normalized_client_id}")


def list_client_interactions(client_id: str, start_date: str = "", end_date: str = "") -> dict[str, Any]:
    """List CRM interactions for a client."""
    normalized_client_id = _required_identifier(client_id, "client_id")
    crm = _load_enterprise_payload("crm/crm_records.json")
    records = [
        copy.deepcopy(record)
        for record in crm.get("interactions", [])
        if record.get("client_id", "").upper() == normalized_client_id
        and _date_in_range(record.get("date", ""), start_date, end_date)
    ]
    return {"world_id": crm["world_id"], "client_id": normalized_client_id, "interactions": records}


def list_meetings(client_id: str = "", start_date: str = "", end_date: str = "") -> dict[str, Any]:
    """List CRM meetings."""
    normalized_client_id = client_id.strip().upper()
    crm = _load_enterprise_payload("crm/crm_records.json")
    records = [
        copy.deepcopy(record)
        for record in crm.get("meetings", [])
        if (not normalized_client_id or record.get("client_id", "").upper() == normalized_client_id)
        and _date_in_range(record.get("date", ""), start_date, end_date)
    ]
    return {"world_id": crm["world_id"], "meetings": records}


def get_meeting_context(meeting_id: str) -> dict[str, Any]:
    """Return one CRM meeting context record."""
    normalized_meeting_id = _required_identifier(meeting_id, "meeting_id")
    crm = _load_enterprise_payload("crm/crm_records.json")
    for meeting in crm.get("meetings", []):
        if meeting["meeting_id"].upper() == normalized_meeting_id:
            result = copy.deepcopy(meeting)
            result["world_id"] = crm["world_id"]
            result["client_record"] = get_client_record(meeting["client_id"])
            result["evidence"] = _internal_evidence(crm["world_id"], "crm_meeting", meeting["meeting_id"])
            return result
    raise FinanceRecordNotFoundError(f"No meeting found for meeting_id {normalized_meeting_id}")


def list_follow_ups(client_id: str = "", status: str = "") -> dict[str, Any]:
    """List CRM follow-up records."""
    normalized_client_id = client_id.strip().upper()
    normalized_status = status.strip().lower()
    crm = _load_enterprise_payload("crm/crm_records.json")
    records = [
        copy.deepcopy(record)
        for record in crm.get("follow_ups", [])
        if (not normalized_client_id or record.get("client_id", "").upper() == normalized_client_id)
        and (not normalized_status or record.get("status", "").lower() == normalized_status)
    ]
    return {"world_id": crm["world_id"], "follow_ups": records}


def get_onboarding_packet(packet_id: str) -> dict[str, Any]:
    """Return one KYC onboarding packet."""
    normalized_packet_id = _required_identifier(packet_id, "packet_id")
    kyc = _load_enterprise_payload("kyc/kyc_records.json")
    for packet in kyc.get("onboarding_packets", []):
        if packet["packet_id"].upper() == normalized_packet_id:
            result = copy.deepcopy(packet)
            result["world_id"] = kyc["world_id"]
            result["evidence"] = _internal_evidence(kyc["world_id"], "kyc_packet", packet["packet_id"])
            return result
    raise FinanceRecordNotFoundError(f"No onboarding packet found for packet_id {normalized_packet_id}")


def screen_sanctions_pep(client_id: str) -> dict[str, Any]:
    """Return read-only sanctions and PEP screening status."""
    normalized_client_id = _required_identifier(client_id, "client_id")
    kyc = _load_enterprise_payload("kyc/kyc_records.json")
    for screening in kyc.get("screening_records", []):
        if screening["client_id"].upper() == normalized_client_id:
            result = copy.deepcopy(screening)
            result["world_id"] = kyc["world_id"]
            result["evidence"] = _internal_evidence(kyc["world_id"], "screening_record", screening["screening_id"])
            return result
    profile = get_client_profile(client_id)
    return {
        "world_id": profile["world_id"],
        "client_id": profile["client_id"],
        "sanctions_status": profile.get("sanctions_status", ""),
        "pep_status": profile.get("pep_status", False),
        "risk_flags": [],
        "evidence": _internal_evidence(profile["world_id"], "client_profile", profile["client_id"]),
    }


def evaluate_kyc_rules(packet_id: str) -> dict[str, Any]:
    """Evaluate task-local KYC rules against a synthetic onboarding packet."""
    packet = get_onboarding_packet(packet_id)
    rules = _task_rules("kyc_rules")
    required_fields = rules.get("required_fields", [])
    required_documents = rules.get("required_documents", [])
    fields = packet.get("fields", {})
    documents = {item.get("document_type") for item in packet.get("document_inventory", [])}
    missing_fields = [field for field in required_fields if not fields.get(field)]
    missing_documents = [document for document in required_documents if document not in documents]
    screening = screen_sanctions_pep(packet["client_id"])
    escalation_required = bool(missing_fields or missing_documents or screening.get("risk_flags"))
    return {
        "world_id": packet["world_id"],
        "packet_id": packet["packet_id"],
        "client_id": packet["client_id"],
        "rule_set_id": rules.get("rule_set_id", "task_kyc_rules"),
        "status": "escalate" if escalation_required else "pass",
        "missing_fields": missing_fields,
        "missing_documents": missing_documents,
        "screening_risk_flags": screening.get("risk_flags", []),
        "evidence": collect_evidence(packet, screening),
    }


def list_kyc_gaps(packet_id: str) -> dict[str, Any]:
    """List KYC gaps produced by task-local rules."""
    evaluation = evaluate_kyc_rules(packet_id)
    return {
        "world_id": evaluation["world_id"],
        "packet_id": evaluation["packet_id"],
        "gaps": {
            "missing_fields": evaluation["missing_fields"],
            "missing_documents": evaluation["missing_documents"],
            "screening_risk_flags": evaluation["screening_risk_flags"],
        },
        "evidence": evaluation["evidence"],
    }


def get_escalation_recommendation(packet_id: str) -> dict[str, Any]:
    """Return a KYC escalation recommendation without making a final decision."""
    evaluation = evaluate_kyc_rules(packet_id)
    recommendation = "escalate_to_compliance_officer" if evaluation["status"] == "escalate" else "no_escalation_needed"
    return {
        "world_id": evaluation["world_id"],
        "packet_id": evaluation["packet_id"],
        "client_id": evaluation["client_id"],
        "recommendation": recommendation,
        "final_decision": "human_required",
        "reason_codes": (
            evaluation["missing_fields"]
            + evaluation["missing_documents"]
            + evaluation["screening_risk_flags"]
        ),
        "evidence": evaluation["evidence"],
    }


def get_trial_balance(entity_id: str, period: str) -> dict[str, Any]:
    """Return one trial balance."""
    ledger = _load_enterprise_payload("ledger/ledger_records.json")
    for record in ledger.get("trial_balances", []):
        if record.get("entity_id") == entity_id and record.get("period") == period:
            result = copy.deepcopy(record)
            result["world_id"] = ledger["world_id"]
            result["evidence"] = _internal_evidence(ledger["world_id"], "trial_balance", f"{entity_id}:{period}")
            return result
    raise FinanceRecordNotFoundError(f"No trial balance found for entity_id {entity_id} period {period}")


def list_gl_transactions(entity_id: str = "", account_code: str = "", period: str = "") -> dict[str, Any]:
    """List GL transactions."""
    ledger = _load_enterprise_payload("ledger/ledger_records.json")
    records = [
        copy.deepcopy(record)
        for record in ledger.get("gl_transactions", [])
        if (not entity_id or record.get("entity_id") == entity_id)
        and (not account_code or record.get("account_code") == account_code)
        and (not period or record.get("period") == period)
    ]
    return {"world_id": ledger["world_id"], "transactions": records}


def get_journal_entry(journal_entry_id: str) -> dict[str, Any]:
    """Return one journal entry."""
    normalized_journal_entry_id = _required_identifier(journal_entry_id, "journal_entry_id")
    ledger = _load_enterprise_payload("ledger/ledger_records.json")
    for entry in ledger.get("journal_entries", []):
        if entry["journal_entry_id"].upper() == normalized_journal_entry_id:
            result = copy.deepcopy(entry)
            result["world_id"] = ledger["world_id"]
            result["evidence"] = _internal_evidence(ledger["world_id"], "journal_entry", entry["journal_entry_id"])
            return result
    raise FinanceRecordNotFoundError(f"No journal entry found for journal_entry_id {normalized_journal_entry_id}")


def list_accrual_candidates(entity_id: str = "", period: str = "") -> dict[str, Any]:
    """List accrual candidates staged for review."""
    ledger = _load_enterprise_payload("ledger/ledger_records.json")
    records = [
        copy.deepcopy(record)
        for record in ledger.get("accrual_candidates", [])
        if (not entity_id or record.get("entity_id") == entity_id)
        and (not period or record.get("period") == period)
    ]
    return {"world_id": ledger["world_id"], "accrual_candidates": records}


def get_rollforward_schedule(entity_id: str, account_code: str, period: str) -> dict[str, Any]:
    """Return one roll-forward schedule."""
    ledger = _load_enterprise_payload("ledger/ledger_records.json")
    for schedule in ledger.get("rollforward_schedules", []):
        if (
                schedule.get("entity_id") == entity_id
                and schedule.get("account_code") == account_code
                and schedule.get("period") == period
        ):
            result = copy.deepcopy(schedule)
            result["world_id"] = ledger["world_id"]
            result["evidence"] = _internal_evidence(
                ledger["world_id"],
                "rollforward_schedule",
                f"{entity_id}:{account_code}:{period}",
            )
            return result
    raise FinanceRecordNotFoundError(
        f"No rollforward schedule found for entity_id {entity_id}, account_code {account_code}, period {period}"
    )


def get_budget_vs_actuals(entity_id: str, period: str) -> dict[str, Any]:
    """Return budget-vs-actual records for an entity and period."""
    ledger = _load_enterprise_payload("ledger/ledger_records.json")
    records = [
        copy.deepcopy(record)
        for record in ledger.get("budget_vs_actuals", [])
        if record.get("entity_id") == entity_id and record.get("period") == period
    ]
    if not records:
        raise FinanceRecordNotFoundError(f"No budget-vs-actuals found for entity_id {entity_id} period {period}")
    return _source_result({
        "world_id": ledger["world_id"],
        "entity_id": entity_id,
        "period": period,
        "lines": records,
    }, ledger, "ledger", "budget_vs_actuals", f"{entity_id}:{period}")


def get_journal_source_breakdown(entity_id: str, period: str) -> dict[str, Any]:
    """Aggregate GL activity by journal source."""
    ledger = _load_enterprise_payload("ledger/ledger_records.json")
    transactions = [
        copy.deepcopy(record)
        for record in ledger.get("gl_transactions", [])
        if record.get("entity_id") == entity_id and record.get("period") == period
    ]
    breakdown: dict[str, dict[str, Any]] = {}
    for transaction in transactions:
        source = transaction.get("journal_source", transaction.get("source", "unspecified"))
        bucket = breakdown.setdefault(source, {"journal_source": source, "transaction_count": 0, "amount": 0.0})
        bucket["transaction_count"] += 1
        bucket["amount"] = round(float(bucket["amount"]) + float(transaction.get("amount", 0.0)), 2)
    return _source_result({
        "world_id": ledger["world_id"],
        "entity_id": entity_id,
        "period": period,
        "breakdown": list(breakdown.values()),
    }, ledger, "ledger", "journal_source_breakdown", f"{entity_id}:{period}")


def draft_adjusting_entry(
        entity_id: str,
        period: str,
        debit_account: str,
        credit_account: str,
        amount: float,
        memo: str = "",
) -> dict[str, Any]:
    """Draft, but do not post, an adjusting journal entry."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    ledger = _load_enterprise_payload("ledger/ledger_records.json")
    draft_id = f"DRAFT-JE-{entity_id}-{period}-{debit_account}-{credit_account}".replace(" ", "-")
    return _source_result({
        "world_id": ledger["world_id"],
        "draft_entry_id": draft_id,
        "entity_id": entity_id,
        "period": period,
        "status": "draft_not_posted",
        "posting_status": "not_posted",
        "memo": memo,
        "lines": [
            {"account_code": debit_account, "debit": round(float(amount), 2), "credit": 0.0},
            {"account_code": credit_account, "debit": 0.0, "credit": round(float(amount), 2)},
        ],
    }, ledger, "ledger", "draft_adjusting_entry", draft_id)


def list_subledger_positions(as_of_date: str = "", asset_class: str = "") -> dict[str, Any]:
    """List subledger positions."""
    subledger = _load_enterprise_payload("subledger/subledger_records.json")
    records = [
        copy.deepcopy(record)
        for record in subledger.get("positions", [])
        if (not as_of_date or record.get("as_of_date") == as_of_date)
        and (not asset_class or record.get("asset_class", "").lower() == asset_class.lower())
    ]
    return {"world_id": subledger["world_id"], "positions": records}


def list_subledger_transactions(trade_date: str = "", asset_class: str = "") -> dict[str, Any]:
    """List subledger transactions."""
    subledger = _load_enterprise_payload("subledger/subledger_records.json")
    records = [
        copy.deepcopy(record)
        for record in subledger.get("transactions", [])
        if (not trade_date or record.get("trade_date") == trade_date)
        and (not asset_class or record.get("asset_class", "").lower() == asset_class.lower())
    ]
    return {"world_id": subledger["world_id"], "transactions": records}


def get_trade_lifecycle(trade_id: str) -> dict[str, Any]:
    """Return one trade lifecycle."""
    normalized_trade_id = _required_identifier(trade_id, "trade_id")
    subledger = _load_enterprise_payload("subledger/subledger_records.json")
    for lifecycle in subledger.get("trade_lifecycles", []):
        if lifecycle["trade_id"].upper() == normalized_trade_id:
            result = copy.deepcopy(lifecycle)
            result["world_id"] = subledger["world_id"]
            result["evidence"] = _internal_evidence(subledger["world_id"], "trade_lifecycle", lifecycle["trade_id"])
            return result
    raise FinanceRecordNotFoundError(f"No trade lifecycle found for trade_id {normalized_trade_id}")


def compare_gl_subledger_records(entity_id: str, period: str, asset_class: str = "") -> dict[str, Any]:
    """Compare read-only GL and subledger reconciliation records."""
    subledger = _load_enterprise_payload("subledger/subledger_records.json")
    records = [
        copy.deepcopy(record)
        for record in subledger.get("reconciliation_records", [])
        if record.get("entity_id") == entity_id
        and record.get("period") == period
        and (not asset_class or record.get("asset_class", "").lower() == asset_class.lower())
    ]
    breaks = [record for record in records if abs(float(record.get("difference", 0.0))) > 0.01]
    return {
        "world_id": subledger["world_id"],
        "entity_id": entity_id,
        "period": period,
        "records": records,
        "breaks": breaks,
        "break_count": len(breaks),
        "evidence": _internal_evidence(
            subledger["world_id"],
            "gl_subledger_reconciliation",
            f"{entity_id}:{period}:{asset_class}",
        ),
    }


def trace_recon_break(break_id: str) -> dict[str, Any]:
    """Trace a reconciliation break to GL and subledger evidence."""
    normalized_break_id = _required_identifier(break_id, "break_id")
    subledger = _load_enterprise_payload("subledger/subledger_records.json")
    for record in subledger.get("break_traces", []):
        if record.get("break_id", "").upper() == normalized_break_id:
            result = copy.deepcopy(record)
            return _source_result(result, subledger, "subledger", "recon_break_trace", normalized_break_id)
    for record in subledger.get("reconciliation_records", []):
        if record.get("break_id", "").upper() == normalized_break_id:
            result = _source_result({
                "break_id": normalized_break_id,
                "root_cause": record.get("suspected_cause", "unknown"),
                "owner": record.get("owner", "ops"),
                "action": record.get("recommended_action", "raise-ticket"),
                "reconciliation_record": copy.deepcopy(record),
                "world_id": subledger["world_id"],
            }, subledger, "subledger", "recon_break_trace", normalized_break_id)
            return result
    raise FinanceRecordNotFoundError(f"No reconciliation break found for break_id {normalized_break_id}")


def get_nav_pack(fund_id: str, as_of_date: str) -> dict[str, Any]:
    """Return one NAV pack."""
    nav = _load_enterprise_payload("nav/nav_records.json")
    for pack in nav.get("nav_packs", []):
        if pack.get("fund_id") == fund_id and pack.get("as_of_date") == as_of_date:
            result = copy.deepcopy(pack)
            result["world_id"] = nav["world_id"]
            result["evidence"] = _internal_evidence(nav["world_id"], "nav_pack", f"{fund_id}:{as_of_date}")
            return result
    raise FinanceRecordNotFoundError(f"No NAV pack found for fund_id {fund_id} as_of_date {as_of_date}")


def get_lp_statement(statement_id: str) -> dict[str, Any]:
    """Return one LP statement."""
    normalized_statement_id = _required_identifier(statement_id, "statement_id")
    nav = _load_enterprise_payload("nav/nav_records.json")
    for statement in nav.get("lp_statements", []):
        if statement["statement_id"].upper() == normalized_statement_id:
            result = copy.deepcopy(statement)
            result["world_id"] = nav["world_id"]
            result["evidence"] = _internal_evidence(nav["world_id"], "lp_statement", statement["statement_id"])
            return result
    raise FinanceRecordNotFoundError(f"No LP statement found for statement_id {normalized_statement_id}")


def recompute_capital_account(statement_id: str) -> dict[str, Any]:
    """Recompute a capital account from statement components."""
    statement = get_lp_statement(statement_id)
    components = statement.get("capital_account", {})
    recomputed = (
        float(components.get("beginning_balance", 0.0))
        + float(components.get("contributions", 0.0))
        - float(components.get("distributions", 0.0))
        + float(components.get("net_gain_loss", 0.0))
        - float(components.get("fees", 0.0))
    )
    reported = float(components.get("ending_balance_reported", 0.0))
    return {
        "world_id": statement["world_id"],
        "statement_id": statement["statement_id"],
        "lp_id": statement["lp_id"],
        "recomputed_ending_balance": round(recomputed, 2),
        "reported_ending_balance": round(reported, 2),
        "difference": round(reported - recomputed, 2),
        "evidence": statement["evidence"],
    }


def list_statement_tieouts(fund_id: str = "", as_of_date: str = "") -> dict[str, Any]:
    """List LP statement tie-outs."""
    nav = _load_enterprise_payload("nav/nav_records.json")
    records = []
    for statement in nav.get("lp_statements", []):
        if fund_id and statement.get("fund_id") != fund_id:
            continue
        if as_of_date and statement.get("as_of_date") != as_of_date:
            continue
        tieout = recompute_capital_account(statement["statement_id"])
        records.append(tieout)
    return {"world_id": nav["world_id"], "tieouts": records}


def search_private_companies(query: str = "", sector: str = "", stage: str = "") -> dict[str, Any]:
    """Search private-company records."""
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    normalized_query = query.strip().lower()
    normalized_sector = sector.strip().lower()
    normalized_stage = stage.strip().lower()
    records = [
        copy.deepcopy(company)
        for company in private_markets.get("private_companies", [])
        if (not normalized_query or normalized_query in _record_text(company))
        and (not normalized_sector or company.get("sector", "").lower() == normalized_sector)
        and (not normalized_stage or company.get("stage", "").lower() == normalized_stage)
    ]
    return {"world_id": private_markets["world_id"], "companies": records}


def get_portco_profile(portco_id: str) -> dict[str, Any]:
    """Return one portfolio-company profile."""
    normalized_portco_id = _required_identifier(portco_id, "portco_id")
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    for company in private_markets.get("private_companies", []):
        if company["portco_id"].upper() == normalized_portco_id:
            result = copy.deepcopy(company)
            result["world_id"] = private_markets["world_id"]
            result["evidence"] = _internal_evidence(
                private_markets["world_id"],
                "portco_profile",
                company["portco_id"],
            )
            return result
    raise FinanceRecordNotFoundError(f"No portco profile found for portco_id {normalized_portco_id}")


def get_portco_kpis(portco_id: str, period: str = "") -> dict[str, Any]:
    """Return KPIs for one private portfolio company."""
    normalized_portco_id = _required_identifier(portco_id, "portco_id")
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    records = [
        copy.deepcopy(record)
        for record in private_markets.get("portco_kpis", [])
        if record.get("portco_id", "").upper() == normalized_portco_id
        and (not period or record.get("period") == period)
    ]
    return {"world_id": private_markets["world_id"], "portco_id": normalized_portco_id, "kpis": records}


def get_fund_portfolio(fund_id: str) -> dict[str, Any]:
    """Return one private-market fund portfolio."""
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    for portfolio in private_markets.get("fund_portfolios", []):
        if portfolio["fund_id"] == fund_id:
            result = copy.deepcopy(portfolio)
            result["world_id"] = private_markets["world_id"]
            result["evidence"] = _internal_evidence(private_markets["world_id"], "fund_portfolio", fund_id)
            return result
    raise FinanceRecordNotFoundError(f"No fund portfolio found for fund_id {fund_id}")


def get_deal_record(deal_id: str) -> dict[str, Any]:
    """Return one private-market deal record."""
    normalized_deal_id = _required_identifier(deal_id, "deal_id")
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    for deal in private_markets.get("deal_pipeline", []):
        if deal["deal_id"].upper() == normalized_deal_id:
            result = copy.deepcopy(deal)
            result["world_id"] = private_markets["world_id"]
            result["evidence"] = _internal_evidence(private_markets["world_id"], "deal_record", deal["deal_id"])
            return result
    raise FinanceRecordNotFoundError(f"No deal record found for deal_id {normalized_deal_id}")


def list_deal_pipeline(stage: str = "") -> dict[str, Any]:
    """List private-market deal pipeline records."""
    normalized_stage = stage.strip().lower()
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    records = [
        copy.deepcopy(deal)
        for deal in private_markets.get("deal_pipeline", [])
        if not normalized_stage or deal.get("stage", "").lower() == normalized_stage
    ]
    return {"world_id": private_markets["world_id"], "deals": records}


def get_valuation_package_summary(package_id: str) -> dict[str, Any]:
    """Return one GP valuation package summary."""
    normalized_package_id = _required_identifier(package_id, "package_id")
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    for package in private_markets.get("valuation_packages", []):
        if package["package_id"].upper() == normalized_package_id:
            result = copy.deepcopy(package)
            result["world_id"] = private_markets["world_id"]
            result["evidence"] = _internal_evidence(
                private_markets["world_id"],
                "valuation_package",
                package["package_id"],
            )
            return result
    raise FinanceRecordNotFoundError(f"No valuation package found for package_id {normalized_package_id}")


def get_funding_rounds(portco_id: str) -> dict[str, Any]:
    """Return funding rounds for one private company."""
    normalized_portco_id = _required_identifier(portco_id, "portco_id")
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    records = [
        copy.deepcopy(record)
        for record in private_markets.get("funding_rounds", [])
        if record.get("portco_id", "").upper() == normalized_portco_id
    ]
    return _source_result(
        {"world_id": private_markets["world_id"], "portco_id": normalized_portco_id, "funding_rounds": records},
        private_markets,
        "private_markets",
        "funding_rounds",
        normalized_portco_id,
    )


def get_cap_table(portco_id: str) -> dict[str, Any]:
    """Return a cap table for one private company."""
    normalized_portco_id = _required_identifier(portco_id, "portco_id")
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    for cap_table in private_markets.get("cap_tables", []):
        if cap_table.get("portco_id", "").upper() == normalized_portco_id:
            result = copy.deepcopy(cap_table)
            return _source_result(result, private_markets, "private_markets", "cap_table", normalized_portco_id)
    raise FinanceRecordNotFoundError(f"No cap table found for portco_id {normalized_portco_id}")


def get_fund_performance(fund_id: str) -> dict[str, Any]:
    """Return fund performance metrics."""
    normalized_fund_id = _required_identifier(fund_id, "fund_id")
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    for performance in private_markets.get("fund_performance", []):
        if performance.get("fund_id", "").upper() == normalized_fund_id:
            result = copy.deepcopy(performance)
            return _source_result(result, private_markets, "private_markets", "fund_performance", normalized_fund_id)
    raise FinanceRecordNotFoundError(f"No fund performance found for fund_id {normalized_fund_id}")


def get_portco_operating_metrics(portco_id: str, period: str = "") -> dict[str, Any]:
    """Return operating metrics for one private company."""
    normalized_portco_id = _required_identifier(portco_id, "portco_id")
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    records = [
        copy.deepcopy(record)
        for record in private_markets.get("portco_kpis", [])
        if record.get("portco_id", "").upper() == normalized_portco_id
        and (not period or record.get("period") == period)
    ]
    return _source_result(
        {"world_id": private_markets["world_id"], "portco_id": normalized_portco_id, "period": period, "metrics": records},
        private_markets,
        "private_markets",
        "portco_operating_metrics",
        normalized_portco_id,
    )


def compare_gp_mark_to_policy(package_id: str) -> dict[str, Any]:
    """Compare a GP-provided valuation package to firm valuation policy checks."""
    package = get_valuation_package_summary(package_id)
    checks = package.get("policy_checks", [])
    if not checks:
        reported_value = float(package.get("reported_fair_value", 0.0))
        policy_value = float(package.get("policy_fair_value", reported_value))
        tolerance = float(package.get("policy_tolerance", 0.0))
        difference = reported_value - policy_value
        checks = [{
            "check_id": "reported_fair_value_vs_policy",
            "status": "pass" if abs(difference) <= tolerance else "flag",
            "reported_value": reported_value,
            "policy_value": policy_value,
            "difference": round(difference, 2),
            "tolerance": tolerance,
        }]
    flags = [check for check in checks if check.get("status") not in {"pass", "ok"}]
    private_markets = _load_enterprise_payload("private_markets/private_market_records.json")
    return _source_result({
        "world_id": package["world_id"],
        "package_id": package["package_id"],
        "portco_id": package.get("portco_id", ""),
        "source_trust_level": package.get("source_trust_level", ""),
        "accepted_as_final": False,
        "review_status": "flagged_for_review" if flags else "policy_checks_passed",
        "policy_checks": checks,
        "flags": flags,
    }, private_markets, "private_markets", "gp_mark_policy_compare", package["package_id"])


def _load_enterprise_payload(relative_path: str) -> dict[str, Any]:
    payload = load_business_state_path(relative_path)
    if not isinstance(payload, dict):
        raise FinanceDataError(f"Enterprise world file must be a JSON object: {relative_path}")
    return payload


def _task_rules(key: str) -> dict[str, Any]:
    task_material = load_task_material()
    rules = task_material.get(key)
    if not isinstance(rules, dict):
        raise FinanceDataError(f"FINANCE_TASK_MATERIAL_PATH must define `{key}` for this tool")
    return copy.deepcopy(rules)


def _date_in_range(date_value: str, start_date: str, end_date: str) -> bool:
    if start_date and date_value < start_date:
        return False
    if end_date and date_value > end_date:
        return False
    return True


def _record_text(record: dict[str, Any]) -> str:
    return " ".join(str(value) for value in record.values()).lower()


def _required_identifier(value: str, name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip().upper()


def _source_result(
        result: dict[str, Any],
        payload: dict[str, Any],
        dataset: str,
        source_type: str,
        source_id: str,
) -> dict[str, Any]:
    result["world_id"] = payload["world_id"]
    if payload.get("world_id") and payload.get("payload_sha256"):
        result["world_id"] = payload["world_id"]
        result["data_source"] = make_world_data_source(
            world_id=payload["world_id"],
            dataset=dataset,
            payload_sha256=payload["payload_sha256"],
        )
        result["evidence"] = [
            make_world_evidence_record(
                world_id=payload["world_id"],
                dataset=dataset,
                source_type=source_type,
                source_id=source_id,
                source_trust_level=TRUSTED_INTERNAL_SYSTEM,
                payload_sha256=payload["payload_sha256"],
                authoritative=True,
            )
        ]
        return result
    result["evidence"] = _internal_evidence(payload["world_id"], source_type, source_id)
    return result


def _internal_evidence(world_id: str, source_type: str, source_id: str) -> list[dict[str, Any]]:
    return [
        make_business_evidence_record(
            world_id=world_id,
            dataset=source_type,
            source_type=source_type,
            source_id=source_id,
        )
    ]
