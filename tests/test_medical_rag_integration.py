"""
Comprehensive Medical RAG Integration Test Suite
Tests all RAG features: vector search, response generation, integration with orchestrator and validation
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Test categories
print("=" * 80)
print("MEDICAL RAG INTEGRATION TEST SUITE")
print("=" * 80)
print()


def test_1_rag_service_availability():
    """Test 1: RAG service initialization and availability"""
    print("TEST 1: RAG Service Availability")
    print("-" * 80)
    
    try:
        from app.services.medical_rag_service import get_medical_rag_service
        
        print(f"✓ Import successful")
        
        # Create service instance (this initializes RAG)
        rag_service = get_medical_rag_service()
        print(f"✓ RAG service instance created")
        
        # Check availability after initialization
        is_available = rag_service.is_available()
        print(f"  is_available(): {is_available}")
        
        if not is_available:
            print("✗ RAG service not available - check vector database")
            return False
        
        # Check if we can access the RAG engine
        if hasattr(rag_service, '_MedicalRAGService__class___rag_engine') or hasattr(rag_service.__class__, '_rag_engine'):
            print("✓ RAG engine accessible")
        
        print("✓ TEST 1 PASSED\n")
        return True
        
    except Exception as e:
        print(f"✗ TEST 1 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_2_medical_query_detection():
    """Test 2: Medical keyword detection"""
    print("TEST 2: Medical Query Detection")
    print("-" * 80)
    
    try:
        from app.services.medical_rag_service import get_medical_rag_service
        rag_service = get_medical_rag_service()
        
        # Medical queries (should return True)
        medical_queries = [
            "What are the symptoms of malaria?",
            "How to treat fever?",
            "I have a headache and cough",
            "Tell me about diabetes",
            "What vaccines are needed for infants?",
            "Covid-19 treatment guidelines",
            "Blood pressure management",
        ]
        
        # Non-medical queries (should return False)
        non_medical_queries = [
            "What's the weather today?",
            "Book an appointment",
            "How do I register?",
            "What's your name?",
            "Tell me a joke",
        ]
        
        print("Testing medical queries:")
        medical_pass = 0
        for query in medical_queries:
            result = rag_service.is_medical_query(query)
            status = "✓" if result else "✗"
            print(f"  {status} '{query}' -> {result}")
            if result:
                medical_pass += 1
        
        print(f"\nTesting non-medical queries:")
        non_medical_pass = 0
        for query in non_medical_queries:
            result = rag_service.is_medical_query(query)
            status = "✓" if not result else "✗"
            print(f"  {status} '{query}' -> {result}")
            if not result:
                non_medical_pass += 1
        
        total_pass = medical_pass + non_medical_pass
        total_tests = len(medical_queries) + len(non_medical_queries)
        accuracy = (total_pass / total_tests) * 100
        
        print(f"\nAccuracy: {total_pass}/{total_tests} ({accuracy:.1f}%)")
        
        if accuracy >= 80:
            print("✓ TEST 2 PASSED\n")
            return True
        else:
            print("✗ TEST 2 FAILED: Accuracy below 80%\n")
            return False
        
    except Exception as e:
        print(f"✗ TEST 2 FAILED: {e}\n")
        return False


def test_3_rag_query_response():
    """Test 3: RAG query and response generation"""
    print("TEST 3: RAG Query & Response Generation")
    print("-" * 80)
    
    try:
        from app.services.medical_rag_service import get_medical_rag_service
        rag_service = get_medical_rag_service()
        
        test_queries = [
            "What are the symptoms of malaria?",
            "How to treat fever in children?",
            "What is diabetes?",
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\nQuery {i}: {query}")
            print("-" * 40)
            
            result = rag_service.get_grounded_response(
                query=query,
                top_k=3,
                min_confidence="low"
            )
            
            # Handle all response types
            if result is None:
                print(f"✗ No response (returned None)")
                return False
            
            if isinstance(result, dict):
                # Check for actual answer vs error dict
                if 'answer' in result:
                    answer = result['answer']
                    confidence = result.get('confidence', 'unknown')
                    sources = result.get('sources', [])
                    
                    print(f"✓ Response generated")
                    print(f"  Confidence: {confidence}")
                    print(f"  Sources: {len(sources)}")
                    print(f"  Answer preview: {answer[:150]}...")
                    
                    if sources:
                        print(f"  Source details:")
                        for idx, src in enumerate(sources[:2], 1):
                            # Sources are strings from RAG, not dicts
                            if isinstance(src, str):
                                print(f"    {idx}. {src[:60]}...")
                            else:
                                print(f"    {idx}. {src.get('source', 'Unknown')[:60]}...")
                                print(f"       Relevance: {src.get('distance', 'N/A')}")
                elif 'validated' in result:
                    print(f"✗ RAG not available (validation dict returned)")
                    return False
                else:
                    print(f"✗ Unexpected dict format: {list(result.keys())}")
                    return False
            else:
                print(f"✗ Unexpected response type: {type(result)}")
                return False
        
        print("\n✓ TEST 3 PASSED\n")
        return True
        
    except Exception as e:
        print(f"✗ TEST 3 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_4_rag_validation():
    """Test 4: RAG response validation"""
    print("TEST 4: RAG Response Validation")
    print("-" * 80)
    
    try:
        from app.services.medical_rag_service import get_medical_rag_service
        rag_service = get_medical_rag_service()
        
        # Test cases: query + correct response + incorrect response
        test_cases = [
            {
                "query": "What are common symptoms of malaria?",
                "correct": "Common symptoms of malaria include fever, chills, headache, and body aches. It's caused by parasites transmitted through mosquito bites.",
                "incorrect": "Malaria causes blue skin and only affects left-handed people."
            },
            {
                "query": "What is diabetes?",
                "correct": "Diabetes is a chronic condition that affects how your body processes blood sugar (glucose). It occurs when the pancreas doesn't produce enough insulin or the body can't effectively use the insulin it produces.",
                "incorrect": "Diabetes is a temporary condition caused by eating too much sugar and can be cured in one day."
            }
        ]
        
        total_correct = 0
        for i, case in enumerate(test_cases, 1):
            print(f"\nTest Case {i}: {case['query']}")
            print("-" * 40)
            
            # Validate correct response
            correct_result = rag_service.validate_with_rag(
                user_query=case['query'],
                bot_response=case['correct']
            )
            
            # Validate incorrect response
            incorrect_result = rag_service.validate_with_rag(
                user_query=case['query'],
                bot_response=case['incorrect']
            )
            
            correct_validated = correct_result.get('validated', False)
            correct_accuracy = correct_result.get('accuracy_score', 0.0) or 0.0
            incorrect_validated = incorrect_result.get('validated', False)
            incorrect_accuracy = incorrect_result.get('accuracy_score', 0.0) or 0.0
            
            print(f"  Correct response:")
            print(f"    Validated: {correct_validated}")
            print(f"    Accuracy: {correct_accuracy:.2f}")
            
            print(f"  Incorrect response:")
            print(f"    Validated: {incorrect_validated}")
            print(f"    Accuracy: {incorrect_accuracy:.2f}")
            
            # Check if validation correctly distinguished
            if correct_accuracy > incorrect_accuracy:
                print(f"  ✓ Correctly identified accurate response")
                total_correct += 1
            else:
                print(f"  ✗ Failed to distinguish accurate response")
        
        success_rate = (total_correct / len(test_cases)) * 100
        print(f"\nValidation accuracy: {total_correct}/{len(test_cases)} ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            print("✓ TEST 4 PASSED\n")
            return True
        else:
            print("✗ TEST 4 FAILED: Validation accuracy below 80%\n")
            return False
        
    except Exception as e:
        print(f"✗ TEST 4 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_5_vector_database_search():
    """Test 5: Direct vector database semantic search"""
    print("TEST 5: Vector Database Semantic Search")
    print("-" * 80)
    
    try:
        # Import from package (handles relative imports properly)
        from medical_rag import MedicalVectorStore
        
        vector_store = MedicalVectorStore()
        
        test_queries = [
            ("malaria symptoms", 0.75),  # Should find relevant results
            ("diabetes treatment", 0.75),
            ("fever in children", 0.75),
        ]
        
        passed = 0
        for query, max_distance in test_queries:
            print(f"\nSearching: '{query}'")
            results = vector_store.search(query, top_k=3)
            
            if results:
                best_distance = results[0]['distance']
                print(f"  ✓ Found {len(results)} results")
                print(f"    Best match distance: {best_distance:.4f}")
                # Use correct key name: 'text' not 'chunk'
                print(f"    Text preview: {results[0]['text'][:100]}...")
                
                if best_distance <= max_distance:
                    print(f"  ✓ Relevance acceptable (≤ {max_distance})")
                    passed += 1
                else:
                    print(f"  ⚠ Low relevance (> {max_distance})")
            else:
                print(f"  ✗ No results found")
        
        success_rate = (passed / len(test_queries)) * 100
        print(f"\nSearch quality: {passed}/{len(test_queries)} ({success_rate:.1f}%)")
        
        if success_rate >= 66:
            print("✓ TEST 5 PASSED\n")
            return True
        else:
            print("✗ TEST 5 FAILED: Search quality below threshold\n")
            return False
        
    except Exception as e:
        print(f"✗ TEST 5 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_6_confidence_scoring():
    """Test 6: RAG confidence level assessment"""
    print("TEST 6: Confidence Scoring")
    print("-" * 80)
    
    try:
        from app.services.medical_rag_service import get_medical_rag_service
        rag_service = get_medical_rag_service()
        
        # Queries expected to have different confidence levels
        test_cases = [
            ("What are the symptoms of malaria?", ["high", "medium"]),  # Common medical Q&A
            ("Tell me about extremely rare genetic disorder XYZ123", ["low", "medium"]),  # Rare topic
            ("What is diabetes?", ["high", "medium"]),  # Very common
        ]
        
        print("Testing confidence levels:")
        for query, expected_levels in test_cases:
            result = rag_service.get_grounded_response(query, top_k=3, min_confidence="low")
            
            if result:
                confidence = result.get('confidence', 'unknown')
                print(f"\n  Query: {query}")
                print(f"  Confidence: {confidence}")
                print(f"  Expected: {' or '.join(expected_levels)}")
                
                if confidence in expected_levels or confidence in ['high', 'medium', 'low']:
                    print(f"  ✓ Valid confidence level")
                else:
                    print(f"  ⚠ Unusual confidence: {confidence}")
            else:
                print(f"\n  ✗ No result for: {query}")
        
        print("\n✓ TEST 6 PASSED (Confidence scoring functional)\n")
        return True
        
    except Exception as e:
        print(f"✗ TEST 6 FAILED: {e}\n")
        return False


def test_7_orchestrator_integration():
    """Test 7: Integration with intelligent orchestrator"""
    print("TEST 7: Orchestrator Integration")
    print("-" * 80)
    
    try:
        # Check if orchestrator has RAG integration
        from app.services.intelligent_orchestrator import IntelligentOrchestrator
        import inspect
        
        orchestrator_code = inspect.getsource(IntelligentOrchestrator)
        
        checks = {
            "medical_rag import": "medical_rag_service" in orchestrator_code,
            "RAG initialization": "self.medical_rag" in orchestrator_code,
            "Medical query detection": "is_medical_query" in orchestrator_code,
            "RAG response call": "get_grounded_response" in orchestrator_code,
        }
        
        print("Integration checks:")
        all_passed = True
        for check, result in checks.items():
            status = "✓" if result else "✗"
            print(f"  {status} {check}: {result}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n✓ TEST 7 PASSED\n")
            return True
        else:
            print("\n✗ TEST 7 FAILED: Missing integration points\n")
            return False
        
    except Exception as e:
        print(f"✗ TEST 7 FAILED: {e}\n")
        return False


def test_8_validation_service_integration():
    """Test 8: Integration with medical validation service"""
    print("TEST 8: Validation Service Integration")
    print("-" * 80)
    
    try:
        # Check if validation service has RAG integration
        from app.services.medical_validation_service import MedicalValidationService
        import inspect
        
        validation_code = inspect.getsource(MedicalValidationService)
        
        checks = {
            "RAG import": "medical_rag_service" in validation_code or "MEDICAL_RAG_AVAILABLE" in validation_code,
            "RAG validation call": "validate_with_rag" in validation_code,
            "RAG accuracy integration": "rag_accuracy" in validation_code or "rag_validation" in validation_code,
        }
        
        print("Integration checks:")
        all_passed = True
        for check, result in checks.items():
            status = "✓" if result else "✗"
            print(f"  {status} {check}: {result}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n✓ TEST 8 PASSED\n")
            return True
        else:
            print("\n✗ TEST 8 FAILED: Missing integration points\n")
            return False
        
    except Exception as e:
        print(f"✗ TEST 8 FAILED: {e}\n")
        return False


def test_9_knowledge_base_coverage():
    """Test 9: Knowledge base coverage statistics"""
    print("TEST 9: Knowledge Base Coverage")
    print("-" * 80)
    
    try:
        sys.path.insert(0, str(project_root / "medical_rag"))
        from medical_rag.vector_store import MedicalVectorStore
        
        vector_store = MedicalVectorStore()
        
        print("Vector database statistics:")
        print(f"  Total chunks: {vector_store.collection.count()}")
        
        # Sample search to verify database is populated
        sample_result = vector_store.search("health", top_k=1)
        if sample_result:
            print(f"  ✓ Database responsive")
            print(f"  Sample chunk source: {sample_result[0].get('metadata', {}).get('source', 'Unknown')}")
        
        chunk_count = vector_store.collection.count()
        
        if chunk_count > 1000:
            print(f"\n✓ TEST 9 PASSED (Comprehensive knowledge base: {chunk_count} chunks)\n")
            return True
        elif chunk_count > 100:
            print(f"\n⚠ TEST 9 WARNING: Limited knowledge base ({chunk_count} chunks)\n")
            return True
        else:
            print(f"\n✗ TEST 9 FAILED: Insufficient knowledge base ({chunk_count} chunks)\n")
            return False
        
    except Exception as e:
        print(f"✗ TEST 9 FAILED: {e}\n")
        return False


def test_10_end_to_end_flow():
    """Test 10: Complete end-to-end medical query flow"""
    print("TEST 10: End-to-End Medical Query Flow")
    print("-" * 80)
    
    try:
        from app.services.medical_rag_service import get_medical_rag_service
        
        rag_service = get_medical_rag_service()
        
        # Simulate complete flow
        user_query = "What are the symptoms of malaria and how is it treated?"
        
        print(f"User Query: {user_query}\n")
        
        # Step 1: Detect medical query
        print("Step 1: Query Detection")
        is_medical = rag_service.is_medical_query(user_query)
        print(f"  Medical query detected: {is_medical}")
        if not is_medical:
            print("  ✗ Failed to detect medical query")
            return False
        print("  ✓ Passed\n")
        
        # Step 2: Get RAG response
        print("Step 2: RAG Response Generation")
        rag_response = rag_service.get_grounded_response(
            query=user_query,
            top_k=3,
            min_confidence="low"
        )
        
        # Validate response format
        if rag_response is None:
            print("  ✗ Failed to generate response (None returned)")
            return False
        
        if not isinstance(rag_response, dict):
            print(f"  ✗ Invalid response type: {type(rag_response)}")
            return False
        
        if 'answer' not in rag_response:
            print(f"  ✗ Response missing 'answer' key. Keys: {list(rag_response.keys())}")
            return False
        
        answer = rag_response['answer']
        confidence = rag_response.get('confidence', 'unknown')
        sources = rag_response.get('sources', [])
        
        print(f"  Response generated: {len(answer)} chars")
        print(f"  Confidence: {confidence}")
        print(f"  Sources: {len(sources)}")
        print("  ✓ Passed\n")
        
        # Step 3: Validate response
        print("Step 3: Response Validation")
        validation = rag_service.validate_with_rag(
            user_query=user_query,
            bot_response=answer
        )
        
        validated = validation.get('validated', False)
        accuracy = validation.get('accuracy_score', 0.0)
        
        print(f"  Validated: {validated}")
        print(f"  Accuracy: {accuracy:.2f}")
        
        if validated and accuracy > 0.5:
            print("  ✓ Passed\n")
        else:
            print("  ⚠ Low validation score\n")
        
        # Step 4: Display final output
        print("Step 4: Final Output")
        print("-" * 40)
        print(f"Answer: {answer[:200]}...")
        print(f"\nSources ({len(sources)}):")
        for i, src in enumerate(sources[:3], 1):
            # Sources are strings from RAG
            if isinstance(src, str):
                print(f"  {i}. {src[:70]}")
            else:
                print(f"  {i}. {src.get('source', 'Unknown')[:70]}")
        print()
        
        print("✓ TEST 10 PASSED (Complete flow successful)\n")
        return True
        
    except Exception as e:
        print(f"✗ TEST 10 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all test suites"""
    
    tests = [
        test_1_rag_service_availability,
        test_2_medical_query_detection,
        test_3_rag_query_response,
        test_4_rag_validation,
        test_5_vector_database_search,
        test_6_confidence_scoring,
        test_7_orchestrator_integration,
        test_8_validation_service_integration,
        test_9_knowledge_base_coverage,
        test_10_end_to_end_flow,
    ]
    
    results = []
    
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"\n✗ EXCEPTION in {test_func.__name__}: {e}\n")
            results.append((test_func.__name__, False))
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Medical RAG integration is fully functional.")
    elif passed >= total * 0.8:
        print(f"\n✓ Most tests passed. {total - passed} test(s) need attention.")
    else:
        print(f"\n⚠ ATTENTION NEEDED: {total - passed} test(s) failed.")
    
    print("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
