import sys
import os
from pathlib import Path

sys.path.append('src')
from agents.intelligent_agent import IntelligentText2SQLAgent
from utils.logging_config import setup_logging, get_logger
import time

# Setup logging with absolute path
log_file = Path(__file__).parent / "logs" / "complex_query_test.log"
setup_logging(log_level="DEBUG", log_file=str(log_file))
logger = get_logger("test_complex_query")

print('Testing medium complex query orchestration...')
logger.info("Starting complex query test")
agent = IntelligentText2SQLAgent()

query = 'give me top 10 customers by sales'
print(f'Query: {query}')
logger.info(f"Running query: {query}")

start = time.time()
result = agent.process_query_mode(query)
end = time.time()

print(f'\nTime: {end-start:.2f}s')
print(f'Success: {result.get("success", False)}')
print(f'Approach: {result.get("approach", "unknown")}')
print(f'SQL: {result.get("sql", "")[:200]}...')
print(f'Log: {result.get("log", "")}')

logger.info(f"Query completed in {end-start:.2f}s")
logger.info(f"Result: success={result.get('success', False)}, approach={result.get('approach', 'unknown')}")

# Check if there are any error details
if 'error' in result:
    print(f'Error: {result["error"]}')
    logger.error(f"Query failed: {result['error']}")
else:
    logger.info("Query completed successfully")
