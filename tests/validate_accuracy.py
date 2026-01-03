#!/usr/bin/env python3
"""Simple validation script to test accuracy improvements."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules import correctly."""
    print("Testing imports...")
    try:
        from app.services.query_engine import QueryEngine
        from app.services.advanced_query_engine import AdvancedQueryEngine
        from app.services.ultra_advanced_query_engine import UltraAdvancedQueryEngine
        from app.core.config import Settings
        from app.core.dependencies import get_query_engine, get_advanced_query_engine
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_config_defaults():
    """Test configuration defaults."""
    print("\nTesting configuration defaults...")
    try:
        from app.core.config import Settings
        
        # Create settings with minimal required fields
        settings = Settings(
            openai_api_key="test_key",
            neo4j_password="test_password"
        )
        
        tests = [
            ("max_context_length", settings.max_context_length, 8000),
            ("openai_max_tokens", settings.openai_max_tokens, 1000),
            ("min_similarity_threshold", settings.min_similarity_threshold, 0.7),
            ("openai_temperature", settings.openai_temperature, 0.0),
            ("enable_self_consistency", settings.enable_self_consistency, True),
            ("enable_answer_confidence", settings.enable_answer_confidence, True),
            ("enable_factuality_verification", settings.enable_factuality_verification, True),
            ("enable_hyde", settings.enable_hyde, True),
            ("enable_query_reformulation", settings.enable_query_reformulation, True),
            ("enable_context_compression", settings.enable_context_compression, True),
        ]
        
        all_passed = True
        for name, actual, expected in tests:
            if actual == expected:
                print(f"✓ {name}: {actual}")
            else:
                print(f"✗ {name}: expected {expected}, got {actual}")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ Config test error: {e}")
        return False

def test_query_engine_initialization():
    """Test that query engines can be initialized with new parameters."""
    print("\nTesting query engine initialization...")
    try:
        from app.services.query_engine import QueryEngine
        from unittest.mock import MagicMock
        
        mock_repo = MagicMock()
        mock_embed = MagicMock()
        
        # Test basic initialization
        engine = QueryEngine(
            repository=mock_repo,
            embedding_service=mock_embed,
            api_key="test_key",
            model="gpt-4-turbo-preview",
            top_k=10,
            rerank_top_k=5,
            max_context_length=8000,
            min_similarity_threshold=0.7,
        )
        
        assert engine.max_context_length == 8000, "max_context_length not set correctly"
        assert engine.min_similarity_threshold == 0.7, "min_similarity_threshold not set correctly"
        
        print("✓ QueryEngine initializes with new parameters")
        return True
    except Exception as e:
        print(f"✗ Query engine initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_advanced_query_engine_initialization():
    """Test advanced query engine initialization."""
    print("\nTesting advanced query engine initialization...")
    try:
        from app.services.advanced_query_engine import AdvancedQueryEngine
        from unittest.mock import MagicMock
        
        mock_repo = MagicMock()
        mock_embed = MagicMock()
        
        engine = AdvancedQueryEngine(
            repository=mock_repo,
            embedding_service=mock_embed,
            api_key="test_key",
            model="gpt-4-turbo-preview",
            max_context_length=8000,
            min_similarity_threshold=0.7,
        )
        
        assert engine.max_context_length == 8000
        assert engine.min_similarity_threshold == 0.7
        
        print("✓ AdvancedQueryEngine initializes with new parameters")
        return True
    except Exception as e:
        print(f"✗ Advanced query engine initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_system_prompt_citations():
    """Test that system prompts require citations."""
    print("\nTesting system prompt citation requirements...")
    try:
        import inspect
        from app.services.query_engine import QueryEngine
        
        # Get the _generate_answer method source
        source = inspect.getsource(QueryEngine._generate_answer)
        
        # Check for citation requirements
        has_critical = 'CRITICAL' in source
        has_must = 'MUST' in source or 'must' in source.lower()
        has_source_format = '[Source' in source
        
        if has_critical and has_source_format:
            print("✓ System prompt requires structured citations")
            return True
        else:
            print(f"✗ Citation requirements not found (CRITICAL: {has_critical}, [Source: {has_source_format})")
            return False
    except Exception as e:
        print(f"✗ System prompt test error: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("ACCURACY IMPROVEMENTS VALIDATION")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Config Defaults", test_config_defaults()))
    results.append(("QueryEngine Init", test_query_engine_initialization()))
    results.append(("AdvancedQueryEngine Init", test_advanced_query_engine_initialization()))
    results.append(("System Prompt Citations", test_system_prompt_citations()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All accuracy improvements validated successfully!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
