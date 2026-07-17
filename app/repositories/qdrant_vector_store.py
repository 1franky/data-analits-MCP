"""Qdrant-backed implementation of the replaceable vector store contract."""

import uuid
from datetime import datetime
from typing import Any, cast

from pydantic import SecretStr
from qdrant_client import QdrantClient, models

from app.exceptions import VectorStoreError
from app.models.rag import ChunkSearchMatch, DocumentChunk, DocumentMetadata
from app.repositories.vector_store import VectorStoreRepository


class QdrantVectorStoreRepository(VectorStoreRepository):
    """Store chunk embeddings in Qdrant and serve filtered semantic search."""

    def __init__(
        self,
        url: str,
        collection_name: str,
        timeout_seconds: int,
        api_key: SecretStr | None = None,
    ) -> None:
        self._collection_name = collection_name
        try:
            self._client = QdrantClient(
                url=url,
                api_key=api_key.get_secret_value() if api_key is not None else None,
                timeout=timeout_seconds,
            )
        except Exception as error:  # pragma: no cover - constructor rarely fails eagerly
            raise VectorStoreError(
                code="VECTOR_STORE_CONNECTION_ERROR",
                message="No fue posible construir el cliente del vector store.",
            ) from error

    def initialize(self, dimensions: int) -> None:
        """Create the collection if missing, or verify its vector size matches."""
        try:
            if not self._client.collection_exists(self._collection_name):
                self._client.create_collection(
                    self._collection_name,
                    vectors_config=models.VectorParams(
                        size=dimensions,
                        distance=models.Distance.COSINE,
                    ),
                )
                return
            info = self._client.get_collection(self._collection_name)
            configured_size = self._extract_vector_size(info)
            if configured_size is not None and configured_size != dimensions:
                raise VectorStoreError(
                    code="VECTOR_STORE_DIMENSION_MISMATCH",
                    message=(
                        f"La colección '{self._collection_name}' ya existe con dimensión "
                        f"{configured_size}, distinta de la configurada ({dimensions})."
                    ),
                )
        except VectorStoreError:
            raise
        except Exception as error:
            raise VectorStoreError(
                code="VECTOR_STORE_INITIALIZE_ERROR",
                message="No fue posible inicializar la colección del vector store.",
            ) from error

    def upsert_chunks(
        self,
        document_id: str,
        chunks: tuple[DocumentChunk, ...],
        vectors: tuple[tuple[float, ...], ...],
        metadata: DocumentMetadata,
    ) -> None:
        """Replace the vectors for one document with a freshly embedded set."""
        try:
            self._delete_document_points(document_id)
            if not chunks:
                return
            points = [
                models.PointStruct(
                    id=self._point_id(chunk.chunk_id),
                    vector=list(vector),
                    payload=self._payload(chunk, metadata),
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            self._client.upsert(self._collection_name, points=points, wait=True)
        except VectorStoreError:
            raise
        except Exception as error:
            raise VectorStoreError(
                code="VECTOR_STORE_UPSERT_ERROR",
                message="No fue posible guardar los vectores del documento.",
            ) from error

    def delete_document(self, document_id: str) -> None:
        """Remove every chunk vector belonging to one document."""
        try:
            self._delete_document_points(document_id)
        except Exception as error:
            raise VectorStoreError(
                code="VECTOR_STORE_DELETE_ERROR",
                message="No fue posible eliminar los vectores del documento.",
            ) from error

    def search(
        self,
        query_vector: tuple[float, ...],
        connection_id: str | None,
        domain: str | None,
        limit: int,
    ) -> tuple[ChunkSearchMatch, ...]:
        """Return the closest chunks, always including connection/domain-less documents."""
        query_filter = self._search_filter(connection_id, domain)
        try:
            response = self._client.query_points(
                self._collection_name,
                query=list(query_vector),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception as error:
            raise VectorStoreError(
                code="VECTOR_STORE_SEARCH_ERROR",
                message="No fue posible consultar el vector store.",
            ) from error
        return tuple(self._to_match(point) for point in response.points)

    def close(self) -> None:
        """Release the underlying Qdrant client connection."""
        self._client.close()

    def _delete_document_points(self, document_id: str) -> None:
        self._client.delete(
            self._collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))

    @staticmethod
    def _payload(chunk: DocumentChunk, metadata: DocumentMetadata) -> dict[str, Any]:
        return {
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "position": chunk.position,
            "text": chunk.text,
            "connection_id": metadata.connection_id,
            "domain": metadata.domain,
            "document_type": metadata.document_type,
            "title": metadata.title,
            "source": metadata.source,
            "version": metadata.version,
            "indexed_at": metadata.indexed_at.isoformat(),
        }

    @staticmethod
    def _search_filter(connection_id: str | None, domain: str | None) -> models.Filter | None:
        must: list[models.Condition] = []
        if connection_id is not None:
            must.append(
                models.Filter(
                    should=[
                        models.FieldCondition(
                            key="connection_id",
                            match=models.MatchValue(value=connection_id),
                        ),
                        models.IsNullCondition(is_null=models.PayloadField(key="connection_id")),
                    ]
                )
            )
        if domain is not None:
            must.append(
                models.Filter(
                    should=[
                        models.FieldCondition(key="domain", match=models.MatchValue(value=domain)),
                        models.IsNullCondition(is_null=models.PayloadField(key="domain")),
                    ]
                )
            )
        if not must:
            return None
        return models.Filter(must=must)

    @staticmethod
    def _to_match(point: models.ScoredPoint) -> ChunkSearchMatch:
        payload = cast(dict[str, Any], point.payload or {})
        return ChunkSearchMatch(
            document_id=cast(str, payload["document_id"]),
            chunk_id=cast(str, payload["chunk_id"]),
            text=cast(str, payload["text"]),
            score=point.score,
            metadata=DocumentMetadata(
                document_id=cast(str, payload["document_id"]),
                title=cast(str, payload["title"]),
                source=cast(str, payload["source"]),
                connection_id=cast(str | None, payload.get("connection_id")),
                domain=cast(str | None, payload.get("domain")),
                document_type=cast(str, payload["document_type"]),
                version=cast(str | None, payload.get("version")),
                indexed_at=datetime.fromisoformat(cast(str, payload["indexed_at"])),
            ),
        )

    @staticmethod
    def _extract_vector_size(info: models.CollectionInfo) -> int | None:
        vectors_config = info.config.params.vectors
        if isinstance(vectors_config, models.VectorParams):
            return vectors_config.size
        return None
