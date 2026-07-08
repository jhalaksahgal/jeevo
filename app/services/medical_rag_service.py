"""
Medical RAG Service Integration
Wraps RAG engine for use in Jeevo's medical validation pipeline
"""
import logging
from typing import Dict, Optional, List
import sys
import asyncio
from pathlib import Path
medical_rag_path = Path(__file__).parent.parent.parent / "medical_rag"
if str(medical_rag_path) not in sys.path:
    sys.path.insert(0, str(medical_rag_path))
logger = logging.getLogger(__name__)
MEDICAL_RAG_AVAILABLE = False
class MedicalRAGService:
    """Service for grounded medical responses using RAG"""
    _instance = None
    _rag_engine = None
    _initialized = False
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __init__(self):
        """Singleton initialization"""
        if not self._initialized:
            self._initialize_rag()
            self.__class__._initialized = True
    def _initialize_rag(self):
        """Initialize RAG engine (lazy loading)"""
        global MEDICAL_RAG_AVAILABLE
        try:
            from medical_rag.rag_engine import MedicalRAGEngine
            self.__class__._rag_engine = MedicalRAGEngine()
            MEDICAL_RAG_AVAILABLE = True
            logger.info("✅ Medical RAG engine initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG engine: {e}")
            self.__class__._rag_engine = None
            MEDICAL_RAG_AVAILABLE = False
    def is_available(self) -> bool:
        """Check if RAG system is available"""
        return self.__class__._rag_engine is not None and MEDICAL_RAG_AVAILABLE
    async def get_grounded_response(
        self,
        query: str,
        top_k: int = 3,
        min_confidence: str = "low"
    ) -> Optional[Dict]:
        """
        Get grounded medical response from RAG system
        Args:
            query: User's medical question
            top_k: Number of relevant documents to retrieve
            min_confidence: Minimum confidence level required
        Returns:
            Dict with answer, confidence, sources, or None if unavailable
        """
        if not self.is_available():
            logger.warning("RAG engine not available")
            return None
        try:
            result = await asyncio.to_thread(self._rag_engine.query, query, top_k=top_k)
            confidence_levels = {"low": 0, "medium": 1, "high": 2}
            if confidence_levels.get(result['confidence'], 0) < confidence_levels.get(min_confidence, 0):
                logger.info(f"RAG confidence {result['confidence']} below threshold {min_confidence}")
                return None
            return result
        except Exception as e:
            logger.error(f"Error getting RAG response: {e}")
            return None
    async def validate_with_rag(
        self,
        user_query: str,
        bot_response: str
    ) -> Dict:
        """
        Validate a bot response against RAG knowledge base
        Args:
            user_query: User's original question
            bot_response: Bot's generated response
        Returns:
            Dict with validation results
        """
        if not self.is_available():
            return {
                "validated": False,
                "reason": "RAG unavailable",
                "accuracy_score": None
            }
        try:
            rag_result = await self.get_grounded_response(user_query, top_k=2)
            if not rag_result:
                return {
                    "validated": False,
                    "reason": "No RAG response",
                    "accuracy_score": None
                }
            rag_answer_lower = rag_result['answer'].lower()
            bot_response_lower = bot_response.lower()
            rag_words = set(word for word in rag_answer_lower.split() if len(word) > 4)
            bot_words = set(word for word in bot_response_lower.split() if len(word) > 4)
            overlap = rag_words.intersection(bot_words)
            accuracy = len(overlap) / len(rag_words) if rag_words else 0.0
            return {
                "validated": True,
                "accuracy_score": accuracy,
                "rag_confidence": rag_result['confidence'],
                "rag_sources": rag_result['sources'],
                "matching_terms": list(overlap)[:10],
                "reason": f"Validated against {len(rag_result['sources'])} sources"
            }
        except Exception as e:
            logger.error(f"Error validating with RAG: {e}")
            return {
                "validated": False,
                "reason": f"Validation error: {str(e)}",
                "accuracy_score": None
            }
    def is_medical_query(self, query: str) -> bool:
        """
        Check if query is medical using simple keyword matching
        Args:
            query: User query
        Returns:
            True if likely medical query
        """
        medical_keywords = [
            "fever", "pain", "headache", "cough", "cold", "flu",
            "diabetes", "blood pressure", "hypertension", "malaria",
            "diarrhea", "vomiting", "nausea", "infection", "disease",
            "medicine", "medication", "treatment", "doctor", "hospital",
            "symptoms", "diagnosis", "illness", "sick", "health",
            "pregnant", "pregnancy", "baby", "child", "vaccine",
            "injury", "wound", "bleeding", "allergy", "asthma"
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in medical_keywords)
_medical_rag_service = None
def get_medical_rag_service() -> MedicalRAGService:
    """Get singleton MedicalRAGService instance"""
    global _medical_rag_service
    if _medical_rag_service is None:
        _medical_rag_service = MedicalRAGService()
    return _medical_rag_service
