"""ChromaDB retriever for the real indexed corpus."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from ..config import Settings
from ..embedding import embed_query
from ..schemas import Passage


class ChromaRetriever:
    name = "chroma"

    def __init__(self, settings: Settings) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self.settings = settings
        self.client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def retrieve(self, question: str, k: int) -> list[Passage]:
        collection = self.client.get_collection(self.settings.collection)
        embedding: Sequence[float] = embed_query(question)
        embeddings: list[Sequence[float]] = [embedding]
        include: list[
            Literal["documents", "embeddings", "metadatas", "distances", "uris", "data"]
        ] = [
            "documents",
            "metadatas",
            "distances",
        ]
        version_question = re.search(
            r"\b(?:19|20)\d{2}\b|\b(?:old|previous|prior|superseded)\b",
            question,
            re.IGNORECASE,
        )
        if version_question:
            result = collection.query(
                query_embeddings=embeddings,
                n_results=k,
                include=include,
            )
        else:
            result = collection.query(
                query_embeddings=embeddings,
                n_results=k,
                where={"superseded": False},
                include=include,
            )

        ids = result["ids"]
        documents = result["documents"]
        metadatas = result["metadatas"]
        distances = result["distances"]
        if documents is None or metadatas is None or distances is None:
            raise RuntimeError("Chroma query did not return passage data")

        passages: list[Passage] = []
        for chunk_id, document, metadata, distance in zip(
            ids[0], documents[0], metadatas[0], distances[0], strict=True
        ):
            page_value = metadata.get("page")
            passages.append(
                Passage(
                    chunk_id=chunk_id,
                    text=document,
                    source=str(metadata["source"]),
                    section=str(metadata["section"]),
                    page=int(page_value) if page_value is not None else None,
                    score=1.0 - distance,
                )
            )

        return passages
