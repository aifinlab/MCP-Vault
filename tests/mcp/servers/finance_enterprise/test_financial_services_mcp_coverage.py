import unittest

from mcpuniverse.mcp.servers.finance_company_data.server import build_server as build_company_data_server
from mcpuniverse.mcp.servers.finance_crm.server import build_server as build_crm_server
from mcpuniverse.mcp.servers.finance_document_store.server import build_server as build_document_store_server
from mcpuniverse.mcp.servers.finance_fx_derivatives.server import build_server as build_fx_derivatives_server
from mcpuniverse.mcp.servers.finance_kyc_screening.server import build_server as build_kyc_server
from mcpuniverse.mcp.servers.finance_ledger.server import build_server as build_ledger_server
from mcpuniverse.mcp.servers.finance_nav.server import build_server as build_nav_server
from mcpuniverse.mcp.servers.finance_private_markets.server import build_server as build_private_markets_server
from mcpuniverse.mcp.servers.finance_rates_fixed_income.server import build_server as build_rates_fixed_income_server
from mcpuniverse.mcp.servers.finance_shared.company_data import get_model_input_pack
from mcpuniverse.mcp.servers.finance_shared.cross_asset_data import (
    bond_price,
    fx_forward_price,
    interest_rate_curve,
    option_value,
)
from mcpuniverse.mcp.servers.finance_shared.document_store import get_document, search_documents
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    compare_gl_subledger_records,
    compare_gp_mark_to_policy,
    draft_adjusting_entry,
    get_budget_vs_actuals,
    get_client_record,
    get_fund_performance,
    get_fund_portfolio,
    get_funding_rounds,
    get_journal_source_breakdown,
    get_nav_pack,
    get_trial_balance,
    list_statement_tieouts,
    screen_sanctions_pep,
    search_private_companies,
    trace_recon_break,
)
from mcpuniverse.mcp.servers.finance_shared.portfolio_extensions import (
    find_tax_loss_harvesting_candidates,
    generate_rebalance_proposal,
    get_model_portfolio,
)
from mcpuniverse.mcp.servers.finance_shared.transaction_data import (
    get_transaction_multiples,
    search_precedent_transactions,
)
from mcpuniverse.mcp.servers.finance_transactions.server import build_server as build_transactions_server
from mcpuniverse.mcp.servers.finance_subledger.server import build_server as build_subledger_server
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinancialServicesMcpCoverage(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        configure_finance_world_env()

    def tearDown(self):
        clear_finance_world_env()

    async def test_enterprise_server_tools(self):
        servers = [
            (build_crm_server(), [
                "search_clients",
                "get_client_record",
                "list_client_interactions",
                "list_meetings",
                "get_meeting_context",
                "list_follow_ups",
            ]),
            (build_kyc_server(), [
                "get_onboarding_packet",
                "screen_sanctions_pep",
                "evaluate_kyc_rules",
                "list_kyc_gaps",
                "get_escalation_recommendation",
            ]),
            (build_ledger_server(), [
                "get_trial_balance",
                "list_gl_transactions",
                "get_journal_entry",
                "list_accrual_candidates",
                "get_rollforward_schedule",
                "get_budget_vs_actuals",
                "get_journal_source_breakdown",
                "draft_adjusting_entry",
            ]),
            (build_subledger_server(), [
                "list_subledger_positions",
                "list_subledger_transactions",
                "get_trade_lifecycle",
                "compare_gl_subledger_records",
                "trace_recon_break",
            ]),
            (build_nav_server(), [
                "get_nav_pack",
                "get_lp_statement",
                "recompute_capital_account",
                "list_statement_tieouts",
            ]),
            (build_private_markets_server(), [
                "search_private_companies",
                "get_portco_profile",
                "get_portco_kpis",
                "get_fund_portfolio",
                "get_deal_record",
                "list_deal_pipeline",
                "get_valuation_package_summary",
                "get_funding_rounds",
                "get_cap_table",
                "get_fund_performance",
                "get_portco_operating_metrics",
                "compare_gp_mark_to_policy",
            ]),
            (build_document_store_server(), [
                "search_documents",
                "get_document",
                "list_folder",
                "get_document_metadata",
            ]),
            (build_company_data_server(), [
                "search_companies",
                "get_standardized_financials",
                "get_segment_financials",
                "get_capital_structure",
                "get_wacc_inputs",
                "get_model_input_pack",
            ]),
            (build_transactions_server(), [
                "search_precedent_transactions",
                "get_transaction_detail",
                "get_transaction_multiples",
                "summarize_sector_transactions",
            ]),
            (build_rates_fixed_income_server(), [
                "bond_price",
                "bond_future_price",
                "interest_rate_curve",
                "credit_curve",
                "inflation_curve",
                "yieldbook_bond_reference",
                "yieldbook_cashflow",
                "yieldbook_scenario",
                "fixed_income_risk_analytics",
            ]),
            (build_fx_derivatives_server(), [
                "fx_spot_price",
                "fx_forward_price",
                "fx_forward_curve",
                "fx_vol_surface",
                "equity_vol_surface",
                "option_template_list",
                "option_value",
                "ir_swap",
            ]),
        ]
        for server, expected_tool_names in servers:
            tools = await server.list_tools()
            self.assertEqual([tool.name for tool in tools], expected_tool_names)

    def test_crm_and_kyc_data_paths(self):
        client = get_client_record("CLIENT-FS-0001")
        self.assertEqual(client["client_name"], "Financial Services Test Client")
        self.assertEqual(client["evidence"][0]["source_trust_level"], "trusted_internal_system")
        self.assertEqual(client["world_id"], "financial_services_seed42")

        screening = screen_sanctions_pep("CLIENT-FS-0001")
        self.assertEqual(screening["sanctions_status"], "clear")

    def test_ledger_subledger_nav_and_private_market_paths(self):
        trial_balance = get_trial_balance("ENT-FS-0001", "2026-05")
        self.assertEqual(trial_balance["lines"][0]["account_code"], "1000")

        reconciliation = compare_gl_subledger_records("ENT-FS-0001", "2026-05")
        self.assertEqual(reconciliation["break_count"], 1)

        nav_pack = get_nav_pack("FUND-FS-III", "2026-05-15")
        self.assertEqual(nav_pack["net_asset_value"], 120000000.0)

        tieouts = list_statement_tieouts("FUND-FS-III", "2026-05-15")
        self.assertEqual(tieouts["tieouts"][0]["difference"], 0.0)

        companies = search_private_companies(sector="software")
        self.assertEqual(companies["companies"][0]["portco_id"], "PC-FS-001")

        portfolio = get_fund_portfolio("FUND-FS-III")
        self.assertEqual(portfolio["holdings"][0]["portco_id"], "PC-FS-001")


class TestFinancialServicesWorldCapabilities(unittest.TestCase):

    def setUp(self):
        configure_finance_world_env()

    def tearDown(self):
        clear_finance_world_env()

    def test_document_company_and_transaction_world_capabilities(self):
        documents = search_documents(query="revenue")
        self.assertEqual(documents["documents"][0]["document_id"], "DOC-FS-10K-AAPL-2025")
        self._assert_world_source(documents["documents"][0], "source_documents")

        document = get_document("DOC-FS-EMAIL-0001")
        self.assertEqual(document["source_trust_level"], "untrusted_email")
        self._assert_world_source(document, "source_documents")

        model_pack = get_model_input_pack("AAPL", model_type="dcf")
        self.assertEqual(model_pack["ticker"], "AAPL")
        self._assert_world_source(model_pack, "company_data")

        transactions = search_precedent_transactions(sector="software")
        self.assertEqual(transactions["transactions"][0]["transaction_id"], "TXN-FS-0001")
        self._assert_world_source(transactions["transactions"][0], "transactions")

        multiples = get_transaction_multiples("TXN-FS-0001")
        self.assertIn("ev_ebitda", multiples["multiples"])
        self._assert_world_source(multiples, "transactions")

    def test_portfolio_ledger_subledger_and_private_market_world_capabilities(self):
        tax_loss = find_tax_loss_harvesting_candidates("ACC-FS-0001", min_loss_amount=100.0)
        self.assertEqual(tax_loss["candidates"][0]["ticker"], "AAPL")
        self._assert_world_source(tax_loss, "accounts")

        model = get_model_portfolio("ACC-FS-0001")
        self.assertEqual(model["model_id"], "MODEL-BALANCED-60-40")
        self._assert_world_source(model, "accounts")

        rebalance = generate_rebalance_proposal("ACC-FS-0001")
        self.assertEqual(rebalance["proposal_status"], "draft_not_submitted")
        self._assert_world_source(rebalance, "accounts")

        budget = get_budget_vs_actuals("ENT-FS-0001", "2026-05")
        self.assertEqual(budget["lines"][0]["account_code"], "6100")
        self._assert_world_source(budget, "ledger")

        breakdown = get_journal_source_breakdown("ENT-FS-0001", "2026-05")
        self.assertEqual(breakdown["breakdown"][0]["journal_source"], "ap_invoice")
        self._assert_world_source(breakdown, "ledger")

        draft_entry = draft_adjusting_entry("ENT-FS-0001", "2026-05", "6100", "2000", 2500.0)
        self.assertEqual(draft_entry["posting_status"], "not_posted")
        self._assert_world_source(draft_entry, "ledger")

        break_trace = trace_recon_break("BRK-FS-0001")
        self.assertEqual(break_trace["break_id"], "BRK-FS-0001")
        self._assert_world_source(break_trace, "subledger")

        rounds = get_funding_rounds("PC-FS-001")
        self.assertEqual(rounds["funding_rounds"][0]["round_type"], "Series C")
        self._assert_world_source(rounds, "private_markets")

        performance = get_fund_performance("FUND-FS-III")
        self.assertGreater(performance["irr"], 0)
        self._assert_world_source(performance, "private_markets")

        gp_check = compare_gp_mark_to_policy("VAL-PKG-FS-0001")
        self.assertFalse(gp_check["accepted_as_final"])
        self._assert_world_source(gp_check, "private_markets")

    def test_rates_fixed_income_fx_and_derivatives_world_capabilities(self):
        bond = bond_price("US91282CJJ18")
        self.assertEqual(bond["bond_id"], "BOND-FS-UST10Y")
        self._assert_world_source(bond, "fixed_income")

        rates = interest_rate_curve("USD")
        self.assertEqual(rates["curve_id"], "USD-GOVT-20260515")
        self._assert_world_source(rates, "rates_curves")

        fx_forward = fx_forward_price("USDJPY", tenor="3M")
        self.assertEqual(fx_forward["currency_pair"], "USDJPY")
        self._assert_world_source(fx_forward, "fx")

        option = option_value(".SPX", strike=5000.0, expiry="2026-08-21", option_type="call")
        self.assertEqual(option["option_id"], "OPT-FS-SPX-5000C-202608")
        self._assert_world_source(option, "derivatives")

    def _assert_world_source(self, payload, dataset):
        self.assertEqual(payload["world_id"], "financial_services_seed42")
        self.assertEqual(payload["data_source"]["data_source_type"], "benchmark_world")
        self.assertEqual(payload["data_source"]["dataset"], dataset)
        self.assertEqual(payload["data_source"]["provider"], "deterministic")
        self.assertTrue(payload["data_source"]["payload_sha256"])
        self.assertIn(payload["evidence"][0]["source_trust_level"], {
            "trusted_internal_system",
            "trusted_deterministic_provider",
            "trusted_regulatory_filing",
            "untrusted_document",
            "untrusted_email",
            "untrusted_gp_package",
        })


if __name__ == "__main__":
    unittest.main()
