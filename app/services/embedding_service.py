"""Embedding service — converts guidelines text to vectors for RAG."""

from typing import Optional
import json
import logging
from sentence_transformers import SentenceTransformer
from app.db import async_session, GuidelineEmbedding
from sqlalchemy import select, and_, func
from datetime import datetime

logger = logging.getLogger(__name__)


# Global embedding model (lazy-loaded)
_embedding_model = None


def _get_embedding_model():
    """Get or initialize the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model: sentence-transformers/all-MiniLM-L6-v2")
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model


def embed_text(text: str) -> list[float]:
    """Convert text to embedding vector."""
    model = _get_embedding_model()
    embedding = model.encode(text, convert_to_tensor=False)
    return embedding.tolist()


def chunk_guideline_content(condition_data: dict) -> list[dict]:
    """
    Split a guideline condition into chunks for embedding.
    
    Each chunk represents a logical section (diagnostic criteria, treatment, etc.)
    to allow more precise retrieval.
    """
    chunks = []
    condition_id = condition_data.get("condition_id", "unknown")
    condition_name = condition_data.get("condition_name", "Unknown")
    category = condition_data.get("category", "general")
    countries = condition_data.get("countries", [])
    
    # Extract and chunk different sections
    sections = {
        "condition_info": f"Condition: {condition_name}. ICD-10: {condition_data.get('icd10', 'N/A')}",
        "symptoms": condition_data.get("diagnostic_criteria", {}).get("symptoms", ""),
        "tests": ", ".join(condition_data.get("diagnostic_criteria", {}).get("tests", [])),
        "treatment": "\n".join(condition_data.get("treatment_guidelines", {}).get("first_line", [])),
        "red_flags": ", ".join(condition_data.get("red_flags", [])),
    }
    
    for section_type, content in sections.items():
        if content:
            chunks.append({
                "condition_id": condition_id,
                "condition_name": condition_name,
                "category": category,
                "countries": countries,
                "chunk_type": section_type,
                "content": content,
                "metadata": {
                    "severity": condition_data.get("severity", "unknown"),
                    "source": condition_data.get("source", ""),
                    "confidence": condition_data.get("confidence", 0.0),
                }
            })
    
    return chunks


async def seed_embeddings():
    """Load guidelines from JSON and seed the embeddings table."""
    import uuid
    from pathlib import Path
    
    guidelines_dir = Path(__file__).parent.parent / "data" / "guidelines"
    guideline_files = [
        "cardiovascular_guidelines.json",
        "respiratory_guidelines.json",
        "gi_neuro_endocrine_guidelines.json",
        "infection_musculoskeletal_psychiatric_guidelines.json",
    ]
    
    total_embeddings = 0
    
    async with async_session() as db:
        # Clear existing embeddings
        logger.info("Clearing existing embeddings...")
        await db.execute("DELETE FROM guideline_embeddings")
        await db.commit()
        
        for filename in guideline_files:
            filepath = guidelines_dir / filename
            if not filepath.exists():
                logger.warning(f"Guidelines file not found: {filepath}")
                continue
            
            logger.info(f"Processing {filename}...")
            
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Process each section in the file
            for section_key, conditions_list in data.items():
                if not isinstance(conditions_list, list):
                    continue
                
                category = section_key.rstrip('s')  # Remove trailing 's'
                logger.info(f"  {section_key}: {len(conditions_list)} conditions")
                
                for condition in conditions_list:
                    try:
                        # Chunk the condition
                        chunks = chunk_guideline_content(condition)
                        
                        # Embed and store each chunk
                        for chunk in chunks:
                            embedding = embed_text(chunk["content"])
                            
                            embedding_obj = GuidelineEmbedding(
                                id=str(uuid.uuid4()),
                                condition_id=chunk["condition_id"],
                                condition_name=chunk["condition_name"],
                                category=category,
                                countries=chunk["countries"],
                                content_chunk=chunk["content"],
                                chunk_index=chunk["chunk_type"],
                                embedding=embedding,
                                metadata=chunk["metadata"],
                            )
                            db.add(embedding_obj)
                            total_embeddings += 1
                        
                        if total_embeddings % 50 == 0:
                            logger.info(f"  Embedded {total_embeddings} chunks so far...")
                    
                    except Exception as e:
                        logger.error(f"Error processing {condition.get('condition_name', 'unknown')}: {e}")
                        continue
            
            await db.commit()
            logger.info(f"Committed {filename}")
    
    logger.info(f"✅ Successfully seeded {total_embeddings} guideline chunks!")
    return total_embeddings


async def retrieve_relevant_guidelines(
    query: str,
    category: Optional[str] = None,
    country: Optional[str] = None,
    k: int = 5,
    min_similarity: float = 0.5,
) -> list[dict]:
    """
    Retrieve the most relevant guideline chunks using vector similarity search.
    
    Args:
        query: The search query (e.g., "treatment for hypertension")
        category: Filter by category (optional)
        country: Filter by country (optional)
        k: Number of results to return
        min_similarity: Minimum similarity score threshold
    
    Returns:
        List of relevant guideline chunks with metadata.
    """
    # Embed the query
    query_embedding = embed_text(query)
    
    async with async_session() as db:
        # Build the query using cosine distance
        query_stmt = (
            select(GuidelineEmbedding)
            .order_by(func.cosine_distance(GuidelineEmbedding.embedding, query_embedding))
            .limit(k)
        )
        
        # Apply filters if provided
        filters = []
        if category:
            filters.append(GuidelineEmbedding.category == category)
        if country:
            filters.append(GuidelineEmbedding.countries.contains([country]))
        
        if filters:
            query_stmt = query_stmt.where(and_(*filters))
        
        result = await db.execute(query_stmt)
        embeddings = result.scalars().all()
        
        # Format results
        results = []
        for emb in embeddings:
            results.append({
                "condition_id": emb.condition_id,
                "condition_name": emb.condition_name,
                "category": emb.category,
                "content": emb.content_chunk,
                "chunk_type": emb.chunk_index,
                "metadata": emb.metadata,
                "source": emb.metadata.get("source", "") if emb.metadata else "",
            })
        
        return results


async def get_condition_guidelines(condition_id: str, country: Optional[str] = None) -> dict:
    """
    Retrieve all guideline information for a specific condition.
    """
    async with async_session() as db:
        query_stmt = select(GuidelineEmbedding).where(
            GuidelineEmbedding.condition_id == condition_id
        )
        
        if country:
            query_stmt = query_stmt.where(GuidelineEmbedding.countries.contains([country]))
        
        result = await db.execute(query_stmt)
        embeddings = result.scalars().all()
        
        # Organize by chunk type
        guidelines = {
            "condition_id": condition_id,
            "chunks": {}
        }
        
        for embedding in embeddings:
            chunk_type = embedding.chunk_index
            if chunk_type not in guidelines["chunks"]:
                guidelines["chunks"][chunk_type] = []
            
            guidelines["chunks"][chunk_type].append({
                "content": embedding.content_chunk,
                "metadata": embedding.metadata,
            })
        
        return guidelines
