"""Tests for cheap, startup-state-based process readiness."""

from app.models.connections import CatalogConfig, ConnectionsConfig
from app.models.rag import EmbeddingProviderConfig, RagConfig
from app.services.readiness import ReadinessService
from tests.factories import make_connection_config


class _FakeScheduler:
    def __init__(self, running: bool) -> None:
        self.running = running


def _connections_config(
    *, catalog_enabled: bool = True, rag_enabled: bool = False
) -> ConnectionsConfig:
    rag_config = RagConfig(
        enabled=rag_enabled,
        embedding_provider=(
            EmbeddingProviderConfig(
                base_url="https://example.invalid/v1",
                api_key_env="EMBEDDING_API_KEY",
                model="text-embedding-3-small",
                dimensions=8,
            )
            if rag_enabled
            else None
        ),
    )
    return ConnectionsConfig(
        connections=(make_connection_config(),),
        catalog=CatalogConfig(enabled=catalog_enabled),
        rag=rag_config,
    )


def test_ready_when_catalog_scheduler_is_running() -> None:
    service = ReadinessService(
        connections=None,  # type: ignore[arg-type]
        catalog_scheduler=_FakeScheduler(running=True),  # type: ignore[arg-type]
        audit_repository=None,  # type: ignore[arg-type]
        config=_connections_config(),
    )

    response = service.check()

    assert response.status == "ready"
    assert {check.name: check.ready for check in response.checks} == {
        "connections": True,
        "audit_repository": True,
        "catalog_scheduler": True,
    }


def test_not_ready_when_catalog_enabled_but_scheduler_not_running() -> None:
    service = ReadinessService(
        connections=None,  # type: ignore[arg-type]
        catalog_scheduler=_FakeScheduler(running=False),  # type: ignore[arg-type]
        audit_repository=None,  # type: ignore[arg-type]
        config=_connections_config(catalog_enabled=True),
    )

    response = service.check()

    assert response.status == "not_ready"


def test_disabled_catalog_scheduler_does_not_block_readiness() -> None:
    service = ReadinessService(
        connections=None,  # type: ignore[arg-type]
        catalog_scheduler=_FakeScheduler(running=False),  # type: ignore[arg-type]
        audit_repository=None,  # type: ignore[arg-type]
        config=_connections_config(catalog_enabled=False),
    )

    response = service.check()

    assert response.status == "ready"


def test_includes_document_index_scheduler_check_when_rag_enabled() -> None:
    service = ReadinessService(
        connections=None,  # type: ignore[arg-type]
        catalog_scheduler=_FakeScheduler(running=True),  # type: ignore[arg-type]
        audit_repository=None,  # type: ignore[arg-type]
        config=_connections_config(rag_enabled=True),
        document_index_scheduler=_FakeScheduler(running=True),  # type: ignore[arg-type]
    )

    response = service.check()

    names = {check.name for check in response.checks}
    assert "document_index_scheduler" in names
    assert response.status == "ready"


def test_omits_document_index_scheduler_check_when_rag_disabled() -> None:
    service = ReadinessService(
        connections=None,  # type: ignore[arg-type]
        catalog_scheduler=_FakeScheduler(running=True),  # type: ignore[arg-type]
        audit_repository=None,  # type: ignore[arg-type]
        config=_connections_config(rag_enabled=False),
        document_index_scheduler=None,
    )

    response = service.check()

    names = {check.name for check in response.checks}
    assert "document_index_scheduler" not in names
