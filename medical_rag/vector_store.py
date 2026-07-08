"""
Vector Store for Medical RAG
Manages embeddings and similarity search using ChromaDB
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import json
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
DEFAULT_VECTOR_DB = Path(__file__).parent / "vector_db"
class MedicalVectorStore:
    """Vector database for medical document retrieval"""
    def __init__(
        self,
        persist_directory: str = None,
        collection_name: str = "medical_guidelines",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """
        Initialize vector store
        Args:
            persist_directory: Directory to persist vector database (defaults to medical_rag/vector_db)
            collection_name: Name of the collection
            embedding_model: HuggingFace model for embeddings
        """
        if persist_directory is None:
            self.persist_directory = DEFAULT_VECTOR_DB
        else:
            self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(exist_ok=True)
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        try:
            self.collection = self.client.get_collection(name=collection_name)
            logger.info(f"Loaded existing collection: {collection_name}")
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "Medical guidelines from WHO, ICMR, NIH, MOH India"}
            )
            logger.info(f"Created new collection: {collection_name}")
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        logger.info("✅ Vector store initialized")
    def load_documents(self, documents_dir: str = "./documents") -> int:
        """
        Load all documents from directory and add to vector store
        Args:
            documents_dir: Directory containing medical documents
        Returns:
            Number of chunks added
        """
        documents_path = Path(documents_dir)
        if not documents_path.exists():
            logger.error(f"Documents directory not found: {documents_dir}")
            return 0
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        total_chunks = 0
        files_processed = 0
        for file_path in documents_path.glob("*.json"):
            if file_path.stat().st_size > 5 * 1024 * 1024:  
                logger.info(f"Skipping large file: {file_path.name}")
                continue
            logger.info(f"Processing: {file_path.name}")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if "qa_pairs" in data:
                    qa_pairs = data["qa_pairs"]
                    source = data.get("collection", file_path.stem)
                    logger.info(f"  Found {len(qa_pairs)} Q&A pairs")
                    for i, qa in enumerate(qa_pairs):
                        question = qa.get("question", "")
                        answer = qa.get("answer", "")
                        if question and answer:
                            text = f"Question: {question}\n\nAnswer: {answer}"
                            self._add_chunk(
                                text=text,
                                source=source,
                                chunk_id=f"{file_path.stem}_qa_{i}",
                                metadata={
                                    "file": file_path.name,
                                    "source": source,
                                    "type": "qa_pair",
                                    "question": question[:200],
                                    "chunk_index": i
                                }
                            )
                            total_chunks += 1
                    files_processed += 1
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}")
        for file_path in documents_path.glob("*.txt"):
            logger.info(f"Processing: {file_path.name}")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            source = file_path.stem.replace("_", " ")
            chunks = text_splitter.split_text(content)
            logger.info(f"  Split into {len(chunks)} chunks")
            for i, chunk in enumerate(chunks):
                self._add_chunk(
                    text=chunk,
                    source=source,
                    chunk_id=f"{file_path.stem}_{i}",
                    metadata={
                        "file": file_path.name,
                        "source": source,
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    }
                )
                total_chunks += 1
            files_processed += 1
        logger.info(f"✅ Loaded {total_chunks} chunks from {files_processed} documents")
        return total_chunks
    def _add_chunk(
        self,
        text: str,
        source: str,
        chunk_id: str,
        metadata: Dict
    ):
        """Add a single chunk to vector store"""
        try:
            embedding = self.embedding_model.encode(text).tolist()
            self.collection.add(
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata],
                ids=[chunk_id]
            )
        except Exception as e:
            logger.error(f"Error adding chunk {chunk_id}: {e}")
    def search(
        self,
        query: str,
        top_k: int = 5,
        source_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for relevant medical guidelines
        Args:
            query: Search query (medical question)
            top_k: Number of results to return
            source_filter: Filter by source (e.g., "WHO", "ICMR")
        Returns:
            List of relevant chunks with metadata
        """
        try:
            query_embedding = self.embedding_model.encode(query).tolist()
            where = None
            if source_filter:
                where = {"source": {"$contains": source_filter}}
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where
            )
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        "text": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i],
                        "source": results['metadatas'][0][i].get('source', 'Unknown')
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    def get_stats(self) -> Dict:
        """Get statistics about the vector store"""
        try:
            count = self.collection.count()
            return {
                "total_chunks": count,
                "collection_name": self.collection_name,
                "persist_directory": str(self.persist_directory)
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    def clear(self):
        """Clear all data from collection"""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(name=self.collection_name)
            logger.info("✅ Collection cleared")
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
if __name__ == "__main__":
    print("Initializing Medical Vector Store...")
    store = MedicalVectorStore()
    print("\nLoading documents...")
    chunks_added = store.load_documents()
    print("\nVector Store Stats:")
    stats = store.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("\n" + "="*60)
    print("Testing Search:")
    print("="*60)
    test_queries = [
        "What is the treatment for malaria?",
        "How to manage fever in children?",
        "Diabetes medication guidelines",
        "Hypertension treatment protocol"
    ]
    for query in test_queries:
        print(f"\nQuery: {query}")
        results = store.search(query, top_k=2)
        for i, result in enumerate(results, 1):
            print(f"\n  Result {i} (Distance: {result['distance']:.4f}):")
            print(f"  Source: {result['source']}")
            print(f"  Text: {result['text'][:200]}...")
    print("\n" + "="*60)
    print("✅ Vector store ready for use!")
    print("="*60)
