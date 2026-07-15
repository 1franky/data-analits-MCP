"""Shared version marker for stable MCP response envelopes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

McpContractVersion = Literal["1.0.0"]
MCP_CONTRACT_VERSION: McpContractVersion = "1.0.0"


class VersionedToolResponse(BaseModel):
    """Base for top-level MCP responses governed by the public contract."""

    model_config = ConfigDict(frozen=True)

    contract_version: McpContractVersion = MCP_CONTRACT_VERSION
