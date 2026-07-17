"""Tests for deriving document metadata from key=value path segments."""

from app.rag.ingestion.path_metadata import derive_metadata_from_path


def test_root_file_has_no_segments() -> None:
    metadata = derive_metadata_from_path("data-dictionary-global.md")
    assert metadata.connection_id is None
    assert metadata.domain is None
    assert metadata.document_type == "documentation"
    assert metadata.title == "Data Dictionary Global"


def test_single_segment_sets_connection() -> None:
    metadata = derive_metadata_from_path("connection=postgres-demo/reglas.md")
    assert metadata.connection_id == "postgres-demo"
    assert metadata.domain is None


def test_multiple_segments_in_any_order() -> None:
    metadata = derive_metadata_from_path("domain=ventas/connection=postgres-demo/reglas.md")
    assert metadata.connection_id == "postgres-demo"
    assert metadata.domain == "ventas"


def test_unrecognized_segment_is_ignored() -> None:
    metadata = derive_metadata_from_path("2026/connection=postgres-demo/reglas.md")
    assert metadata.connection_id == "postgres-demo"


def test_document_type_defaults_by_extension() -> None:
    assert derive_metadata_from_path("a.sql").document_type == "sql_reference"
    assert derive_metadata_from_path("a.json").document_type == "structured_reference"
    assert derive_metadata_from_path("a.yaml").document_type == "structured_reference"
    assert derive_metadata_from_path("a.md").document_type == "documentation"


def test_explicit_type_segment_overrides_default() -> None:
    metadata = derive_metadata_from_path("type=sql_reference/consultas.md")
    assert metadata.document_type == "sql_reference"


def test_explicit_title_segment_overrides_default() -> None:
    metadata = derive_metadata_from_path("title=Reporte-Personalizado/a.md")
    assert metadata.title == "Reporte-Personalizado"


def test_explicit_version_segment() -> None:
    metadata = derive_metadata_from_path("version=2/a.md")
    assert metadata.version == "2"


def test_default_title_normalizes_separators() -> None:
    metadata = derive_metadata_from_path("reglas_de-negocio.md")
    assert metadata.title == "Reglas De Negocio"
