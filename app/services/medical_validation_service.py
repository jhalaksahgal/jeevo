import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
try:
    from app.services.medical_rag_service import get_medical_rag_service
    MEDICAL_RAG_AVAILABLE = True
except ImportError:
    MEDICAL_RAG_AVAILABLE = False
logger = logging.getLogger(__name__)
class ValidationResult(BaseModel):
    """Result of medical response validation"""
    risk_level: str  
    confidence_score: float
    requires_escalation: bool
    validation_message: str
    high_risk_keywords_detected: List[str] = []
    emergency_keywords_detected: List[str] = []
    verified_claims: List[str] = []
    contradicted_claims: List[str] = []
    accuracy_score: Optional[float] = None
    appropriateness_score: Optional[float] = None
    semantic_confidence: Optional[float] = None
    sources_used: List[str] = []
    fact_checks: List[Dict[str, Any]] = []
    escalation_trigger: Optional[str] = None
class MedicalValidationService:
    """Service to validate medical responses for safety and risk"""
    EMERGENCY_KEYWORDS = [
        "emergency", "urgent", "hospital", "ambulance", "cardiac", "heart attack",
        "stroke", "seizure", "unconscious", "bleeding", "severe bleeding",
        "poisoning", "overdose", "suicide", "self-harm", "death",
        "serious injury", "accident", "trauma",
        "chest pain", "shortness of breath", "difficulty breathing",
        "severe pain", "losing consciousness", "unresponsive"
    ]
    HIGH_RISK_KEYWORDS = [
        "pregnant", "pregnancy", "infant", "newborn", "baby",
        "cancer", "tumor", "malignant", "chemotherapy",
        "diabetes", "insulin", "kidney disease", "liver disease",
        "mental health", "depression", "anxiety", "psychosis",
        "addiction", "drug abuse", "alcohol abuse",
        "pain relief", "medication", "prescription",
        "high fever", "severe", "critical", "acute"
    ]
    MEDICAL_CONDITIONS = [
        "asthma", "diabetes", "hypertension", "blood pressure",
        "cholesterol", "thyroid", "arthritis", "migraine",
        "eczema", "psoriasis", "allergies"
    ]
    @staticmethod
    async def validate_response(
        db: AsyncSession,
        user_query: str,
        bot_response: str,
        confidence_score: float = 0.5,
        use_semantic_validation: bool = True,
        llm_model: str = "gpt-3.5-turbo"
    ) -> ValidationResult:
        """
        Validate a bot response against medical safety criteria using hybrid approach
        Args:
            db: Database session
            user_query: The original user query
            bot_response: The bot's response
            confidence_score: Confidence score of the response (0-1)
            use_semantic_validation: Enable semantic validation
            llm_model: LLM model to use
        Returns:
            ValidationResult with risk assessment
        """
        try:
            query_lower = user_query.lower() if user_query else ""
            response_lower = bot_response.lower() if bot_response else ""
            verified_claims = []
            contradicted_claims = []
            accuracy_score = confidence_score
            semantic_confidence = confidence_score
            sources_used = []
            fact_checks = []
            emergency_keywords = MedicalValidationService._find_keywords(
                query_lower + " " + response_lower,
                MedicalValidationService.EMERGENCY_KEYWORDS
            )
            if emergency_keywords:
                emergency_in_query = any(kw in query_lower for kw in MedicalValidationService.EMERGENCY_KEYWORDS)
                emergency_in_response = any(kw in response_lower for kw in MedicalValidationService.EMERGENCY_KEYWORDS)
                emergency_appropriate_responses = [
                    "emergency", "hospital", "ambulance", "call", "seek", "doctor", 
                    "urgent", "immediate", "911", "emt", "paramedic"
                ]
                has_appropriate_response = any(resp in response_lower for resp in emergency_appropriate_responses)
                if emergency_in_response and not emergency_in_query:
                    risk_level = "critical"
                elif emergency_in_query:
                    danger_patterns = [
                        "don't go", "avoid hospital", "don't call", "don't seek", 
                        "ignore", "it's nothing", "not serious", "just relax"
                    ]
                    explicitly_dangerous = any(pattern in response_lower for pattern in danger_patterns)
                    if explicitly_dangerous:
                        risk_level = "critical"
                    else:
                        risk_level = "high"
                else:
                    risk_level = "critical"
                return ValidationResult(
                    risk_level=risk_level,
                    confidence_score=1.0,
                    requires_escalation=True,
                    validation_message=f"Emergency situation detected: {', '.join(emergency_keywords[:3])}",
                    emergency_keywords_detected=emergency_keywords,
                    escalation_trigger="emergency_keywords",
                    semantic_confidence=1.0,
                    accuracy_score=1.0 if has_appropriate_response else 0.0,
                    appropriateness_score=1.0 if has_appropriate_response else 0.0
                )
            high_risk_keywords = MedicalValidationService._find_keywords(
                query_lower,
                MedicalValidationService.HIGH_RISK_KEYWORDS
            )
            medical_conditions = MedicalValidationService._find_keywords(
                query_lower,
                MedicalValidationService.MEDICAL_CONDITIONS
            )
            requires_escalation = False
            risk_level = "low"
            escalation_trigger = None
            danger_patterns = [
                ("aspirin", ["child", "children", "kid", "infant", "baby", "toddler", "newborn"]),
                ("antibiotic", ["viral", "virus", "cold", "flu", "dengue"]),
                ("paracetamol", ["overdose", "liver disease", "hepatitis", "cirrhosis"]),
                ("ibuprofen", ["kidney disease", "renal failure", "heart disease"]),
            ]
            dangerous_combo_found = False
            for medication, contraindicated_populations in danger_patterns:
                if medication in response_lower:
                    for pop in contraindicated_populations:
                        if pop in query_lower:
                            contradicted_claims.append(f"'{medication}' is contraindicated for {pop}")
                            risk_level = "high"
                            requires_escalation = True
                            escalation_trigger = "dangerous_medication_combination"
                            dangerous_combo_found = True
                            break
                if dangerous_combo_found:
                    break
            if not dangerous_combo_found:
                if high_risk_keywords and confidence_score < 0.7:
                    risk_level = "high"
                    requires_escalation = True
                    escalation_trigger = "high_risk_low_confidence"
                elif high_risk_keywords or medical_conditions:
                    if confidence_score < 0.5:
                        risk_level = "high"
                        requires_escalation = True
                        escalation_trigger = "medical_condition_low_confidence"
                    elif confidence_score >= 0.7:
                        good_practices = [
                            "paracetamol", "acetaminophen", "ibuprofen", "rest", "fluids", "water", "sleep",
                            "hydrate", "hydration", "consult doctor", "see doctor", "seek medical",
                            "nets", "mosquito", "vaccination", "vaccine", "preventive", "prevention"
                        ]
                        has_good_advice = any(practice in response_lower for practice in good_practices)
                        dangerous_patterns_in_response = [
                            "avoid doctor", "don't see doctor", "don't seek help",
                            "stop medication", "skip prescription", "don't treat"
                        ]
                        has_dangerous_advice = any(pattern in response_lower for pattern in dangerous_patterns_in_response)
                        if has_dangerous_advice:
                            risk_level = "high"
                            requires_escalation = True
                            escalation_trigger = "dangerous_advice_pattern"
                        elif has_good_advice:
                            risk_level = "low"
                        else:
                            risk_level = "medium"
                    else:
                        risk_level = "medium"
                elif confidence_score < 0.3:
                    risk_level = "high"
                    requires_escalation = True
                    escalation_trigger = "very_low_confidence"
            if use_semantic_validation and not requires_escalation:
                try:
                    from app.services.semantic_validation_engine import SemanticValidator
                    validator = SemanticValidator()
                    semantic_result = await validator.validate_response(
                        db=db,
                        user_query=user_query,
                        response_text=bot_response
                    )
                    verified_claims = semantic_result.get("verified_claims", [])
                    contradicted_claims.extend(semantic_result.get("contradicted_claims", []))
                    accuracy_score = semantic_result.get("accuracy_score", confidence_score)
                    semantic_confidence = semantic_result.get("confidence", confidence_score)
                    sources_used = semantic_result.get("sources_used", [])
                    if MEDICAL_RAG_AVAILABLE:
                        try:
                            rag_service = get_medical_rag_service()
                            if rag_service.is_available():
                                rag_validation = rag_service.validate_with_rag(
                                    user_query=user_query,
                                    bot_response=bot_response
                                )
                                if rag_validation.get('validated'):
                                    rag_accuracy = rag_validation.get('accuracy_score', 0.0)
                                    accuracy_score = (accuracy_score + rag_accuracy) / 2  
                                    rag_sources = rag_validation.get('rag_sources', [])
                                    sources_used.extend([f"RAG: {src}" for src in rag_sources])
                                    logger.info(f"✅ RAG validation - Accuracy: {rag_accuracy:.2f}, Sources: {len(rag_sources)}")
                        except Exception as e:
                            logger.warning(f"RAG validation error: {e}")
                    fact_checks = semantic_result.get("fact_checks", [])
                    if semantic_result.get("contradicted_claims"):
                        risk_level = "high"
                        requires_escalation = True
                        escalation_trigger = "contradictions_detected"
                    elif accuracy_score < 0.5:
                        risk_level = "high"
                        requires_escalation = True
                        escalation_trigger = "low_accuracy_response"
                    elif accuracy_score > 0.7 and not contradicted_claims and verified_claims:
                        risk_level = "low"
                        requires_escalation = False
                        escalation_trigger = None
                except Exception as e:
                    logger.warning(f"Semantic validation failed (non-blocking): {e}")
            validation_message = "Response is appropriate"
            if requires_escalation:
                if escalation_trigger == "emergency_keywords":
                    validation_message = f"Emergency: {', '.join(emergency_keywords[:2])}"
                elif escalation_trigger == "dangerous_medication_combination":
                    validation_message = f"Dangerous medication advice: {', '.join(contradicted_claims[:2])}"
                elif escalation_trigger == "contradictions_detected":
                    validation_message = f"Contradictions found: {', '.join(contradicted_claims[:2])}"
                elif escalation_trigger == "low_accuracy_response":
                    validation_message = "Low accuracy response - requires review"
                elif escalation_trigger == "high_risk_low_confidence":
                    validation_message = f"High-risk with low confidence"
                elif escalation_trigger == "very_low_confidence":
                    validation_message = "Very low confidence"
                elif escalation_trigger == "medical_condition_low_confidence":
                    validation_message = "Medical condition with low confidence"
            logger.info(
                f"[VALIDATION] Query: '{user_query[:40]}...' | "
                f"Risk: {risk_level} | Escalate: {requires_escalation} | "
                f"Confidence: {confidence_score}"
            )
            return ValidationResult(
                risk_level=risk_level,
                confidence_score=confidence_score,
                requires_escalation=requires_escalation,
                validation_message=validation_message,
                high_risk_keywords_detected=high_risk_keywords + medical_conditions,
                emergency_keywords_detected=emergency_keywords,
                verified_claims=verified_claims,
                contradicted_claims=contradicted_claims,
                accuracy_score=accuracy_score,
                appropriateness_score=accuracy_score,
                semantic_confidence=semantic_confidence,
                sources_used=sources_used,
                fact_checks=fact_checks,
                escalation_trigger=escalation_trigger
            )
        except Exception as e:
            logger.error(f"Error validating response: {e}")
            return ValidationResult(
                risk_level="high",
                confidence_score=0.0,
                requires_escalation=True,
                validation_message=f"Validation error: {str(e)}",
                high_risk_keywords_detected=[],
                emergency_keywords_detected=[],
                escalation_trigger="validation_error"
            )
    @staticmethod
    def _find_keywords(text: str, keyword_list: List[str]) -> List[str]:
        """Find keywords present in text"""
        found = []
        for keyword in keyword_list:
            if keyword in text:
                found.append(keyword)
        return found
