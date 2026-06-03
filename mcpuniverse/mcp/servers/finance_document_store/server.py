"""Document-store MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.document_store import (
    get_document as get_document_payload,
    get_document_metadata as get_document_metadata_payload,
    list_folder as list_folder_payload,
    search_documents as search_documents_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    mcp = FastMCP("finance_document_store", port=port)

    @mcp.tool()
    def search_documents(query: str = "", folder_path: str = "", source_type: str = "", ticker: str = "") -> str:
        """Search benchmark-world source documents."""
        return _json_response(search_documents_payload(query=query, folder_path=folder_path, source_type=source_type, ticker=ticker))

    @mcp.tool()
    def get_document(document_id: str, include_untrusted_text: bool = True) -> str:
        """Get one source document by id."""
        return _json_response(get_document_payload(document_id=document_id, include_untrusted_text=include_untrusted_text))

    @mcp.tool()
    def list_folder(folder_path: str = "") -> str:
        """List documents under a folder path."""
        return _json_response(list_folder_payload(folder_path=folder_path))

    @mcp.tool()
    def get_document_metadata(document_id: str) -> str:
        """Get document metadata without full text."""
        return _json_response(get_document_metadata_payload(document_id=document_id))

    return mcp


@click.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", help="Transport type")
@click.option("--port", default="8000", help="Port to listen on for SSE")
def main(transport: str, port: str):
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_document_store")
    logger.info("Starting the finance document-store MCP server")
    build_server(int(port)).run(transport=transport.lower())
