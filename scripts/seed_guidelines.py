"""Script to seed the guideline embeddings vector store."""

import asyncio
import json
import logging
from pathlib import Path
import uuid

from app.db import async_session, GuidelineEmbedding, init_db
from app.services.embedding_service import embed_text, chunk_guideline_content

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_vector_store():
    """Load guidelines from JSON and seed the embeddings table."""
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    
    guidelines_dir = Path(__file__).parent / "data" / "guidelines"
    
    # File mapping: filename -> category (for files with multiple categories)
    file_mappings = {
        "cardiovascular_guidelines.json": ["cardiovascular"],
        "respiratory_guidelines.json": ["respiratory"],
        "gi_neuro_endocrine_guidelines.json": ["gastrointestinal", "neurological", "endocrine"],
        "infection_musculoskeletal_psychiatric_guidelines.json": ["infectious_disease", "musculoskeletal", "psychiatric"],
    }
    
    total_embeddings = 0
    
    async with async_session() as db:
        # Clear existing embeddings
        logger.info("Clearing existing embeddings...")
        await db.execute("DELETE FROM guideline_embeddings")
        await db.commit()
        
        # Process each guideline file
        for filename, categories in file_mappings.items():
            filepath = guidelines_dir / filename
            
            if not filepath.exists():
                logger.warning(f"Guidelines file not found: {filepath}")
                continue
            
            logger.info(f"\nProcessing {filename}...")
            
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Process each section in the file
            for section_key, conditions_list in data.items():
                if not isinstance(conditions_list, list):
                    continue
                
                # Determine category based on section key
                category = section_key.rstrip('s')  # Remove trailing 's' for singular form
                
                logger.info(f"  Processing {section_key}: {len(conditions_list)} conditions")
                
                for condition_idx, condition in enumerate(conditions_list, 1):
                    condition_id = condition.get("condition_id", f"unknown_{condition_idx}")
                    condition_name = condition.get("condition_name", "Unknown")
                    countries = condition.get("countries", ["India", "US", "UK"])
                    severity = condition.get("severity", "unknown")
                    source = condition.get("source", "")
                    confidence = condition.get("confidence", 0.0)
                    
                    # Chunk the condition into logical sections
                    chunks = chunk_guideline_content(condition)
                    
                    # Embed and store each chunk
                    for chunk in chunks:
                        try:
                            # Generate embedding
                            embedding = embed_text(chunk["content"])
                            
                            # Create database object
                            embedding_obj = GuidelineEmbedding(
                                id=str(uuid.uuid4()),
                                condition_id=chunk["condition_id"],
                                condition_name=chunk["condition_name"],
                                category=category,
                                countries=countries,
                                content_chunk=chunk["content"],
                                chunk_index=chunk["chunk_type"],
                                embedding=embedding,
                                metadata_={
                                    "severity": severity,
                                    "source": source,
                                    "confidence": confidence,
                                    "chunk_type": chunk["chunk_type"],
                                },
                            )
                            
                            db.add(embedding_obj)
                            total_embeddings += 1
                            
                            if total_embeddings % 50 == 0:
                                logger.info(f"    Embedded {total_embeddings} chunks...")
                        
                        except Exception as e:
                            logger.error(f"Error embedding chunk for {condition_name}: {e}")
                            continue
                    
                    logger.info(f"    ✓ {condition_name} ({len(chunks)} chunks)")
            
            # Commit after each file
            await db.commit()
            logger.info(f"  Committed embeddings for {filename}")
    
    logger.info(f"\n✅ Successfully seeded {total_embeddings} guideline chunks!")
    return total_embeddings


async def verify_embeddings():
    """Verify that embeddings were properly seeded."""
    async with async_session() as db:
        # Count total embeddings
        from sqlalchemy import func, select
        
        result = await db.execute(select(func.count(GuidelineEmbedding.id)))
        total_count = result.scalar() or 0
        
        # Count by category
        from sqlalchemy import select, distinct
        
        result = await db.execute(select(distinct(GuidelineEmbedding.category)))
        categories = result.scalars().all()
        
        # Count by condition
        result = await db.execute(select(func.count(distinct(GuidelineEmbedding.condition_id))))
        unique_conditions = result.scalar() or 0
        
        logger.info("\n" + "="*60)
        logger.info("EMBEDDING VERIFICATION REPORT")
        logger.info("="*60)
        logger.info(f"Total embedding chunks: {total_count}")
        logger.info(f"Unique conditions: {unique_conditions}")
        logger.info(f"Categories: {len(categories)}")
        
        for category in sorted(categories):
            result = await db.execute(
                select(func.count(GuidelineEmbedding.id)).where(
                    GuidelineEmbedding.category == category
                )
            )
            count = result.scalar() or 0
            logger.info(f"  • {category}: {count} chunks")
        
        # Show sample retrieval
        logger.info("\n" + "="*60)
        logger.info("SAMPLE RETRIEVAL TEST")
        logger.info("="*60)
        
        from app.services.embedding_service import retrieve_relevant_guidelines
        
        sample_query = "treatment for chest pain"
        logger.info(f"Query: '{sample_query}'")
        
        results = await retrieve_relevant_guidelines(query=sample_query, k=3)
        logger.info(f"Retrieved {len(results)} results:")
        
        for idx, result in enumerate(results, 1):
            logger.info(f"\n  Result {idx}:")
            logger.info(f"    Condition: {result['condition_name']}")
            logger.info(f"    Type: {result['chunk_type']}")
            logger.info(f"    Content: {result['content'][:100]}...")


async def main():
    """Run the seeding process."""
    try:
        # Seed embeddings
        total = await seed_vector_store()
        
        # Verify
        await verify_embeddings()
        
        logger.info("\n" + "="*60)
        logger.info("✅ SEEDING COMPLETE AND VERIFIED")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Error during seeding: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
