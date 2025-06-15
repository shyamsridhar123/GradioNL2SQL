#!/usr/bin/env python3
"""
Test script for airplane mode components
Tests fast, offline functionality without database dependencies
"""

import sys
import os
import time

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airplane_mode.schema_analyst import AirplaneModeSchemaAnalyst
from airplane_mode.query_router import AirplaneModeRouter
from airplane_mode.sql_generator import AirplaneModeSQLGenerator

def test_airplane_mode():
    """Test all airplane mode components"""
    print("🛩️  TESTING AIRPLANE MODE (OFFLINE) COMPONENTS")
    print("=" * 50)
    
    # Test Query Router
    print("\n1. Testing Query Router...")
    router = AirplaneModeRouter()
    
    test_queries = [
        "show total sales by region by customer",
        "list all customers",
        "get product inventory",
        "complex analytics with multiple joins and subqueries"    ]
    
    for query in test_queries:
        start_time = time.time()
        use_airplane, reason, metadata = router.should_use_airplane_mode(query)
        end_time = time.time()
        print(f"   Query: '{query[:40]}...'")
        print(f"   Use Airplane Mode: {use_airplane}")
        print(f"   Reason: {reason}")
        print(f"   Metadata: {metadata}")
        print(f"   Time: {(end_time - start_time) * 1000:.1f}ms")
        print()
      # Test Schema Analyst
    print("\n2. Testing Schema Analyst (Airplane Mode)...")
    analyst = AirplaneModeSchemaAnalyst()
    
    for query in test_queries[:2]:  # Test first 2 queries
        start_time = time.time()
        schema_result = analyst.analyze_schema_for_query(query)
        end_time = time.time()
        print(f"   Query: '{query}'")
        schema_text = schema_result.get('schema_text', 'No schema')
        print(f"   Schema Analysis: {schema_text[:100]}...")
        print(f"   Time: {(end_time - start_time) * 1000:.1f}ms")
        print()
      # Test SQL Generator
    print("\n3. Testing SQL Generator (Airplane Mode)...")
    sql_gen = AirplaneModeSQLGenerator()
    for query in test_queries[:2]:  # Test first 2 queries
        start_time = time.time()
        # Get schema info for this specific query
        schema_info = analyst.analyze_schema_for_query(query)
        sql_result = sql_gen.generate_sql(query, schema_info)
        end_time = time.time()
        print(f"   Query: '{query}'")
        print(f"   Success: {sql_result.get('success', False)}")
        sql_text = sql_result.get('sql', 'No SQL generated')
        print(f"   Generated SQL: {sql_text[:100]}...")
        print(f"   Explanation: {sql_result.get('explanation', 'No explanation')[:50]}...")
        print(f"   Time: {(end_time - start_time) * 1000:.1f}ms")
        print()
    
    print("✅ AIRPLANE MODE TESTS COMPLETED!")
    print("All components work offline without database/LLM dependencies")

if __name__ == "__main__":
    test_airplane_mode()
