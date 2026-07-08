"""
Semantic Validation Engine
Extracts claims from LLM responses and validates them against medical sources
"""
import logging
import time
from typing import Dict, List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories import (
    ExtractedClaimRepository,
    FactCheckResultRepository,
    MedicalConditionRepository,
)
from app.services.medical_knowledge_base_service import medical_knowledge_base
from app.ai.llm import MedicalLLM
logger = logging.getLogger(__name__)
class ClaimExtractor:
    """
    Extracts testable medical claims from LLM responses.
    Uses LLM to parse and structure claims.
    """
    CLAIM_EXTRACTION_PROMPT = """Analyze this medical response and extract all medical claims.
For each claim, identify:
1. The claim text
2. The claim type (symptom, treatment, diagnosis, prevention, general_info, warning, etc.)
3. Whether it's testable against medical sources
Return as JSON:
{
    "claims": [
        {"text": "...", "type": "...", "testable": true/false, "confidence": 0.0-1.0},
        ...
    ]
}
Response to analyze:
{response}
Return ONLY valid JSON, no other text."""
    def __init__(self):
        try:
            self.llm = MedicalLLM()
            self.has_llm = True
        except:
            self.llm = None
            self.has_llm = False
    async def extract_claims(self, response_text: str) -> List[Dict]:
        """Extract medical claims from response"""
        try:
            if not response_text or len(response_text.strip()) < 10:
                return []
            if not self.has_llm:
                return self._extract_claims_simple(response_text)
            prompt = self.CLAIM_EXTRACTION_PROMPT.format(response=response_text)
            extraction_response = await self.llm.get_medical_response(prompt, language="en")
            import json
            try:
                data = json.loads(extraction_response)
                claims = data.get("claims", [])
                testable_claims = [c for c in claims if c.get("testable", False)]
                logger.info(
                    f"Extracted {len(testable_claims)} testable claims from response"
                )
                return testable_claims
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse claim extraction JSON: {extraction_response}")
                return []
        except Exception as e:
            logger.error(f"Error extracting claims: {e}")
            return self._extract_claims_simple(response_text)
    def _extract_claims_simple(self, response_text: str) -> List[Dict]:
        """Simple claim extraction without LLM"""
        claims = []
        keywords = {
            "treatment": ["take", "use", "drink", "apply", "inject", "medicine", "drug", "treatment", "therapy", "paracetamol", "aspirin", "antiviral"],
            "symptom": ["fever", "cough", "rash", "pain", "nausea", "dizzy", "transmitted"],
            "prevention": ["avoid", "prevent", "protect", "wash", "rest", "exercise", "nets", "repellent"],
            "warning": ["serious", "dangerous", "avoid", "emergency", "seek help", "if symptoms", "doctor", "no treatment"],
        }
        response_lower = response_text.lower()
        found_keywords = set()  
        for claim_type, words in keywords.items():
            for word in words:
                if word in response_lower and word not in found_keywords:
                    sentences = response_text.replace(", ", ".").split(". ")
                    for sent in sentences:
                        if word in sent.lower():
                            claim_text = sent.strip()
                            if claim_text and len(claim_text) > 5:
                                claims.append({
                                    "text": claim_text,
                                    "type": claim_type,
                                    "testable": True,
                                    "confidence": 0.7
                                })
                                found_keywords.add(word)
                                break
        return claims
