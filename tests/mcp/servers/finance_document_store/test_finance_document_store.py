import unittest

from mcpuniverse.mcp.servers.finance_document_store.server import build_server
from mcpuniverse.mcp.servers.finance_shared.document_store import (
    get_document,
    get_document_metadata,
    list_folder,
    search_documents,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceDocumentStore(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        configure_finance_world_env()
        self.mcp = build_server(port=12345)

    def tearDown(self):
        clear_finance_world_env()

    async def test_server_tools(self):
        tools = await self.mcp.list_tools()
        self.assertEqual(
            [tool.name for tool in tools],
            [
                "search_documents",
                "get_document",
                "list_folder",
                "get_document_metadata",
            ],
        )

    def test_search_documents(self):
        result = search_documents(ticker="AAPL", source_type="regulatory_filing")

        self.assertEqual(result["documents"][0]["document_id"], "DOC-FS-10K-AAPL-2025")
        self.assertEqual(result["documents"][0]["source_trust_level"], "trusted_regulatory_filing")

    def test_get_document_metadata_omits_untrusted_text(self):
        result = get_document_metadata("DOC-FS-EMAIL-0001")

        self.assertEqual(result["document_id"], "DOC-FS-EMAIL-0001")
        self.assertEqual(result["source_trust_level"], "untrusted_email")
        self.assertNotIn("untrusted_text", result)

    def test_list_folder(self):
        result = list_folder("/client_emails")

        self.assertEqual(result["documents"][0]["document_id"], "DOC-FS-EMAIL-0001")

    def test_get_document_can_hide_untrusted_text(self):
        result = get_document("DOC-FS-EMAIL-0001", include_untrusted_text=False)

        self.assertEqual(result["untrusted_text"], "")


if __name__ == "__main__":
    unittest.main()
