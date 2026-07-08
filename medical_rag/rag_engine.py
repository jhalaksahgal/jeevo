"""
Medical RAG Engine
Main interface for Retrieval-Augmented Generation with medical guidelines
"""
import os
import logging
from typing import List, Dict, Optional, Tuple
import openai
try:
    from .vector_store import MedicalVectorStore
except ImportError:
    from vector_store import MedicalVectorStore
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class MedicalRAGEngine:
    """
    RAG engine for medical question answering
    Retrieves relevant guidelines and generates responses
    """
    def __init__(
        self,
        vector_store: Optional[MedicalVectorStore] = None,
        model: str = "gpt-4o-mini",
        use_groq: bool = False
    ):
        """
        Initialize RAG engine
        Args:
            vector_store: MedicalVectorStore instance (creates new if None)
            model: OpenAI model to use
            use_groq: Use Groq instead of OpenAI
        """
        self.vector_store = vector_store or MedicalVectorStore()
        self.use_groq = use_groq or os.getenv("USE_GROQ", "false").lower() == "true"
        if self.use_groq:
            api_key = os.getenv("GROQ_API_KEY")
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            logger.info(f"Initialized RAG with Groq: {self.model}")
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            self.client = openai.OpenAI(api_key=api_key)
            self.model = model
            logger.info(f"Initialized RAG with OpenAI: {self.model}")
    def query(
        self,
        question: str,
        top_k: int = 5,
        source_filter: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 600
    ) -> Dict:
        """
        Query medical knowledge base and generate response
        Args:
            question: Medical question from user
            top_k: Number of relevant chunks to retrieve
            source_filter: Filter by source (e.g., "WHO")
            temperature: LLM temperature (lower = more factual)
            max_tokens: Maximum response length
        Returns:
            Dict with answer, sources, and metadata
        """
        try:
            logger.info(f"Retrieving guidelines for: {question}")
            retrieved_chunks = self.vector_store.search(
                query=question,
                top_k=top_k,
                source_filter=source_filter
            )
            if not retrieved_chunks:
                return {
                    "answer": "I don't have sufficient verified medical guidelines to answer this question. Please consult a healthcare professional.",
                    "sources": [],
                    "confidence": "low",
                    "retrieved_chunks": []
                }
            context = self._format_context(retrieved_chunks)
            sources = self._extract_sources(retrieved_chunks)
            logger.info("Generating response with LLM...")
            answer = self._generate_response(
                question=question,
                context=context,
                temperature=temperature,
                max_tokens=max_tokens
            )
            confidence = self._assess_confidence(retrieved_chunks)
            return {
                "answer": answer,
                "sources": sources,
                "confidence": confidence,
                "retrieved_chunks": len(retrieved_chunks),
                "context_length": len(context)
            }
        except Exception as e:
            logger.error(f"Error in RAG query: {e}")
            return {
                "answer": "An error occurred while processing your question. Please try again.",
                "sources": [],
                "confidence": "error",
                "error": str(e)
            }
    def _format_context(self, chunks: List[Dict]) -> str:
        """Format retrieved chunks into context for LLM"""
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk['metadata'].get('source', 'Unknown')
            text = chunk['text']
            context_parts.append(f"[Source {i}: {source}]\n{text}\n")
        return "\n".join(context_parts)
    def _extract_sources(self, chunks: List[Dict]) -> List[str]:
        """Extract unique sources from retrieved chunks"""
        sources = set()
        for chunk in chunks:
            source = chunk['metadata'].get('source', 'Unknown')
            sources.add(source)
        return sorted(list(sources))
    def _generate_response(
        self,
        question: str,
        context: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate response using LLM with retrieved context"""
        system_prompt = """You are a medical assistant providing information based ONLY on official medical guidelines.
CRITICAL RULES:
1. Answer ONLY using information from the provided guideline excerpts
2. If guidelines don't contain the answer, say "This information is not available in the current guidelines"
3. ALWAYS cite which source you're using (WHO, ICMR, NIH, etc.)
4. Include medical disclaimers for serious conditions
5. Recommend consulting healthcare professionals
6. For emergencies, suggest calling emergency services (108 in India)
7. Never make up information or use knowledge outside the provided context
8. Be clear, empathetic, and use simple language
FORMAT:
- Start with direct answer
- Cite source in parentheses
- Include relevant details from guidelines
- End with appropriate recommendation/disclaimer"""
        user_prompt = f"""Official Medical Guidelines:
{context}
---
User Question: {question}
Based ONLY on the above official guidelines, provide a clear, accurate answer. Always cite which guideline you're using."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return "Unable to generate response. Please try again."
    def _assess_confidence(self, chunks: List[Dict]) -> str:
        """Assess confidence based on retrieval quality"""
        if not chunks:
            return "none"
        avg_distance = sum(chunk['distance'] for chunk in chunks) / len(chunks)
        if avg_distance < 0.5:
            return "high"
        elif avg_distance < 0.7:
            return "medium"
        else:
            return "low"
    def get_guideline_summary(self, condition: str) -> Dict:
        """Get comprehensive guideline summary for a condition"""
        query = f"Complete information about {condition}: symptoms, diagnosis, treatment, prevention"
        return self.query(
            question=query,
            top_k=10,
            temperature=0.2
        )
def main():
    """Test the RAG engine"""
    print("="*70)
    print("MEDICAL RAG ENGINE - INTERACTIVE TEST")
    print("="*70)
    print("\n1. Initializing vector store...")
    vector_store = MedicalVectorStore()
    print("2. Loading medical documents...")
    chunks = vector_store.load_documents()
    print(f"   ✅ Loaded {chunks} chunks")
    print("\n3. Initializing RAG engine...")
    rag = MedicalRAGEngine(vector_store=vector_store)
    print("\n" + "="*70)
    print("RAG ENGINE READY")
    print("="*70)
    test_questions = [
        "What is the first-line treatment for malaria?",
        "How should I treat fever in a child?",
        "What are the symptoms of diabetes?",
        "What medications are used for hypertension?",
        "Is aspirin safe for children with fever?"
    ]
    print("\nRunning test queries:\n")
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*70}")
        print(f"QUESTION {i}: {question}")
        print('='*70)
        result = rag.query(question, top_k=3)
        print(f"\n📊 METADATA:")
        print(f"   Confidence: {result['confidence']}")
        print(f"   Sources: {', '.join(result['sources'])}")
        print(f"   Retrieved Chunks: {result['retrieved_chunks']}")
        print(f"\n💬 ANSWER:")
        print(f"{result['answer']}")
    print("\n" + "="*70)
    print("✅ RAG ENGINE TEST COMPLETE")
    print("="*70)
    print("\nTo use in your project:")
    print("1. Import: from medical_rag.rag_engine import MedicalRAGEngine")
    print("2. Initialize: rag = MedicalRAGEngine()")
    print("3. Query: result = rag.query('your medical question')")
    print("="*70)
if __name__ == "__main__":
    main()
