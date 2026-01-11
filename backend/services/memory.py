"""
RAG Memory service for agent context retrieval.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.database import AgentMemory
from services.embedding import get_embedding_service
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MemoryService:
    """Service for storing and retrieving agent memories using RAG."""

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()

    async def store_memory(
        self,
        organization_id: int,
        memory_type: str,
        content: str,
        summary: Optional[str] = None,
        importance: float = 0.5,
        source_entity_type: Optional[str] = None,
        source_entity_id: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> AgentMemory:
        """
        Store a memory with embedding for later retrieval.

        Args:
            organization_id: Organization ID for multi-tenancy
            memory_type: Type of memory (bom_parse, supplier_match, pricing, po_generation)
            content: The content to store
            summary: Optional summary of the content
            importance: Importance score 0.0-1.0
            source_entity_type: Related entity type (bom, supplier, part, po)
            source_entity_id: Related entity ID
            metadata: Additional metadata

        Returns:
            The created AgentMemory record
        """
        # Create embedding
        embedding = await self.embedding_service.create_embedding(content)

        memory = AgentMemory(
            organization_id=organization_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            embedding=embedding,
            importance=importance,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            metadata=metadata or {},
        )

        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)

        return memory

    async def search_memories(
        self,
        organization_id: int,
        query: str,
        memory_type: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.7,
    ) -> list[dict]:
        """
        Search for relevant memories using semantic similarity.

        Args:
            organization_id: Organization ID
            query: Search query
            memory_type: Optional filter by memory type
            top_k: Maximum number of results
            min_similarity: Minimum similarity threshold

        Returns:
            List of matching memories with similarity scores
        """
        # Create query embedding
        query_embedding = await self.embedding_service.create_embedding(query)

        # Build query
        base_query = self.db.query(
            AgentMemory,
            AgentMemory.embedding.cosine_distance(query_embedding).label("distance")
        ).filter(
            AgentMemory.organization_id == organization_id,
            AgentMemory.embedding.isnot(None),
        )

        if memory_type:
            base_query = base_query.filter(AgentMemory.memory_type == memory_type)

        # Order by similarity and limit
        results = (
            base_query
            .order_by("distance")
            .limit(top_k * 2)  # Get extra to filter by threshold
            .all()
        )

        # Convert to response format and filter by threshold
        memories = []
        for memory, distance in results:
            similarity = 1 - distance
            if similarity >= min_similarity:
                # Update accessed_at
                memory.accessed_at = datetime.utcnow()

                memories.append({
                    "id": memory.id,
                    "memory_type": memory.memory_type,
                    "content": memory.content,
                    "summary": memory.summary,
                    "importance": float(memory.importance),
                    "similarity": similarity,
                    "source_entity_type": memory.source_entity_type,
                    "source_entity_id": memory.source_entity_id,
                    "metadata": memory.metadata,
                    "created_at": memory.created_at.isoformat(),
                })

                if len(memories) >= top_k:
                    break

        self.db.commit()

        return memories

    async def get_context_for_query(
        self,
        organization_id: int,
        query: str,
        memory_types: Optional[list[str]] = None,
        max_context_length: int = 4000,
    ) -> str:
        """
        Get formatted context string for a query.

        Args:
            organization_id: Organization ID
            query: The query to get context for
            memory_types: Optional list of memory types to search
            max_context_length: Maximum length of context string

        Returns:
            Formatted context string for injection into prompts
        """
        all_memories = []

        # Search across specified memory types
        types_to_search = memory_types or ["bom_parse", "supplier_match", "pricing", "po_generation"]

        for memory_type in types_to_search:
            memories = await self.search_memories(
                organization_id=organization_id,
                query=query,
                memory_type=memory_type,
                top_k=3,
            )
            all_memories.extend(memories)

        if not all_memories:
            return ""

        # Sort by similarity and importance
        all_memories.sort(
            key=lambda m: m["similarity"] * 0.7 + m["importance"] * 0.3,
            reverse=True
        )

        # Format context
        context_parts = ["## Relevant Context from Memory\n"]
        current_length = len(context_parts[0])

        for memory in all_memories:
            entry = f"\n### {memory['memory_type'].replace('_', ' ').title()}\n{memory['content']}\n"
            if current_length + len(entry) > max_context_length:
                break
            context_parts.append(entry)
            current_length += len(entry)

        return "".join(context_parts)

    def delete_memories_for_entity(
        self,
        source_entity_type: str,
        source_entity_id: int,
    ) -> int:
        """
        Delete all memories associated with a specific entity.

        Args:
            source_entity_type: Entity type
            source_entity_id: Entity ID

        Returns:
            Number of deleted memories
        """
        deleted = (
            self.db.query(AgentMemory)
            .filter(
                AgentMemory.source_entity_type == source_entity_type,
                AgentMemory.source_entity_id == source_entity_id,
            )
            .delete()
        )
        self.db.commit()
        return deleted
