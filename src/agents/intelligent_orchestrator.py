"""
Intelligent Multi-Agent Orchestrator for Text2SQL
Uses LLMs to make decisions about tool usage and query processing strategy
"""

import json
import re
from typing import Dict, Any, List, Optional
from openai import AzureOpenAI
import os
from utils.logging_config import get_logger
from utils.json_parser import extract_and_parse_json, validate_json_structure, create_fallback_response

logger = get_logger("text2sql.intelligent_orchestrator")

class IntelligentOrchestrator:
    """
    LLM-powered orchestrator that makes intelligent decisions about:
    - Which tools to use for a given query
    - How to approach complex queries
    - When to retry vs fail
    - How to combine multiple data sources
    """
    
    def __init__(self):
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        # Use the default/fast model for orchestration decisions
        self.orchestrator_model = os.getenv("DEFAULT_AGENT_MODEL", os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT", "gpt-4.1"))
        
    def analyze_query_intent(self, query: str, available_schema: str) -> Dict[str, Any]:
        """
        Use LLM to analyze query intent and determine processing strategy
        """
        system_prompt = """You are an intelligent database query orchestrator. Your job is to analyze natural language queries and determine the best strategy to process them.

Given a user query and database schema, you need to decide:
1. Query complexity (simple, medium, complex)
2. Which tables are likely needed
3. What type of analysis is required (aggregation, joins, filtering, etc.)
4. Whether the query can be answered with available data
5. Potential challenges or ambiguities

IMPORTANT: Respond with ONLY a valid JSON object, no additional text or explanations.

JSON Schema:
{
    "complexity": "simple|medium|complex",
    "confidence": 0.0-1.0,
    "likely_tables": ["table1", "table2"],
    "query_type": "select|aggregate|join|complex_analytical",
    "key_concepts": ["concept1", "concept2"],
    "challenges": ["challenge1", "challenge2"],
    "strategy": "direct_sql|decompose|clarify_with_user",
    "reasoning": "explanation of your analysis"
}"""

        user_prompt = f"""
Query: "{query}"

Available Database Schema:
{available_schema}

Analyze this query and determine the best processing strategy.
"""

        try:
            # Use appropriate parameters based on model type
            completion_params = {
                "model": self.orchestrator_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            
            # Handle different parameter requirements
            if "o4-mini" in self.orchestrator_model.lower() or "o1" in self.orchestrator_model.lower():
                completion_params["max_completion_tokens"] = 1000
                # o4-mini doesn't support temperature parameter
            else:
                completion_params["max_tokens"] = 1000
                completion_params["temperature"] = 0.1
                
            response = self.client.chat.completions.create(**completion_params)
            
            # Parse JSON response using robust parser
            content = response.choices[0].message.content.strip()
            logger.debug(f"Raw orchestrator response: {content[:300]}...")
            
            parsed_result = extract_and_parse_json(content, "object")
            if parsed_result and validate_json_structure(parsed_result, ["complexity", "confidence"]):
                logger.debug("Successfully parsed orchestrator response")
                return parsed_result
            else:
                logger.warning("Could not parse orchestrator response as valid JSON with required fields")
                return self._fallback_analysis(query)
                
        except Exception as e:
            logger.error(f"Error in query intent analysis: {e}")
            return self._fallback_analysis(query)
    
    def intelligent_schema_selection(self, query: str, all_tables: List[Dict], intent_analysis: Dict) -> List[Dict]:
        """
        Use LLM to intelligently select relevant tables based on semantic understanding
        """
        
        system_prompt = """You are a database schema expert. Given a natural language query and a list of database tables with their columns, identify which tables are most relevant to answer the query.

Consider:
1. Semantic relationships between query terms and table/column names
2. Likely joins needed between tables
3. Data flow for the requested analysis

Respond with a JSON array of table names in order of relevance:
["most_relevant_table", "second_table", "third_table"]

Only include tables that are actually needed for the query."""

        # Format table information for LLM
        table_info = []
        for table in all_tables:
            columns = [f"{col.name} ({col.data_type})" for col in table.columns]
            table_info.append(f"Table: {table.schema}.{table.name}\nColumns: {', '.join(columns)}")
        
        schema_text = "\n\n".join(table_info)
        
        user_prompt = f"""
Query: "{query}"

Query Analysis: {intent_analysis}

Available Tables:
{schema_text}

Select the most relevant tables for this query.
"""

        try:
            # Build completion parameters based on model
            completion_params = {
                "model": self.orchestrator_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            
            # Add parameters based on model type
            if "o4-mini" in self.orchestrator_model.lower() or "o1" in self.orchestrator_model.lower():
                completion_params["max_completion_tokens"] = 500
                # o4-mini doesn't support temperature parameter
            else:
                completion_params["max_tokens"] = 500
                completion_params["temperature"] = 0.1
                
            response = self.client.chat.completions.create(**completion_params)            
            content = response.choices[0].message.content.strip()
            logger.debug(f"Raw schema selection response: {content[:300]}...")
            
            # Parse JSON response using robust parser
            parsed_result = extract_and_parse_json(content, "array")
            if parsed_result and isinstance(parsed_result, list):
                logger.debug("Successfully parsed schema selection response")
                # Filter original tables to only include relevant ones
                relevant_tables = []
                for table_name in parsed_result:
                    for table in all_tables:
                        if f"{table.schema}.{table.name}" == table_name or table.name == table_name:
                            relevant_tables.append(table)
                            break
                return relevant_tables
            else:
                logger.warning("Could not parse schema selection response as valid JSON array")
                return all_tables[:5]  # Fallback to first 5 tables
                
        except Exception as e:
            logger.error(f"Error in intelligent schema selection: {e}")
            return all_tables[:5]  # Fallback
    def decide_processing_approach(self, query: str, intent_analysis: Dict, schema_context: str) -> Dict[str, Any]:
        """
        Decide how to process the query based on complexity and available tools
        OPTIMIZED: Uses rule-based model selection for speed and reliability
        """
        
        complexity = intent_analysis.get("complexity", "medium")
        confidence = intent_analysis.get("confidence", 0.5)
        strategy = intent_analysis.get("strategy", "direct_sql")
        
        # FAST: Rule-based model selection (no LLM call needed)
        model_selection = self._select_model_by_complexity(complexity, query)
        
        # FAST: Rule-based approach selection
        approach_selection = self._select_approach_by_complexity(complexity, confidence)
        
        # Only use LLM for very ambiguous cases (saves time and API calls)
        if confidence < 0.3 or complexity == "unknown":
            return self._llm_driven_approach_decision(query, intent_analysis, schema_context)
        
        # Return fast rule-based decision
        return {
            "approach": approach_selection["approach"],
            "llm_model": model_selection,
            "expected_iterations": approach_selection["iterations"],
            "confidence": confidence,
            "reasoning": f"Rule-based selection: {complexity} query -> {model_selection}"
        }
    
    def _select_model_by_complexity(self, complexity: str, query: str) -> str:
        """
        FAST: Rule-based model selection for speed and cost optimization
        """
        # Check for explicit complex indicators in query
        complex_indicators = [
            "ranking", "rank", "top 10", "top 20", "percentile",
            "window function", "partition", "recursive", "cte", "with",
            "pivot", "unpivot", "over", "row_number", "dense_rank",
            "analysis", "trends", "forecasting", "comprehensive",
            "year-over-year", "seasonal", "growth rate", "cohort"
        ]
        
        query_lower = query.lower()
        has_complex_indicators = any(indicator in query_lower for indicator in complex_indicators)        # Model selection logic using YOUR env variables
        if complexity == "complex" or has_complex_indicators:
            return os.getenv("COMPLEX_AGENT_MODEL", os.getenv("AZURE_OPENAI_O4MINI_DEPLOYMENT", "o4-mini"))
        else:  # simple or medium - use fast default model
            return os.getenv("DEFAULT_AGENT_MODEL", os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT", "gpt-4.1"))
    
    def _select_approach_by_complexity(self, complexity: str, confidence: float) -> Dict[str, Any]:
        """
        FAST: Rule-based approach selection
        """
        if complexity == "simple" and confidence > 0.7:
            return {"approach": "direct_generation", "iterations": 1}
        elif complexity == "complex":
            return {"approach": "iterative_refinement", "iterations": 3}
        elif confidence < 0.5:
            return {"approach": "clarify_requirements", "iterations": 0}
        else:
            return {"approach": "direct_generation", "iterations": 2}
    
    def _llm_driven_approach_decision(self, query: str, intent_analysis: Dict, schema_context: str) -> Dict[str, Any]:
        """
        FALLBACK: LLM-driven decision for ambiguous cases only
        """
        complexity = intent_analysis.get("complexity", "medium")
        
        # LLM-driven decision making (only for ambiguous cases)
        system_prompt = """You are a query processing strategist. Based on query analysis, decide the best approach to generate accurate SQL.

Your options:
1. "direct_generation" - Generate SQL directly with available schema
2. "iterative_refinement" - Generate SQL, test, refine based on errors
3. "decompose_query" - Break complex query into simpler parts
4. "clarify_requirements" - Query is ambiguous, need user clarification
5. "use_stored_procedure" - Query matches available stored procedure

For model selection:
- Use "gpt-4.1" for simple/medium queries, CRUD operations, basic aggregations
- Use "o4-mini" for complex analytical queries, window functions, rankings, forecasting

Respond with JSON:
{
    "approach": "one of the above options",
    "llm_model": "gpt-4.1|o4-mini",
    "expected_iterations": 1-3,
    "confidence": 0.0-1.0,
    "reasoning": "why this approach"
}"""

        user_prompt = f"""
Query: "{query}"
Intent Analysis: {json.dumps(intent_analysis, indent=2)}
Schema Context: {schema_context[:1000]}...

Decide the best processing approach and model.
"""

        try:
            # Build completion parameters based on model
            completion_params = {
                "model": self.orchestrator_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            
            # Add parameters based on model type
            if "o4-mini" in self.orchestrator_model.lower() or "o1" in self.orchestrator_model.lower():
                completion_params["max_completion_tokens"] = 500
                # o4-mini doesn't support temperature parameter
            else:
                completion_params["max_tokens"] = 500
                completion_params["temperature"] = 0.1
                
            response = self.client.chat.completions.create(**completion_params)            
            content = response.choices[0].message.content.strip()
            logger.debug(f"Raw approach decision response: {content[:300]}...")
            
            # Parse JSON response using robust parser
            parsed_result = extract_and_parse_json(content, "object")
            if parsed_result and validate_json_structure(parsed_result, ["approach", "confidence"]):
                logger.debug("Successfully parsed approach decision response")
                # Ensure model selection is correct
                if not parsed_result.get("llm_model"):
                    parsed_result["llm_model"] = self._select_model_by_complexity(complexity, query)
                return parsed_result
            else:
                logger.warning("Could not parse approach decision response as valid JSON")
                return self._fallback_approach(complexity)
                
        except Exception as e:
            logger.error(f"Error in LLM approach decision: {e}")
            return self._fallback_approach(complexity)
    
    def analyze_failure_and_retry(self, query: str, sql_attempts: List[str], errors: List[str], schema_context: str) -> Dict[str, Any]:
        """
        Analyze why queries failed and determine if/how to retry
        """
        
        system_prompt = """You are a SQL debugging expert. Analyze failed SQL queries and their errors to determine if and how to retry.

Consider:
1. Types of errors (syntax, logical, data issues)
2. Patterns in failed attempts
3. Whether the query is actually answerable with available data
4. What corrections might work

Respond with JSON:
{
    "should_retry": true/false,
    "retry_strategy": "fix_syntax|change_approach|simplify_query|get_more_context",
    "specific_fixes": ["fix1", "fix2"],
    "confidence": 0.0-1.0,
    "diagnosis": "what went wrong",
    "alternative_approach": "if retry won't work, suggest alternative"
}"""

        attempts_text = ""
        for i, (sql, error) in enumerate(zip(sql_attempts, errors)):
            attempts_text += f"Attempt {i+1}:\nSQL: {sql}\nError: {error}\n\n"

        user_prompt = f"""
Original Query: "{query}"

Failed Attempts:
{attempts_text}

Schema Context: {schema_context[:800]}...

Analyze these failures and recommend next steps.
"""

        try:
            # Build completion parameters based on model
            completion_params = {
                "model": self.orchestrator_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
              # Add parameters based on model type
            if "o4-mini" in self.orchestrator_model.lower() or "o1" in self.orchestrator_model.lower():
                completion_params["max_completion_tokens"] = 800
                # o4-mini doesn't support temperature parameter
            else:
                completion_params["max_tokens"] = 800
                completion_params["temperature"] = 0.1
                
            response = self.client.chat.completions.create(**completion_params)
            
            content = response.choices[0].message.content.strip()
            logger.debug(f"Raw failure analysis response: {content[:300]}...")
            
            # Parse JSON response using robust parser
            parsed_result = extract_and_parse_json(content, "object")
            if parsed_result and validate_json_structure(parsed_result, ["should_retry", "diagnosis"]):
                logger.debug("Successfully parsed failure analysis response")
                return parsed_result
            else:
                logger.warning("Could not parse failure analysis response as valid JSON")
                return create_fallback_response("failure")
                
        except Exception as e:
            logger.error(f"Error in failure analysis: {e}")
            return {"should_retry": False, "diagnosis": f"Analysis error: {e}"}
    
    def _fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback analysis when LLM fails"""
        return {
            "complexity": "medium",
            "confidence": 0.5,
            "likely_tables": [],
            "query_type": "select",            "key_concepts": [],
            "challenges": ["LLM analysis failed"],            "strategy": "direct_sql",
            "reasoning": "Using fallback analysis due to LLM error"
        }
    
    def _fallback_approach(self, complexity: str) -> Dict[str, Any]:
        """Fallback approach when LLM fails"""        
        return {
            "approach": "direct_generation",
            "llm_model": os.getenv("COMPLEX_AGENT_MODEL", "o4-mini") if complexity == "complex" else os.getenv("DEFAULT_AGENT_MODEL", "gpt-4.1"),
            "expected_iterations": 2,
            "confidence": 0.5,
            "reasoning": "Fallback approach due to LLM decision error"
        }
