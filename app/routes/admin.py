"""Admin endpoints — audit log access, guideline seeding."""

import logging
from fastapi import APIRouter, Depends, Query, HTTPException

from app.services.audit import get_audit_logs
from app.services.embedding_service import seed_embeddings
from app.services.citation_service import get_citations_with_urls, add_citation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs")
async def list_audit_logs(
    conversation_id: str | None = Query(None),
    step: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Retrieve audit logs with optional filtering."""
    logs = await get_audit_logs(
        conversation_id=conversation_id,
        step=step,
        limit=limit,
    )
    return {"logs": logs, "count": len(logs)}


@router.post("/seed-guidelines")
async def seed_guidelines_endpoint():
    """
    Seed the guideline embeddings vector store.
    
    This loads all curated clinical guidelines from JSON files,
    chunks them, generates embeddings, and stores in PostgreSQL.
    
    **Warning:** This deletes all existing embeddings and rebuilds from scratch.
    """
    try:
        logger.info("Starting guideline seeding...")
        await seed_embeddings()
        logger.info("Guideline seeding completed successfully")
        
        return {
            "status": "success",
            "message": "Guidelines seeded successfully",
            "next_step": "Run end-to-end tests or make /diagnose requests"
        }
    
    except Exception as e:
        logger.error(f"Error seeding guidelines: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error seeding guidelines: {str(e)}"
        )


@router.get("/citations")
def list_citations():
    """
    List all available guideline citations with URLs.
    
    Returns metadata for all tracked clinical guideline sources including:
    - Full names and URLs
    - Publication dates
    - DOI identifiers
    - Version information
    """
    # Get all citations by passing empty list (will return all)
    from app.services.citation_service import GUIDELINE_CITATIONS
    
    citations = []
    for source_name in sorted(GUIDELINE_CITATIONS.keys()):
        citation_obj = GUIDELINE_CITATIONS[source_name]
        citations.append({
            "name": source_name,
            "full_name": citation_obj.source,
            "url": citation_obj.url,
            "publication_date": citation_obj.publication_date,
            "doi": citation_obj.doi,
            "version": citation_obj.version,
            "authors": citation_obj.authors,
        })
    
    return {
        "total": len(citations),
        "citations": citations
    }


@router.get("/citations/{source_name}")
def get_citation_detail(source_name: str):
    """Get detailed information about a specific citation."""
    citations = get_citations_with_urls([source_name])
    
    if not citations:
        raise HTTPException(
            status_code=404,
            detail=f"Citation '{source_name}' not found"
        )
    
    return citations[0]


@router.post("/citations")
def add_new_citation(
    source_name: str = Query(..., description="Short name (e.g., 'WHO 2022')"),
    source: str = Query(..., description="Full source title"),
    url: str | None = Query(None, description="URL to guideline source"),
    publication_date: str | None = Query(None, description="Publication date (YYYY-MM-DD)"),
    version: str | None = Query(None, description="Guideline version"),
):
    """
    Add a new clinical guideline citation to the system.
    
    This registers a new source that can be tracked and cited in recommendations.
    """
    try:
        authors = ["Unknown"]  # Could be extended with more metadata
        add_citation(
            source_name=source_name,
            source=source,
            url=url,
            publication_date=publication_date,
            authors=authors,
            version=version,
        )
        
        logger.info(f"Added new citation: {source_name}")
        
        return {
            "status": "success",
            "message": f"Citation '{source_name}' added successfully",
            "citation": {
                "name": source_name,
                "full_name": source,
                "url": url,
                "publication_date": publication_date,
                "version": version,
            }
        }
    
    except Exception as e:
        logger.error(f"Error adding citation: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Error adding citation: {str(e)}"
        )
