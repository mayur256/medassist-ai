"""Citation service — format and track guideline sources."""

from typing import Optional
from datetime import datetime


class Citation:
    """Represents a citation to a clinical guideline."""
    
    def __init__(
        self,
        source: str,
        url: Optional[str] = None,
        publication_date: Optional[str] = None,
        authors: Optional[list[str]] = None,
        doi: Optional[str] = None,
        page_numbers: Optional[str] = None,
        version: Optional[str] = None,
    ):
        self.source = source
        self.url = url
        self.publication_date = publication_date
        self.authors = authors or []
        self.doi = doi
        self.page_numbers = page_numbers
        self.version = version
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "source": self.source,
            "url": self.url,
            "publication_date": self.publication_date,
            "authors": self.authors,
            "doi": self.doi,
            "page_numbers": self.page_numbers,
            "version": self.version,
        }
    
    def format_apa(self) -> str:
        """Format citation in APA style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown"
        year = self.publication_date.split("-")[0] if self.publication_date else "n.d."
        
        citation = f"{authors_str} ({year}). {self.source}."
        
        if self.doi:
            citation += f" https://doi.org/{self.doi}"
        elif self.url:
            citation += f" Retrieved from {self.url}"
        
        return citation
    
    def format_mla(self) -> str:
        """Format citation in MLA style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown"
        
        citation = f"{authors_str}. \"{self.source}.\""
        
        if self.publication_date:
            citation += f" {self.publication_date}."
        
        if self.doi:
            citation += f" https://doi.org/{self.doi}"
        elif self.url:
            citation += f" {self.url}"
        
        return citation
    
    def format_harvard(self) -> str:
        """Format citation in Harvard style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown"
        year = self.publication_date.split("-")[0] if self.publication_date else "n.d."
        
        citation = f"{authors_str}, {year}. {self.source}."
        
        if self.doi:
            citation += f" https://doi.org/{self.doi}"
        elif self.url:
            citation += f" Available at: {self.url}"
        
        return citation
    
    def format_chicago(self) -> str:
        """Format citation in Chicago style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown"
        
        citation = f"{authors_str}. {self.source}."
        
        if self.publication_date:
            citation += f" Accessed {self.publication_date}."
        
        if self.url:
            citation += f" {self.url}"
        
        return citation


# Global citation database
GUIDELINE_CITATIONS = {
    "WHO 2021": Citation(
        source="World Health Organization Clinical Guidelines 2021",
        url="https://www.who.int/publications",
        publication_date="2021-01-01",
        authors=["WHO"],
        version="2021",
    ),
    "WHO 2020": Citation(
        source="World Health Organization Clinical Guidelines 2020",
        url="https://www.who.int/publications",
        publication_date="2020-01-01",
        authors=["WHO"],
        version="2020",
    ),
    "NICE 2020": Citation(
        source="National Institute for Health and Care Excellence Guidelines 2020",
        url="https://www.nice.org.uk/guidance",
        publication_date="2020-01-01",
        authors=["NICE"],
        version="2020",
    ),
    "NICE 2019": Citation(
        source="National Institute for Health and Care Excellence Guidelines 2019",
        url="https://www.nice.org.uk/guidance",
        publication_date="2019-01-01",
        authors=["NICE"],
        version="2019",
    ),
    "ICMR 2020": Citation(
        source="Indian Council of Medical Research Guidelines 2020",
        url="https://www.icmr.gov.in/",
        publication_date="2020-01-01",
        authors=["ICMR"],
        version="2020",
    ),
    "ICMR 2019": Citation(
        source="Indian Council of Medical Research Guidelines 2019",
        url="https://www.icmr.gov.in/",
        publication_date="2019-01-01",
        authors=["ICMR"],
        version="2019",
    ),
    "ACC/AHA 2021": Citation(
        source="American College of Cardiology / American Heart Association Guidelines 2021",
        url="https://www.acc.org/",
        publication_date="2021-01-01",
        authors=["ACC", "AHA"],
        doi="10.1161/CIR",
        version="2021",
    ),
    "ACC/AHA 2020": Citation(
        source="American College of Cardiology / American Heart Association Guidelines 2020",
        url="https://www.acc.org/",
        publication_date="2020-01-01",
        authors=["ACC", "AHA"],
        version="2020",
    ),
    "ESC 2020": Citation(
        source="European Society of Cardiology Guidelines 2020",
        url="https://www.escardio.org/",
        publication_date="2020-01-01",
        authors=["ESC"],
        version="2020",
    ),
    "ESC 2019": Citation(
        source="European Society of Cardiology Guidelines 2019",
        url="https://www.escardio.org/",
        publication_date="2019-01-01",
        authors=["ESC"],
        version="2019",
    ),
    "IDSA 2019": Citation(
        source="Infectious Diseases Society of America Guidelines 2019",
        url="https://www.idsociety.org/",
        publication_date="2019-01-01",
        authors=["IDSA"],
        version="2019",
    ),
    "BTS 2018": Citation(
        source="British Thoracic Society Guidelines 2018",
        url="https://www.brit-thoracic.org.uk/",
        publication_date="2018-01-01",
        authors=["BTS"],
        version="2018",
    ),
    "GINA 2022": Citation(
        source="Global Initiative for Asthma Guidelines 2022",
        url="https://ginasthma.org/",
        publication_date="2022-01-01",
        authors=["GINA"],
        version="2022",
    ),
    "ADA 2022": Citation(
        source="American Diabetes Association Guidelines 2022",
        url="https://www.diabetes.org/",
        publication_date="2022-01-01",
        authors=["ADA"],
        version="2022",
    ),
}


def get_citation(source_name: str) -> Optional[Citation]:
    """Retrieve citation by source name."""
    return GUIDELINE_CITATIONS.get(source_name)


def format_citations(
    source_names: list[str],
    format_style: str = "apa"
) -> list[str]:
    """
    Format multiple citations in the specified style.
    
    Args:
        source_names: List of source names (e.g., "WHO 2021", "NICE 2020")
        format_style: Citation format ("apa", "mla", "harvard", "chicago")
    
    Returns:
        List of formatted citations
    """
    citations = []
    
    for source_name in source_names:
        citation = get_citation(source_name)
        if citation:
            if format_style == "apa":
                citations.append(citation.format_apa())
            elif format_style == "mla":
                citations.append(citation.format_mla())
            elif format_style == "harvard":
                citations.append(citation.format_harvard())
            elif format_style == "chicago":
                citations.append(citation.format_chicago())
            else:
                citations.append(citation.format_apa())  # Default to APA
    
    return citations


def get_citations_with_urls(source_names: list[str]) -> list[dict]:
    """
    Get citations with URLs for clinician reference.
    
    Args:
        source_names: List of source names
    
    Returns:
        List of citations with all metadata
    """
    citations = []
    
    for source_name in source_names:
        citation = get_citation(source_name)
        if citation:
            citations.append({
                "name": source_name,
                "full_name": citation.source,
                "url": citation.url,
                "publication_date": citation.publication_date,
                "doi": citation.doi,
                "version": citation.version,
            })
    
    return citations


def add_citation(
    source_name: str,
    source: str,
    url: Optional[str] = None,
    publication_date: Optional[str] = None,
    authors: Optional[list[str]] = None,
    doi: Optional[str] = None,
    version: Optional[str] = None,
):
    """Add a new citation to the database."""
    GUIDELINE_CITATIONS[source_name] = Citation(
        source=source,
        url=url,
        publication_date=publication_date,
        authors=authors,
        doi=doi,
        version=version,
    )
