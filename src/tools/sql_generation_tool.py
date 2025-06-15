"""
SQL Generation Tool for Smolagents
Converts user intent and schema context into safe, parameterized T-SQL
"""

from smolagents import Tool
import os
import json
from openai import AzureOpenAI
import sys

# Add parent directory to path to import utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.logging_config import get_logger

logger = get_logger("text2sql.tools.sql_generator")

class SQLGenerationTool(Tool):
    name = "sql_generator"
    description =    """
    Generates safe, parameterized T-SQL queries based on user natural language input 
    and relevant database schema information. Returns executable SQL with parameters.
    """
    inputs = {
        "user_query": {
            "type": "string",
            "description": "The user's natural language query"
        },
        "schema_info": {
            "type": "string", 
            "description": "Relevant database schema information from schema analyst"
        }
    }
    output_type = "string"

    def __init__(self):
        super().__init__()
        logger.debug("Initializing SQL Generation Tool...")
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
        )
        logger.debug("SQL Generation Tool initialized successfully")
        
    def forward(self, user_query: str, schema_info: str) -> str:
        """
        Generate SQL query from natural language and schema
        """
        logger.info(f"Generating SQL for query: {user_query[:100]}...")
        
        try:
            # Determine which model to use based on query complexity
            model_deployment = self._select_model(user_query)
            logger.debug(f"Selected model: {model_deployment}")            # Create system prompt for SQL generation
            system_prompt = """You are a SQL expert for Azure SQL Server T-SQL.

CRITICAL RULES:
1. ONLY use tables and columns that exist in the provided schema
2. DO NOT make up table or column names
3. Use exact table names with proper schema prefixes (e.g., SalesLT.Customer)
4. Generate only SELECT statements
5. Use direct values like "TOP 10", never parameters like "TOP(@param)"
6. If schema is incomplete, make reasonable assumptions using common table names like SalesLT.Customer, SalesLT.Product, SalesLT.SalesOrderHeader
7. Return ONLY the SQL query, no explanations

Schema format:
Table: schema.tablename
  - column: datatype NULL/NOT NULL [PK/FK markers]"""

            user_prompt = f"""Generate a T-SQL query for this request:
"{user_query}"

Available schema:
{schema_info}

Return only the SQL query."""
            
            response = self.client.chat.completions.create(
                model=model_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=1000
            )
            
            sql_query = response.choices[0].message.content
            
            if not sql_query:
                logger.warning("Empty response from LLM")
                return "-- Error: Empty response from LLM"
            
            logger.debug(f"Raw LLM response: {sql_query[:200]}...")
            
            # Clean up the response thoroughly
            sql_query = self._clean_sql_response(sql_query)
            
            logger.debug(f"Cleaned SQL: {sql_query[:200]}...")
            
            return sql_query
            
        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
            return f"-- Error generating SQL: {str(e)}"
    
    def _clean_sql_response(self, sql_response: str) -> str:
        """
        Clean and validate SQL response from LLM
        """
        if not sql_response:
            return "-- Error: Empty SQL response"
        
        # Remove null characters that cause HY090 errors
        sql_query = sql_response.replace('\x00', '')
        
        # Strip whitespace
        sql_query = sql_query.strip()
        
        # Remove markdown code blocks
        if sql_query.startswith("```sql"):
            sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
        elif sql_query.startswith("```"):
            sql_query = sql_query.replace("```", "").strip()
        
        # Remove any leading/trailing explanation text
        lines = sql_query.split('\n')
        sql_lines = []
        in_sql = False
        
        for line in lines:
            line_stripped = line.strip().upper()
            # Start capturing when we see SQL keywords
            if (line_stripped.startswith(('SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE')) or 
                in_sql):
                in_sql = True
                sql_lines.append(line)
            # Stop if we see explanation text after SQL
            elif in_sql and (line_stripped.startswith(('NOTE:', 'EXPLANATION:', 'THIS QUERY'))):
                break
        
        if sql_lines:
            sql_query = '\n'.join(sql_lines).strip()
          # Final validation
        if not sql_query or sql_query.startswith('--'):
            return "-- Error: No valid SQL found in response"
        
        # Ensure it ends properly (no trailing explanation)
        if sql_query and not sql_query.endswith(';'):
            # Remove any trailing explanation
            lines = sql_query.split('\n')
            for i in range(len(lines)-1, -1, -1):
                if lines[i].strip() and not lines[i].strip().upper().startswith(('--', 'NOTE', 'EXPLANATION')):
                    sql_query = '\n'.join(lines[:i+1])
                    break
        
        return sql_query
    
    def _select_model(self, user_query: str) -> str:
        """
        Select appropriate model based on query complexity using env variables
        DEFAULT_AGENT_MODEL (gpt-4.1) for simple/medium queries (fast, efficient)
        COMPLEX_AGENT_MODEL (o4-mini) for complex reasoning tasks (deep analysis)
        """
        query_lower = user_query.lower()
        
        # Complex reasoning indicators that benefit from complex model
        complex_reasoning_indicators = [
            "window function", "rank", "partition", "recursive", "cte", "with",
            "pivot", "unpivot", "over", "row_number", "dense_rank",
            "analysis", "cohort", "trend", "forecasting", "year-over-year",
            "seasonal", "comprehensive", "correlation", "statistical"        ]
        
        if any(indicator in query_lower for indicator in complex_reasoning_indicators):
            return os.getenv("COMPLEX_AGENT_MODEL", os.getenv("AZURE_OPENAI_O4MINI_DEPLOYMENT", "o4-mini"))
        else:
            return os.getenv("DEFAULT_AGENT_MODEL", os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT", "gpt-4.1"))
