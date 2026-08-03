"""Integration tests for RAG with the full diagnosis workflow."""

import pytest
from unittest.mock import AsyncMock, patch

from app.models.request import DiagnoseRequest, PatientInfo
from app.orchestrator.graph import run_full


class TestRAGOrchestrator:
    """Test RAG integration in the full diagnosis orchestrator."""
    
    @pytest.mark.asyncio
    async def test_full_diagnosis_flow_with_rag(self):
        """Test complete diagnosis flow incorporating RAG."""
        request = DiagnoseRequest(
            patient=PatientInfo(
                age=52,
                gender="male",
                country="US",
                known_conditions=["hypertension", "diabetes"],
                allergies=["penicillin"]
            ),
            symptoms="Severe chest pain radiating to left arm with sweating for 2 hours"
        )
        
        # Mock all the LLM calls in the pipeline
        mock_ner_result = {
            "symptoms": ["chest pain", "sweating"],
            "duration": "2 hours",
            "severity": "severe",
            "timeline": []
        }
        
        mock_diagnosis_result = {
            "diagnoses": [
                {
                    "condition": "Acute Coronary Syndrome",
                    "confidence": 0.9,
                    "reasoning": "Acute onset substernal chest pain with diaphoresis in patient with cardiac risk factors"
                },
                {
                    "condition": "Myocardial Infarction",
                    "confidence": 0.85,
                    "reasoning": "Similar presentation, risk profile warrants urgent evaluation"
                }
            ],
            "suggested_tests": [
                {
                    "test": "12-lead ECG",
                    "reasoning": "Identify ST-elevation or other acute changes"
                },
                {
                    "test": "Troponin I/T",
                    "reasoning": "Confirms myocardial necrosis"
                }
            ],
            "guideline_citations": {
                "sources": ["ACC/AHA 2021", "ESC 2020"],
                "conditions_referenced": ["ACS", "MI"],
                "total_guidelines_used": 5
            }
        }
        
        mock_treatment_result = {
            "treatments": [
                "Immediate cardiology consultation",
                "Oxygen therapy if SpO2 < 94%",
                "Dual antiplatelet therapy (aspirin contraindicated)",
                "Beta-blocker for rate control",
                "ACE inhibitor"
            ],
            "guideline_citations": {
                "sources": ["ACC/AHA 2021"],
                "conditions_referenced": ["ACS"],
                "total_guidelines_used": 3
            }
        }
        
        mock_compliance_result = {
            "treatments": [
                "Immediate cardiology consultation",
                "Oxygen therapy",
                "P2Y12 inhibitor (clopidogrel, not aspirin)",
                "Beta-blocker",
                "ACE inhibitor"
            ],
            "red_flags": ["chest pain", "sweating"],
            "urgency_score": 5,
            "urgency_rationale": "Critical: Acute MI with cardiac risk factors requires immediate intervention"
        }
        
        with patch('app.services.ner_service.extract_entities') as mock_ner:
            with patch('app.services.rag_service.build_diagnosis_context') as mock_diag_rag:
                with patch('app.services.llm_service.query_llm_json') as mock_llm:
                    with patch('app.services.rag_service.build_treatment_context') as mock_treat_rag:
                        with patch('app.services.compliance_engine.apply_compliance') as mock_compliance:
                            
                            # Setup mocks
                            mock_ner.return_value = type('obj', (object,), {
                                'symptoms': mock_ner_result['symptoms'],
                                'duration': mock_ner_result['duration'],
                                'severity': mock_ner_result['severity'],
                                'timeline': mock_ner_result['timeline']
                            })()
                            
                            mock_diag_rag.return_value = {
                                "guidelines_text": "## Acute Coronary Syndrome\nTreat with antiplatelet therapy",
                                "citations": {"sources": ["ACC/AHA 2021"], "conditions_referenced": ["ACS"]},
                                "guideline_count": 3
                            }
                            
                            mock_treat_rag.return_value = {
                                "guidelines_text": "## ACS Treatment\nUse dual antiplatelet therapy",
                                "citations": {"sources": ["ACC/AHA 2021"], "conditions_referenced": ["ACS"]},
                                "guideline_count": 3
                            }
                            
                            mock_llm.side_effect = [
                                mock_diagnosis_result,  # First call: diagnosis
                                mock_treatment_result   # Second call: treatment
                            ]
                            
                            mock_compliance.return_value = mock_compliance_result
                            
                            # Run the full workflow
                            response = await run_full(request)
        
        # Verify response structure
        assert response.status == "complete"
        assert len(response.differential_diagnosis) > 0
        assert len(response.suggested_tests) > 0
        assert len(response.treatment_options) > 0
        assert len(response.red_flags) > 0
        assert response.urgency_score == 5
        
        # Verify RAG integration
        assert response.differential_diagnosis[0].condition == "Acute Coronary Syndrome"
        assert response.differential_diagnosis[0].confidence >= 0.8
        assert any("ECG" in t.test for t in response.suggested_tests)
        assert response.urgency_rationale != ""
    
    @pytest.mark.asyncio
    async def test_rag_respects_patient_country(self):
        """Test that RAG filters guidelines by patient's country."""
        request = DiagnoseRequest(
            patient=PatientInfo(
                age=35,
                gender="female",
                country="India",
                known_conditions=[],
                allergies=[]
            ),
            symptoms="High fever and body aches"
        )
        
        with patch('app.services.ner_service.extract_entities') as mock_ner:
            with patch('app.services.rag_service.build_diagnosis_context') as mock_diag_rag:
                with patch('app.services.llm_service.query_llm_json') as mock_llm:
                    with patch('app.services.rag_service.build_treatment_context') as mock_treat_rag:
                        with patch('app.services.compliance_engine.apply_compliance') as mock_compliance:
                            
                            mock_ner.return_value = type('obj', (object,), {
                                'symptoms': ["fever", "body aches"],
                                'duration': None,
                                'severity': None,
                                'timeline': []
                            })()
                            
                            # Track if country filtering was applied
                            build_diag_context_calls = []
                            
                            async def track_diag_context(*args, **kwargs):
                                build_diag_context_calls.append(kwargs)
                                return {
                                    "guidelines_text": "ICMR Guidelines",
                                    "citations": {},
                                    "guideline_count": 2
                                }
                            
                            mock_diag_rag.side_effect = track_diag_context
                            
                            mock_treat_rag.return_value = {
                                "guidelines_text": "",
                                "citations": {},
                                "guideline_count": 0
                            }
                            
                            mock_llm.side_effect = [
                                {
                                    "diagnoses": [{"condition": "Dengue", "confidence": 0.7, "reasoning": "Fever + arthralgia"}],
                                    "suggested_tests": []
                                },
                                {"treatments": []}
                            ]
                            
                            mock_compliance.return_value = {
                                "treatments": [],
                                "red_flags": [],
                                "urgency_score": 2,
                                "urgency_rationale": ""
                            }
                            
                            await run_full(request)
        
        # Verify country was passed to RAG context builder
        assert len(build_diag_context_calls) > 0
        assert build_diag_context_calls[0].get("country") == "India"


