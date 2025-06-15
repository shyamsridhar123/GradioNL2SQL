"""
Error Correction Tool for Smolagents
Inspects error messages, adjusts queries, and retries on failure
"""

from smolagents import Tool
import os
import re
from openai import AzureOpenAI

class ErrorCorrectionTool(Tool):
    name = "error_corrector"
    description = """
    Analyzes SQL execution errors and generates corrected queries.
    Uses LLM to understand error messages and suggest fixes.
    """
    inputs = {
        "original_query": {
            "type": "string",
            "description": "The original SQL query that failed"
        },
        "error_message": {
            "type": "string",
            "description": "The error message from SQL execution"
        },
        "schema_info": {
            "type": "string",
            "description": "Relevant database schema information"
        }
    }
    output_type = "string"

    def __init__(self):
        super().__init__()
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
        )
        
    def forward(self, original_query: str, error_message: str, schema_info: str) -> str:
        """
        Analyze error and generate corrected SQL
        """
        try:
            # Use o4-mini for error correction (cost-effective for this task)
            model_deployment = os.getenv("AZURE_OPENAI_O4MINI_DEPLOYMENT", "gpt-4o-mini")
            
            system_prompt = """You are a SQL error correction specialist for Azure SQL Server.
            
Analyze the error message and generate a corrected SQL query.

Common error patterns and fixes:
- Invalid column name: Check schema and use correct column names
- Invalid object name: Verify table names exist in schema
- Syntax errors: Fix T-SQL syntax issues
- GROUP BY errors: When using aggregate functions, ALL non-aggregate columns in SELECT must be in GROUP BY
- Subquery column references: Columns referenced in subqueries must be properly grouped
- JOIN errors: Fix JOIN conditions and table aliases

CRITICAL GROUP BY RULES:
1. If SELECT has SUM(), COUNT(), AVG(), etc., then ALL other columns must be in GROUP BY
2. Columns used in subqueries that reference outer query columns must be carefully handled
3. When grouping by date parts, make sure all date expressions are consistent
4. For complex subqueries with correlated references, simplify or restructure the query

Return ONLY the corrected SQL query, no explanations."""

            user_prompt = f"""Original query that failed:
{original_query}

Error message:
{error_message}

Available schema:
{schema_info}

Generate the corrected SQL query:"""

            response = self.client.chat.completions.create(
                model=model_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=2000
            )
            
            corrected_query = response.choices[0].message.content.strip()
            
            # Clean up the response
            if corrected_query.startswith("```sql"):
                corrected_query = corrected_query.replace("```sql", "").replace("```", "").strip()
            
            return corrected_query
            
        except Exception as e:
            return f"Error in correction: {str(e)}"
    
    def _analyze_error_type(self, error_message: str) -> str:
        """
        Categorize the type of SQL error
        """
        error_lower = error_message.lower()
        
        if "invalid column name" in error_lower:
            return "column_error"
        elif "invalid object name" in error_lower:
            return "table_error"
        elif "syntax error" in error_lower:
            return "syntax_error"
        elif "aggregate" in error_lower or "group by" in error_lower:
            return "aggregate_error"
        elif "join" in error_lower:
            return "join_error"
        else:
            return "unknown_error"
