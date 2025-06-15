"""
LLM Schema Analyst Tool - Intelligent and Agentic
Uses LLM to understand query semantics and intelligently route between models
"""

import os
import sys
import json
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple
from openai import AzureOpenAI

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.connection import DatabaseConnection
from database.config import DatabaseConfig
from database.schema_inspector import SchemaInspector
from utils.logging_config import get_logger

logger = get_logger("text2sql.llm_schema_analyst")

class LLMSchemaAnalystTool:
    """
    Intelligent LLM-powered schema analyst that:
    1. Uses LLM to understand query semantics (not keyword matching)
    2. Routes between GPT-4.1 (default/fast) and o1-mini (complex reasoning) 
    3. Makes intelligent decisions about relevant tables
    """
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        
        # Model routing configuration using env variables
        self.models = {
            "fast": os.getenv("DEFAULT_AGENT_MODEL", os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT", "gpt-4.1")),
            "complex": os.getenv("COMPLEX_AGENT_MODEL", os.getenv("AZURE_OPENAI_O4MINI_DEPLOYMENT", "o4-mini"))
        }
        
        # Cache for performance
        self._schema_cache = None
        self._analysis_cache = {}
        self._cache_expiry = 600  # 10 minutes
        logger.info("LLM Schema Analyst initialized with intelligent routing")
    
    def _get_database_schema(self) -> List[Any]:
        """Get database schema with caching and proper connection handling"""
        if self._schema_cache is not None:
            return self._schema_cache
            
        try:
            config = DatabaseConfig.from_env(use_managed_identity=False)
            # Use context manager for proper connection handling
            with DatabaseConnection(config) as db:
                inspector = SchemaInspector(db)
                tables = inspector.get_all_tables()
                
                self._schema_cache = tables
                logger.info(f"Schema cached with {len(tables)} tables")
                return tables
                
        except Exception as e:
            logger.error(f"Error getting database schema: {e}")
            return []
    
    def _analyze_query_complexity(self, query: str) -> Tuple[str, float, str]:
        """
        Intelligently analyze query complexity to determine optimal LLM routing
        Returns: (model_choice, confidence_score, reasoning)
        """
        query_lower = query.lower().strip()
        
        # Complex query indicators
        complex_indicators = {
            'joins': ['join', 'inner join', 'left join', 'right join', 'full join'],
            'subqueries': ['subquery', 'nested', 'exists', 'in (select'],
            'aggregations': ['group by', 'having', 'partition', 'window function'],
            'advanced_sql': ['case when', 'pivot', 'unpivot', 'recursive', 'cte'],
            'multiple_conditions': ['and.*or', 'between.*and', 'multiple where'],
            'calculations': ['calculate', 'compute', 'formula', 'expression']
        }
        
        # Simple query indicators
        simple_indicators = {
            'basic_select': ['show', 'list', 'get', 'find', 'display'],
            'single_table': ['from one table', 'simple select', 'basic query'],
            'count_only': ['count', 'total only', 'how many']
        }
        
        # Speed requirement indicators
        speed_indicators = ['quick', 'fast', 'immediate', 'asap', 'urgent']
        
        complexity_score = 0
        speed_requirement = False
        reasoning_parts = []
        
        # Check for complexity indicators
        for category, patterns in complex_indicators.items():
            for pattern in patterns:
                if pattern in query_lower:
                    complexity_score += 1
                    reasoning_parts.append(f"Found {category}: '{pattern}'")
        
        # Check for simple indicators (reduce complexity)
        for category, patterns in simple_indicators.items():
            for pattern in patterns:
                if pattern in query_lower:
                    complexity_score -= 0.5
                    reasoning_parts.append(f"Simple pattern: '{pattern}'")
        
        # Check for speed requirements
        for pattern in speed_indicators:
            if pattern in query_lower:
                speed_requirement = True
                reasoning_parts.append(f"Speed required: '{pattern}'")
        
        # Decision logic
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "No specific patterns detected"
        
        if speed_requirement and complexity_score < 2:
            return "fast", 0.9, f"Speed prioritized with low complexity. {reasoning}"
        elif complexity_score >= 3:
            return "complex", 0.95, f"High complexity detected (score: {complexity_score}). {reasoning}"
        elif complexity_score >= 1:
            return "complex", 0.8, f"Moderate complexity (score: {complexity_score}). {reasoning}"
        else:
            return "fast", 0.85, f"Simple query, using fast model. {reasoning}"
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for query"""
        return hashlib.md5(query.lower().encode()).hexdigest()
    
    def _get_cached_analysis(self, query: str) -> Optional[str]:
        """Get cached analysis if available and not expired"""
        cache_key = self._get_cache_key(query)
        
        if cache_key in self._analysis_cache:
            result, timestamp = self._analysis_cache[cache_key]
            if time.time() - timestamp < self._cache_expiry:
                logger.info(f"Using cached analysis for: {query[:50]}...")
                return result
            else:
                del self._analysis_cache[cache_key]
        
        return None
    
    def _cache_analysis(self, query: str, result: str) -> None:
        """Cache analysis result"""
        cache_key = self._get_cache_key(query)
        self._analysis_cache[cache_key] = (result, time.time())
    
    def analyze_schema(self, query: str) -> str:
        """
        Main method: Intelligent schema analysis using LLM semantic understanding
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cached_result = self._get_cached_analysis(query)
            if cached_result:
                return cached_result
            
            # Get database schema
            tables = self._get_database_schema()
            if not tables:
                return "No database tables available - check database connection"
              # Intelligent model routing
            model_choice, confidence, routing_reasoning = self._analyze_query_complexity(query)
            selected_model = self.models[model_choice]
            
            logger.info(f"Query routing: {selected_model} (confidence: {confidence:.2f})")
            logger.debug(f"Routing reasoning: {routing_reasoning}")
            
            # For very simple queries, use fast keyword matching to avoid LLM delay
            if confidence > 0.85 and model_choice == "fast" and self._is_obvious_query(query):
                logger.info("Using fast keyword fallback for obvious query")
                result = self._fast_keyword_analysis(query, tables, routing_reasoning)
                self._cache_analysis(query, result)
                total_time = time.time() - start_time
                logger.info(f"Fast analysis completed in {total_time:.2f}s")
                return result
            
            # Create schema summary for LLM
            schema_summary = self._create_schema_summary(tables)
            
            # System prompt for intelligent semantic understanding
            system_prompt = """You are an expert database architect with deep understanding of SQL and business domains.

            Analyze the user's natural language query and the database schema to identify the most relevant tables and columns needed.

            Think semantically, not just by keywords:
            - "sales" could mean SalesOrderHeader, SalesOrderDetail, or revenue-related tables
            - "customer" could mean Customer, Person, or user-related tables  
            - "region" could mean Address, StateProvince, Territory, or geographic tables
            - "product" could mean Product, ProductCategory, Inventory

            Return JSON:
            {
                "relevant_tables": ["schema.table1", "schema.table2"],
                "reasoning": "Detailed explanation of why these tables are needed",
                "confidence": 0.9,
                "join_strategy": "How tables should be joined",
                "key_columns": ["important columns for this query"],
                "query_type": "classification of query (simple_select, aggregation, etc)"
            }

            Focus on understanding the INTENT behind the query, not just matching keywords."""
                        
            user_prompt = f"""            User Query: "{query}"

            Query Analysis: {routing_reasoning}

            Available Database Schema:
            {schema_summary}

            Analyze this query semantically and identify the most relevant tables and relationships.
            """
            
            # Call the intelligently selected LLM with timeout
            # Use appropriate token parameter based on model
            completion_params = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "timeout": 60.0  # Increase to 60 seconds for complex analysis
            }
            
            # o4-mini and o1 models have different parameter requirements
            if "o4-mini" in selected_model.lower() or "o1" in selected_model.lower():
                completion_params["max_completion_tokens"] = 3000  # Increased from 1500
                # o4-mini only supports default temperature (1), so remove temperature setting
                if "temperature" in completion_params:
                    del completion_params["temperature"]
                logger.debug(f"Using max_completion_tokens=3000 and default temperature for model: {selected_model}")
            else:
                completion_params["max_tokens"] = 3000  # Increased from 1500
                logger.debug(f"Using max_tokens=3000 and temperature 0.1 for model: {selected_model}")
            
            llm_start_time = time.time()
            response = self.client.chat.completions.create(**completion_params)
            
            llm_time = time.time() - llm_start_time
            llm_result = response.choices[0].message.content.strip()
            
            # Process LLM response
            result = self._process_llm_response(
                llm_result, tables, selected_model, confidence, llm_time, routing_reasoning
            )
              # Cache the result
            self._cache_analysis(query, result)
            
            total_time = time.time() - start_time
            logger.info(f"Schema analysis completed in {total_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM schema analysis: {e}")            # Fast fallback: return simplified schema context instead of error
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                logger.warning("Schema analysis timed out, using fast fallback")
                return self._create_fast_schema_fallback(tables, query)
            return f"Schema analysis error: {str(e)}"
    
    def _create_fast_schema_fallback(self, tables: List[Any], query: str) -> str:
        """
        Create a fast schema fallback when LLM analysis times out
        Returns a simplified schema context without LLM processing
        """
        logger.info("Creating fast schema fallback due to timeout")
        
        # Simple pattern matching for likely tables
        query_lower = query.lower()
        relevant_tables = []
        
        # Basic table matching
        for table in tables:
            table_name_lower = table.name.lower()
            if (table_name_lower in query_lower or 
                any(word in query_lower for word in ['customer', 'order', 'product', 'sale']) and 
                any(word in table_name_lower for word in ['customer', 'order', 'product', 'sale'])):
                relevant_tables.append(table)
        
        # If no specific matches, include tables with common business entities
        if not relevant_tables:
            business_keywords = ['customer', 'order', 'product', 'sale', 'item', 'detail', 'header']
            for table in tables:
                if any(keyword in table.name.lower() for keyword in business_keywords):
                    relevant_tables.append(table)
        
        # Fallback to first few tables if still nothing
        if not relevant_tables:
            relevant_tables = tables[:3]
        
        # Create simplified schema summary
        schema_summary = "Schema Analysis (Fast Fallback):\n"
        schema_summary += f"Query: {query}\n"
        schema_summary += f"Relevant Tables ({len(relevant_tables)}):\n\n"
        
        for table in relevant_tables:
            schema_summary += f"{table.schema}.{table.name}:\n"
            key_columns = [col for col in table.columns[:5]]  # First 5 columns
            for col in key_columns:
                pk = " [PK]" if col.is_primary_key else ""
                fk = " [FK]" if col.is_foreign_key else ""
                schema_summary += f"  - {col.name}: {col.data_type}{pk}{fk}\n"
            schema_summary += "\n"
        
        return schema_summary

    def _create_schema_summary(self, tables: List[Any]) -> str:
        """Create condensed schema summary for LLM"""
        summary = "Database Tables:\n"
        for table in tables:
            summary += f"\n{table.schema}.{table.name}:\n"
            # Show key columns first
            pk_columns = [col for col in table.columns if col.is_primary_key]
            fk_columns = [col for col in table.columns if col.is_foreign_key]
            other_columns = [col for col in table.columns if not col.is_primary_key and not col.is_foreign_key]
            
            # Display in order: PK, FK, then others (limit to avoid token overflow)
            displayed_columns = pk_columns + fk_columns + other_columns[:3]
            
            for col in displayed_columns:
                pk = " [PK]" if col.is_primary_key else ""
                fk = " [FK]" if col.is_foreign_key else ""
                summary += f"  - {col.name}: {col.data_type}{pk}{fk}\n"
            
            if len(table.columns) > len(displayed_columns):
                summary += f"  ... and {len(table.columns) - len(displayed_columns)} more columns\n"
        return summary
    
    def _process_llm_response(self, llm_result: str, tables: List[Any], 
                            model: str, confidence: float, llm_time: float, 
                            routing_reasoning: str) -> str:
        """Process LLM response and format final result"""
        try:
            # Clean the LLM result - remove markdown code blocks
            cleaned_result = llm_result.strip()
            
            # Remove markdown code blocks if present
            if "```json" in cleaned_result:
                # Extract JSON from markdown
                start = cleaned_result.find("```json") + 7
                end = cleaned_result.find("```", start)
                if end != -1:
                    cleaned_result = cleaned_result[start:end].strip()
            elif "```" in cleaned_result:
                # Handle generic code blocks
                start = cleaned_result.find("```") + 3
                end = cleaned_result.find("```", start)
                if end != -1:
                    cleaned_result = cleaned_result[start:end].strip()
            
            # Try to parse JSON response
            analysis = json.loads(cleaned_result)
            relevant_table_names = analysis.get("relevant_tables", [])
            reasoning = analysis.get("reasoning", "")
            llm_confidence = analysis.get("confidence", 0.5)
            join_strategy = analysis.get("join_strategy", "")
            key_columns = analysis.get("key_columns", [])
            query_type = analysis.get("query_type", "unknown")
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON response, using text fallback")
            # Extract table names from text response as fallback
            relevant_table_names = []
            for table in tables:
                if table.name.lower() in llm_result.lower():
                    relevant_table_names.append(f"{table.schema}.{table.name}")
            
            reasoning = llm_result
            llm_confidence = 0.6
            join_strategy = "Not specified"
            key_columns = []
            query_type = "text_fallback"
        
        # Find actual table objects
        relevant_tables = []
        for table in tables:
            table_full_name = f"{table.schema}.{table.name}"
            if any(name.lower() in table_full_name.lower() for name in relevant_table_names):
                relevant_tables.append(table)
        
        # Fallback if no tables found
        if not relevant_tables:
            logger.warning("No relevant tables found by LLM, using keyword fallback")
            # Simple fallback based on common table name patterns
            query_words = llm_result.lower().split()
            for table in tables:
                if any(word in table.name.lower() for word in query_words if len(word) > 3):
                    relevant_tables.append(table)
        
        # Format intelligent result
        if not relevant_tables:
            return "No relevant tables identified for this query"
        
        result = f"INTELLIGENT SCHEMA ANALYSIS\n"
        result += f"Model: {model} | LLM Confidence: {llm_confidence:.2f} | Time: {llm_time:.2f}s\n"
        result += f"Query Type: {query_type}\n"
        result += f"Routing: {routing_reasoning}\n\n"
        
        result += f"Analysis: {reasoning}\n\n"
        
        if join_strategy:
            result += f"Join Strategy: {join_strategy}\n\n"
        
        result += "RELEVANT TABLES:\n"
        for i, table in enumerate(relevant_tables[:3], 1):  # Limit to top 3
            result += f"\n{i}. Table: {table.schema}.{table.name}\n"
            for col in table.columns:
                pk = " [PK]" if col.is_primary_key else ""
                fk = " [FK]" if col.is_foreign_key else ""
                nullable = "NULL" if col.is_nullable else "NOT NULL"
                
                # Highlight key columns identified by LLM
                highlight = " ★" if any(col.name.lower() in kc.lower() for kc in key_columns) else ""
                result += f"   - {col.name}: {col.data_type} {nullable}{pk}{fk}{highlight}\n"
            result += "\n"
        
        return result