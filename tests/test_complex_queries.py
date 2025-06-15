"""
Test script for Text2SQL application with complex queries
Run this to test various query complexities and validate functionality
"""

import sys
import os
import time

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from agents.smolagent import Text2SQLAgent
from utils.logging_config import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO", log_file="logs/test_queries.log")
logger = get_logger("text2sql.test")

def test_query(agent, description, query, expected_complexity="medium"):
    """Test a single query and return results"""
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"QUERY: {query}")
    print(f"EXPECTED COMPLEXITY: {expected_complexity}")
    print(f"{'='*60}")
    
    try:
        start_time = time.time()
        result = agent.process_query_mode(query)
        end_time = time.time()
        
        print(f"✅ SUCCESS in {end_time - start_time:.2f}s")
        print(f"SQL Generated: {result.get('sql', 'No SQL')[:200]}...")
        print(f"Rows Returned: {len(result.get('results', []))}")
        print(f"Log: {result.get('log', 'No log')}")
        
        if result.get('error_corrected'):
            print(f"🔧 Error Correction Applied: {result['error_corrected']}")
            
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        logger.error(f"Test failed for query: {query[:100]}...", exc_info=True)
        return False

def main():
    """Run comprehensive tests"""
    logger.info("Starting Text2SQL test suite...")
    
    try:
        # Initialize agent
        print("Initializing Text2SQL Agent...")
        agent = Text2SQLAgent()
        print("✅ Agent initialized successfully")
        
        # Define test queries by complexity
        test_cases = [
            # Simple queries (should use o4-mini)
            {
                "description": "Simple Customer List",
                "query": "Show me all customers from New York",
                "complexity": "simple"
            },
            {
                "description": "Basic Product Search",
                "query": "What are the top 5 selling products this month?",
                "complexity": "simple"
            },
            {
                "description": "Recent Orders",
                "query": "List all orders placed in the last 7 days",
                "complexity": "simple"
            },
            
            # Medium complexity (border between models)
            {
                "description": "Sales by Region",
                "query": "Show total sales by region for the current year",
                "complexity": "medium"
            },
            {
                "description": "Customer Analysis",
                "query": "Find customers who haven't placed an order in 90 days",
                "complexity": "medium"
            },
            {
                "description": "Profit Margin Analysis",
                "query": "Which products have the highest profit margin?",
                "complexity": "medium"
            },
            
            # Complex queries (should use GPT-4.1)
            {
                "description": "Multi-table Revenue Analysis",
                "query": "Show me the total sales revenue by product category and region for the last quarter, including the number of orders and average order value, sorted by revenue descending",
                "complexity": "complex"
            },
            {
                "description": "Customer Segmentation",
                "query": "Identify high-value customers who have made more than 10 orders in the past 6 months, spent over $5000, and haven't placed an order in the last 30 days",
                "complexity": "complex"
            },
            {
                "description": "Month-over-Month Growth",
                "query": "Calculate the month-over-month revenue growth percentage for each product category over the past year",
                "complexity": "complex"
            },
            {
                "description": "Top Performing Customers with Ranking",
                "query": "Find customers who have spent more than the average customer spending in their region, show their rank within their region and percentage difference from the regional average",
                "complexity": "complex"
            }
        ]
        
        # Run tests
        passed = 0
        total = len(test_cases)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n\n🧪 TEST {i}/{total}")
            success = test_query(
                agent, 
                test_case["description"], 
                test_case["query"], 
                test_case["complexity"]
            )
            if success:
                passed += 1
            
            # Add delay between tests to avoid rate limiting
            time.sleep(2)
        
        # Summary
        print(f"\n\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print(f"⚠️  {total - passed} tests failed. Check logs for details.")
            
    except Exception as e:
        print(f"❌ Test suite failed to initialize: {str(e)}")
        logger.error("Test suite initialization failed", exc_info=True)

if __name__ == "__main__":
    main()
