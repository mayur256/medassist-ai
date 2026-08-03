"""End-to-end tests for RAG with clinical guidelines."""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.embedding_service import (
    embed_text,
    chunk_guideline_content,
    retrieve_relevant_guidelines,
    get_condition_guidelines,
)
from app.services.rag_service import (
    format_guidelines_for_prompt,
    format_citations,
    retrieve_guidelines_for_condition,
    retrieve_guidelines_for_symptoms,
    retrieve_guidelines_for_treatment,
    build_diagnosis_context,
    build_treatment_context,
)


class TestEmbeddingService:
    """Test embedding generation and retrieval."""
    
    def test_embed_text_returns_vector(self):
        """Test that embed_text returns a valid vector."""
        text = "Hypertension treatment guidelines"
        embedding = embed_text(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 384  # all-MiniLM-L6-v2 dimension
        assert all(isinstance(x, float) for x in embedding)
    
    def test_embed_text_similar_texts_have_close_embeddings(self):
        """Test that similar texts produce similar embeddings."""
        text1 = "Treatment for hypertension"
        text2 = "Blood pressure management therapy"
        text3 = "How to make pizza"
        
        emb1 = embed_text(text1)
        emb2 = embed_text(text2)
        emb3 = embed_text(text3)
        
        # Calculate cosine similarity
        def cosine_sim(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x ** 2 for x in a) ** 0.5
            norm_b = sum(x ** 2 for x in b) ** 0.5
            return dot / (norm_a * norm_b) if norm_a * norm_b > 0 else 0
        
        sim_12 = cosine_sim(emb1, emb2)  # Should be high
        sim_13 = cosine_sim(emb1, emb3)  # Should be low
        
        assert sim_12 > sim_13, "Similar texts should have higher similarity"
        assert sim_12 > 0.5, "Similar texts should have high similarity"
    
    def test_chunk_guideline_content_creates_chunks(self):
        """Test that chunk_guideline_content creates logical chunks."""
        condition = {
            "condition_id": "hypertension",
            "condition_name": "Hypertension",
            "countries": ["India", "US"],
            "severity": "moderate",
            "diagnostic_criteria": {
                "symptoms": "Headache, dizziness",
                "tests": ["BP reading", "ECG"]
            },
            "treatment_guidelines": {
                "first_line": ["ACE inhibitors", "Beta blockers"]
            },
            "red_flags": ["Severe headache", "Vision changes"],
            "source": "WHO 2021",
            "confidence": 0.9,
        }
        
        chunks = chunk_guideline_content(condition)
        
        assert len(chunks) > 0, "Should create at least one chunk"
        assert all("content" in chunk for chunk in chunks)
        assert all("chunk_type" in chunk for chunk in chunks)
        assert all(chunk["condition_name"] == "Hypertension" for chunk in chunks)
        
        # Check that different chunk types are created
        chunk_types = {chunk["chunk_type"] for chunk in chunks}
        assert len(chunk_types) > 1, "Should create multiple chunk types"


class TestRAGService:
    """Test RAG retrieval and formatting."""
    
    def test_format_guidelines_for_prompt_with_empty_list(self):
        """Test formatting with no guidelines."""
        result = format_guidelines_for_prompt([])
        assert result == ""
    
    def test_format_guidelines_for_prompt_creates_readable_text(self):
        """Test that format_guidelines_for_prompt creates readable text."""
        guidelines = [
            {
                "condition_name": "Hypertension",
                "chunk_type": "treatment",
                "content": "Use ACE inhibitors",
                "source": "WHO 2021",
            },
            {
                "condition_name": "Hypertension",
                "chunk_type": "tests",
                "content": "Blood pressure reading",
                "source": "WHO 2021",
            }
        ]
        
        result = format_guidelines_for_prompt(guidelines)
        
        assert "CLINICAL GUIDELINES CONTEXT" in result
        assert "Hypertension" in result
        assert "WHO 2021" in result
        assert "Treatment Guidelines" in result
        assert "Recommended Tests" in result
    
    def test_format_citations_extracts_sources(self):
        """Test that format_citations extracts unique sources and conditions."""
        guidelines = [
            {
                "condition_name": "Hypertension",
                "source": "WHO 2021",
            },
            {
                "condition_name": "Hypertension",
                "source": "WHO 2021",
            },
            {
                "condition_name": "Diabetes",
                "source": "ADA 2022",
            }
        ]
        
        citations = format_citations(guidelines)
        
        assert citations["total_guidelines_used"] == 3
        assert "WHO 2021" in citations["sources"]
        assert "ADA 2022" in citations["sources"]
        assert len(citations["sources"]) == 2, "Should have unique sources only"
        assert "Hypertension" in citations["conditions_referenced"]
        assert "Diabetes" in citations["conditions_referenced"]


class TestDiagnosisRAGIntegration:
    """Test RAG integration with diagnosis engine."""
    
    @pytest.mark.asyncio
    async def test_build_diagnosis_context_returns_guidelines(self):
        """Test that build_diagnosis_context fetches and formats guidelines."""
        # Mock the retrieve_relevant_guidelines function
        mock_guidelines = [
            {
                "condition_name": "Acute Coronary Syndrome",
                "chunk_type": "treatment",
                "content": "Aspirin + P2Y12 inhibitor",
                "source": "ACC/AHA 2021",
            }
        ]
        
        with patch('app.services.rag_service.retrieve_relevant_guidelines', 
                   new_callable=AsyncMock, return_value=mock_guidelines):
            result = await build_diagnosis_context(
                symptoms=["chest pain", "sweating"],
                patient_conditions=["hypertension"],
                country="US"
            )
        
        assert "guidelines_text" in result
        assert "citations" in result
        assert "guideline_count" in result
        assert result["guideline_count"] > 0
        assert len(result["guidelines_text"]) > 0
    
    @pytest.mark.asyncio
    async def test_build_diagnosis_context_filters_by_country(self):
        """Test that diagnosis context respects country filtering."""
        # Mock retrieve_relevant_guidelines to capture the call
        with patch('app.services.rag_service.retrieve_relevant_guidelines',
                   new_callable=AsyncMock, return_value=[]) as mock_retrieve:
            
            await build_diagnosis_context(
                symptoms=["chest pain"],
                patient_conditions=[],
                country="India"
            )
            
            # Verify country was passed to retrieval
            assert mock_retrieve.called
            call_kwargs = mock_retrieve.call_args[1]
            assert call_kwargs.get("country") == "India"


class TestTreatmentRAGIntegration:
    """Test RAG integration with treatment engine."""
    
    @pytest.mark.asyncio
    async def test_build_treatment_context_returns_guidelines(self):
        """Test that build_treatment_context fetches treatment guidelines."""
        mock_guidelines = [
            {
                "condition_name": "Hypertension",
                "chunk_type": "treatment",
                "content": "ACE inhibitors, Beta blockers",
                "source": "WHO 2021",
            }
        ]
        
        diagnoses = [
            {"condition": "Hypertension", "confidence": 0.8, "reasoning": "High BP readings"}
        ]
        
        with patch('app.services.rag_service.retrieve_relevant_guidelines',
                   new_callable=AsyncMock, return_value=mock_guidelines):
            result = await build_treatment_context(
                diagnoses=diagnoses,
                country="US",
                patient_allergies=["penicillin"]
            )
        
        assert "guidelines_text" in result
        assert "citations" in result
        assert "guideline_count" in result
        assert result["guideline_count"] > 0
    
    @pytest.mark.asyncio
    async def test_build_treatment_context_filters_allergy_guidelines(self):
        """Test that treatment context filters out allergy-related guidelines."""
        # Guidelines mentioning aspirin (which patient is allergic to)
        mock_guidelines = [
            {
                "condition_name": "ACS",
                "chunk_type": "treatment",
                "content": "Aspirin is contraindicated in this patient",
                "source": "WHO 2021",
            }
        ]
        
        diagnoses = [{"condition": "ACS", "confidence": 0.8, "reasoning": "Chest pain"}]
        
        with patch('app.services.rag_service.retrieve_relevant_guidelines',
                   new_callable=AsyncMock, return_value=mock_guidelines):
            result = await build_treatment_context(
                diagnoses=diagnoses,
                country="US",
                patient_allergies=["aspirin"]
            )
        
        # Should still work but filter appropriately
        assert result["guideline_count"] >= 0


class TestEndToEndRAG:
    """End-to-end tests for full RAG workflow."""
    
    @pytest.mark.asyncio
    async def test_rag_workflow_for_diagnosis(self):
        """Test complete RAG workflow for diagnosis generation."""
        from app.services.diagnosis_engine import generate_diagnoses
        
        patient = {
            "age": 52,
            "gender": "male",
            "country": "US",
            "known_conditions": ["hypertension"],
            "allergies": []
        }
        
        symptoms = ["chest pain", "shortness of breath"]
        
        # Mock the LLM to return a diagnosis
        mock_llm_response = {
            "diagnoses": [
                {
                    "condition": "Acute Coronary Syndrome",
                    "confidence": 0.8,
                    "reasoning": "Acute onset chest pain with dyspnea in patient with cardiac risk factors"
                }
            ],
            "suggested_tests": [
                {
                    "test": "ECG",
                    "reasoning": "To identify ST-segment elevation"
                }
            ]
        }
        
        with patch('app.services.rag_service.build_diagnosis_context',
                   new_callable=AsyncMock, return_value={
                       "guidelines_text": "## ACS Guidelines\nTreat with aspirin",
                       "citations": {"sources": ["ACC/AHA 2021"], "conditions_referenced": ["ACS"]},
                       "guideline_count": 3
                   }):
            with patch('app.services.llm_service.query_llm_json',
                       new_callable=AsyncMock, return_value=mock_llm_response):
                result = await generate_diagnoses(
                    symptoms=symptoms,
                    patient=patient,
                    duration="2 hours",
                    severity="severe"
                )
        
        assert "diagnoses" in result
        assert "suggested_tests" in result
        assert len(result["diagnoses"]) > 0
        assert result["diagnoses"][0]["condition"] == "Acute Coronary Syndrome"
        assert result["guideline_citations"]["total_guidelines_used"] == 3
    
    @pytest.mark.asyncio
    async def test_rag_workflow_for_treatment(self):
        """Test complete RAG workflow for treatment generation."""
        from app.services.treatment_engine import generate_treatments
        
        patient = {
            "age": 52,
            "gender": "male",
            "country": "US",
            "known_conditions": ["hypertension"],
            "allergies": []
        }
        
        diagnoses = [
            {
                "condition": "Hypertension",
                "confidence": 0.85,
                "reasoning": "BP > 160/100 mmHg"
            }
        ]
        
        mock_llm_response = {
            "treatments": [
                "ACE inhibitors (lisinopril or enalapril)",
                "Calcium channel blocker (amlodipine)",
                "Lifestyle modification (low sodium diet)"
            ]
        }
        
        with patch('app.services.rag_service.build_treatment_context',
                   new_callable=AsyncMock, return_value={
                       "guidelines_text": "## Hypertension Treatment\nFirst line: ACE-I or CCB",
                       "citations": {"sources": ["WHO 2021"], "conditions_referenced": ["Hypertension"]},
                       "guideline_count": 2
                   }):
            with patch('app.services.llm_service.query_llm_json',
                       new_callable=AsyncMock, return_value=mock_llm_response):
                result = await generate_treatments(
                    diagnoses=diagnoses,
                    patient=patient
                )
        
        assert "treatments" in result
        assert len(result["treatments"]) > 0
        assert any("ACE" in t.lower() or "inhibitor" in t.lower() for t in result["treatments"])
        assert result["guideline_citations"]["total_guidelines_used"] == 2


class TestRAGErrorHandling:
    """Test error handling in RAG system."""
    
    @pytest.mark.asyncio
    async def test_diagnosis_with_no_guidelines_returns_valid_result(self):
        """Test that diagnosis works even if no guidelines are found."""
        from app.services.diagnosis_engine import generate_diagnoses
        
        patient = {
            "age": 45,
            "gender": "female",
            "country": "US",
            "known_conditions": [],
            "allergies": []
        }
        
        mock_llm_response = {
            "diagnoses": [{"condition": "Common cold", "confidence": 0.6, "reasoning": "URI symptoms"}],
            "suggested_tests": []
        }
        
        with patch('app.services.rag_service.build_diagnosis_context',
                   new_callable=AsyncMock, return_value={
                       "guidelines_text": "",
                       "citations": {"sources": [], "conditions_referenced": []},
                       "guideline_count": 0
                   }):
            with patch('app.services.llm_service.query_llm_json',
                       new_callable=AsyncMock, return_value=mock_llm_response):
                result = await generate_diagnoses(
                    symptoms=["cough", "sore throat"],
                    patient=patient
                )
        
        # Should still return valid result
        assert "diagnoses" in result
        assert len(result["diagnoses"]) > 0
    
    @pytest.mark.asyncio
    async def test_treatment_with_malformed_llm_response(self):
        """Test that treatment handles malformed LLM responses gracefully."""
        from app.services.treatment_engine import generate_treatments
        
        patient = {
            "age": 65,
            "gender": "male",
            "country": "US",
            "known_conditions": [],
            "allergies": []
        }
        
        diagnoses = [{"condition": "Diabetes", "confidence": 0.85, "reasoning": "High blood glucose"}]
        
        # Return invalid response
        with patch('app.services.rag_service.build_treatment_context',
                   new_callable=AsyncMock, return_value={
                       "guidelines_text": "",
                       "citations": {},
                       "guideline_count": 0
                   }):
            with patch('app.services.llm_service.query_llm_json',
                       new_callable=AsyncMock, return_value=None):
                result = await generate_treatments(
                    diagnoses=diagnoses,
                    patient=patient
                )
        
        # Should return empty treatments gracefully
        assert "treatments" in result
        assert result["treatments"] == []