class SemanticValidator:
    """
    Validates extracted claims against medical knowledge base.
    Performs fact-checking and identifies contradictions.
    """
    def __init__(self):
        self.kb = medical_knowledge_base
        self.claim_extractor = ClaimExtractor()
    async def validate_response(
        self,
        db: AsyncSession,
        response_text: str,
        user_query: str = "",
        llm_model: str = "gpt-4o-mini",
    ) -> Dict:
        """
        Comprehensive validation of LLM response against medical sources.
        Returns detailed validation report.
        """
        start_time = time.time()
        validation_report = {
            "validation_method": "source_based",
            "response_text": response_text,
            "user_query": user_query,
            "llm_model": llm_model,
            "extracted_claims": [],
            "fact_checks": [],
            "quality_metrics": {
                "total_claims": 0,
                "verified_claims": 0,
                "contradicted_claims": 0,
                "unverifiable_claims": 0,
                "concerning_claims": 0,
            },
            "scores": {
                "semantic_confidence": 0.5,
                "completeness": 0.5,
                "accuracy": 0.5,
                "appropriateness": 0.5,
            },
            "risk_assessment": {"level": "low", "triggers": []},
            "requires_escalation": False,
            "sources_used": [],
            "validation_duration_ms": 0,
        }
        try:
            claims = await self.claim_extractor.extract_claims(response_text)
            validation_report["extracted_claims"] = claims
            validation_report["quality_metrics"]["total_claims"] = len(claims)
            if not claims:
                validation_report["scores"]["completeness"] = 0.3
                logger.info("No testable claims extracted")
                return validation_report
            verified_count = 0
            contradicted_count = 0
            unverifiable_count = 0
            concerning_count = 0
            for claim in claims:
                check_result = await self._validate_claim(db, claim)
                validation_report["fact_checks"].append(check_result)
                if check_result["status"] == "verified":
                    verified_count += 1
                elif check_result["status"] == "contradicted":
                    contradicted_count += 1
                    validation_report["risk_assessment"]["triggers"].append(
                        f"Contradicted claim: {claim['text']}"
                    )
                elif check_result["status"] == "concerning":
                    concerning_count += 1
                    validation_report["risk_assessment"]["triggers"].append(
                        f"Concerning claim: {claim['text']}"
                    )
                else:
                    unverifiable_count += 1
            validation_report["quality_metrics"]["verified_claims"] = verified_count
            validation_report["quality_metrics"]["contradicted_claims"] = contradicted_count
            validation_report["quality_metrics"]["unverifiable_claims"] = unverifiable_count
            validation_report["quality_metrics"]["concerning_claims"] = concerning_count
            total = len(claims)
            if total > 0:
                accuracy = verified_count / total
                validation_report["scores"]["accuracy"] = accuracy
                validation_report["scores"]["semantic_confidence"] = (
                    verified_count / total
                )  
                if contradicted_count > 0:
                    validation_report["scores"]["appropriateness"] = max(
                        0, 0.7 - (contradicted_count / total * 0.5)
                    )
                else:
                    validation_report["scores"]["appropriateness"] = 0.8
            if contradicted_count > 0 or concerning_count >= 3:
                validation_report["risk_assessment"]["level"] = "high"
                validation_report["requires_escalation"] = True
            elif concerning_count > 0:
                validation_report["risk_assessment"]["level"] = "medium"
                validation_report["requires_escalation"] = True
            elif unverifiable_count > (total * 0.5):
                validation_report["risk_assessment"]["level"] = "medium"
            sources = await self.kb.get_sources(db)
            validation_report["sources_used"] = [s["name"] for s in sources[:5]]
            logger.info(
                f"Validation complete: verified={verified_count}, "
                f"contradicted={contradicted_count}, unverifiable={unverifiable_count}"
            )
        except Exception as e:
            logger.error(f"Error in semantic validation: {e}")
            validation_report["risk_assessment"]["level"] = "medium"
            validation_report["risk_assessment"]["triggers"].append(
                f"Validation error: {str(e)}"
            )
            validation_report["requires_escalation"] = True
        finally:
            validation_report["validation_duration_ms"] = int(
                (time.time() - start_time) * 1000
            )
        return validation_report
    async def _validate_claim(self, db: AsyncSession, claim: Dict) -> Dict:
        """Validate a single claim and return check result"""
        check_result = {
            "claim": claim["text"],
            "claim_type": claim.get("type", "unknown"),
            "status": "unverifiable",  
            "confidence": 0.0,
            "sources": [],
            "details": "",
        }
        try:
            claim_type = claim.get("type", "").lower()
            claim_text = claim["text"].lower()
            if claim_type == "symptom":
                is_verified, confidence, matches = await self.kb.verify_symptom(
                    db, claim_text
                )
                if is_verified:
                    check_result["status"] = "verified"
                    check_result["confidence"] = confidence
                    check_result["sources"] = matches
                else:
                    check_result["status"] = "unverifiable"
                    check_result["confidence"] = 0.2
            elif claim_type == "treatment":
                is_verified, confidence, matches = await self.kb.verify_treatment(
                    db, claim_text
                )
                if is_verified:
                    check_result["status"] = "verified"
                    check_result["confidence"] = confidence
                    check_result["sources"] = matches
                else:
                    check_result["status"] = "unverifiable"
                    check_result["confidence"] = 0.2
            elif claim_type == "prevention":
                is_verified, confidence, matches = await self.kb.verify_treatment(
                    db, claim_text
                )
                if is_verified:
                    check_result["status"] = "verified"
                    check_result["confidence"] = confidence
                else:
                    check_result["status"] = "unverifiable"
            elif claim_type in ["warning", "emergency"]:
                check_result["status"] = "concerning"
                check_result["confidence"] = 0.5
                check_result["details"] = "Emergency/warning claims require expert review"
            else:
                check_result["status"] = "unverifiable"
                check_result["confidence"] = 0.3
        except Exception as e:
            logger.error(f"Error validating claim: {e}")
            check_result["status"] = "concerning"
            check_result["details"] = f"Validation error: {str(e)}"
        return check_result
semantic_validator = SemanticValidator()