class TestRAGPerformance:
    """Test RAG performance and efficiency."""
    
    @pytest.mark.asyncio
    async def test_rag_retrieval_completes_within_timeout(self):
        """Test that RAG retrieval completes quickly."""
        import time
        
        from app.services.rag_service import build_diagnosis_context
        
        start_time = time.time()
        
        with patch('app.services.embedding_service.retrieve_relevant_guidelines',
                   new_callable=AsyncMock, return_value=[]):
            await build_diagnosis_context(
                symptoms=["chest pain"],
                patient_conditions=[],
                country="US"
            )
        
        elapsed = time.time() - start_time
        
        # RAG retrieval should complete in < 2 seconds
        assert elapsed < 2.0, f"RAG retrieval took {elapsed}s, should be < 2s"


class TestRAGQuality:
    """Test RAG output quality."""
    
    def test_format_guidelines_for_prompt_includes_all_fields(self):
        """Test that formatted guidelines include all necessary fields."""
        from app.services.rag_service import format_guidelines_for_prompt
        
        guidelines = [
            {
                "condition_name": "Hypertension",
                "chunk_type": "treatment",
                "content": "ACE inhibitors, Beta blockers, Calcium channel blockers",
                "source": "WHO 2021",
            },
            {
                "condition_name": "Hypertension",
                "chunk_type": "tests",
                "content": "Blood pressure measurement, ECG, Urinalysis",
                "source": "WHO 2021",
            },
            {
                "condition_name": "Hypertension",
                "chunk_type": "red_flags",
                "content": "Severe headache, vision changes, chest pain",
                "source": "WHO 2021",
            }
        ]
        
        result = format_guidelines_for_prompt(guidelines)
        
        # Verify all fields are present
        assert "Hypertension" in result
        assert "WHO 2021" in result
        assert "Treatment Guidelines" in result or "treatment" in result.lower()
        assert "Recommended Tests" in result or "tests" in result.lower()
        assert "Red Flags" in result or "red_flags" in result.lower()
        assert "ACE inhibitors" in result
        assert "Blood pressure" in result
    
    def test_citations_include_all_unique_sources(self):
        """Test that citations capture all unique sources."""
        from app.services.rag_service import format_citations
        
        guidelines = [
            {"source": "WHO 2021", "condition_name": "ACS"},
            {"source": "ACC/AHA 2021", "condition_name": "ACS"},
            {"source": "ESC 2020", "condition_name": "ACS"},
            {"source": "WHO 2021", "condition_name": "MI"},  # Duplicate
            {"source": "ICMR 2020", "condition_name": "MI"},
        ]
        
        citations = format_citations(guidelines)
        
        # Should have 4 unique sources
        assert len(citations["sources"]) == 4
        assert set(citations["sources"]) == {"WHO 2021", "ACC/AHA 2021", "ESC 2020", "ICMR 2020"}
        assert len(set(citations["conditions_referenced"])) == 2
