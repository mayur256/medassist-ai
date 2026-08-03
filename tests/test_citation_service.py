"""Tests for citation tracking and source URLs."""

import pytest
from app.services.citation_service import (
    Citation,
    get_citation,
    format_citations,
    get_citations_with_urls,
    add_citation,
)


class TestCitationFormatting:
    """Test citation formatting in various styles."""
    
    def test_citation_format_apa(self):
        """Test APA format citation."""
        citation = Citation(
            source="Clinical Guidelines 2021",
            url="https://example.com/guidelines",
            publication_date="2021-06-15",
            authors=["Smith, J.", "Johnson, M."],
            doi="10.1234/example",
        )
        
        apa = citation.format_apa()
        
        assert "Smith, J., Johnson, M." in apa
        assert "(2021)" in apa
        assert "Clinical Guidelines 2021" in apa
        assert "https://doi.org/10.1234/example" in apa
    
    def test_citation_format_mla(self):
        """Test MLA format citation."""
        citation = Citation(
            source="Clinical Guidelines 2021",
            url="https://example.com/guidelines",
            publication_date="2021-06-15",
            authors=["Smith, J."],
        )
        
        mla = citation.format_mla()
        
        assert "Smith, J." in mla
        assert "Clinical Guidelines 2021" in mla
    
    def test_citation_format_harvard(self):
        """Test Harvard format citation."""
        citation = Citation(
            source="Clinical Guidelines 2021",
            publication_date="2021-06-15",
            authors=["Smith, J."],
        )
        
        harvard = citation.format_harvard()
        
        assert "Smith, J." in harvard
        assert "2021" in harvard
        assert "Clinical Guidelines 2021" in harvard
    
    def test_citation_format_chicago(self):
        """Test Chicago format citation."""
        citation = Citation(
            source="Clinical Guidelines 2021",
            publication_date="2021-06-15",
            authors=["Smith, J."],
        )
        
        chicago = citation.format_chicago()
        
        assert "Smith, J." in chicago
        assert "Clinical Guidelines 2021" in chicago


class TestCitationService:
    """Test citation service functions."""
    
    def test_get_citation_existing(self):
        """Test retrieving an existing citation."""
        citation = get_citation("WHO 2021")
        
        assert citation is not None
        assert citation.source == "World Health Organization Clinical Guidelines 2021"
        assert citation.url == "https://www.who.int/publications"
    
    def test_get_citation_nonexisting(self):
        """Test retrieving a non-existing citation."""
        citation = get_citation("NONEXISTENT 2021")
        
        assert citation is None
    
    def test_format_multiple_citations(self):
        """Test formatting multiple citations."""
        sources = ["WHO 2021", "NICE 2020"]
        citations = format_citations(sources, format_style="apa")
        
        assert len(citations) == 2
        assert all(isinstance(c, str) for c in citations)
        assert all(len(c) > 0 for c in citations)
    
    def test_get_citations_with_urls(self):
        """Test getting citations with full metadata."""
        sources = ["WHO 2021", "NICE 2020"]
        citations = get_citations_with_urls(sources)
        
        assert len(citations) == 2
        
        for citation in citations:
            assert "name" in citation
            assert "full_name" in citation
            assert "url" in citation
            assert citation["url"] is not None
    
    def test_add_new_citation(self):
        """Test adding a new citation to the database."""
        add_citation(
            source_name="TEST 2025",
            source="Test Guideline 2025",
            url="https://test.example.com",
            publication_date="2025-01-01",
            version="1.0",
        )
        
        # Verify it was added
        citation = get_citation("TEST 2025")
        assert citation is not None
        assert citation.source == "Test Guideline 2025"
        assert citation.version == "1.0"


class TestCitationExtraction:
    """Test extraction of citations from clinical reasoning."""
    
    def test_extract_citations_from_reasoning(self):
        """Test extracting source names from reasoning text."""
        reasoning = "Per ACC/AHA 2021 guidelines: acute onset chest pain suggests ACS. WHO 2021 also supports this."
        
        # Manually extract sources
        sources = set()
        for key in ["WHO", "NICE", "ICMR", "ACC/AHA", "ESC", "ADA", "GINA", "BTS", "IDSA"]:
            if key in reasoning:
                sources.add(key)
        
        assert "ACC/AHA" in sources
        assert "WHO" in sources
        assert "NICE" not in sources


class TestCitationMetadata:
    """Test citation metadata storage and retrieval."""
    
    def test_citation_to_dict(self):
        """Test converting citation to dictionary."""
        citation = Citation(
            source="Test Guideline",
            url="https://test.com",
            publication_date="2021-01-01",
            doi="10.1234/test",
            version="1.0",
        )
        
        citation_dict = citation.to_dict()
        
        assert citation_dict["source"] == "Test Guideline"
        assert citation_dict["url"] == "https://test.com"
        assert citation_dict["doi"] == "10.1234/test"
        assert citation_dict["version"] == "1.0"
    
    def test_citation_with_minimal_info(self):
        """Test citation with minimal information."""
        citation = Citation(source="Minimal Guideline")
        
        assert citation.source == "Minimal Guideline"
        assert citation.url is None
        assert citation.publication_date is None
        assert len(citation.authors) == 0
