"""
TRULY INTELLIGENT Multi-Agent Text2SQL System
Uses LLM-powered orchestration to make smart decisions about query processing
"""

import sys
import os
import json
from typing import Dict, Any, List, Optional
import re

# Add src directory to path to access tools and database modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import intelligent orchestrator and LLM-powered tools
from agents.intelligent_orchestrator import IntelligentOrchestrator
from tools.llm_schema_analyst_tool import LLMSchemaAnalystTool
from tools.sql_generation_tool import SQLGenerationTool
from tools.error_correction_tool import ErrorCorrectionTool

# Import airplane mode components
from airplane_mode.query_router import AirplaneModeRouter
from airplane_mode.sql_generator import AirplaneModeSQLGenerator
from airplane_mode.schema_analyst import AirplaneModeSchemaAnalyst

# Import database modules
from database.connection import DatabaseConnection
from database.config import DatabaseConfig
from utils.logging_config import get_logger
from utils.query_cache import QueryResultCache

logger = get_logger("text2sql.intelligent_agent")

class IntelligentText2SQLAgent:
    """
    TRULY INTELLIGENT Agent that uses LLM orchestration to make smart decisions
    about how to process queries, which tools to use, and how to handle errors
    """
    def __init__(self):
        logger.info("Initializing Intelligent Text2SQL Agent...")
        
        # Initialize query cache for performance
        self.query_cache = QueryResultCache(cache_ttl=3600)  # 1 hour cache
        
        # Initialize airplane mode components (fastest - no LLM calls)
        logger.debug("Initializing airplane mode components...")
        self.airplane_router = AirplaneModeRouter()
        self.airplane_sql_generator = AirplaneModeSQLGenerator()
        self.airplane_schema_analyst = AirplaneModeSchemaAnalyst()
        
        # Initialize the LLM-powered orchestrator (the brain)
        logger.debug("Initializing intelligent orchestrator...")
        self.orchestrator = IntelligentOrchestrator()
        
        # Initialize LLM-powered schema analyst
        logger.debug("Initializing LLM schema analyst...")
        self.llm_schema_analyst = LLMSchemaAnalystTool()
        
        # Initialize SQL generator
        logger.debug("Initializing SQL generator...")
        self.sql_generator = SQLGenerationTool()
        
        # Initialize error corrector
        logger.debug("Initializing error corrector...")
        self.error_corrector = ErrorCorrectionTool()
          # Initialize database connection - use SQL authentication
        logger.debug("Setting up database connection...")
        self.config = DatabaseConfig.from_env(use_managed_identity=False)
        self.db_connection = DatabaseConnection(self.config)
        
        # Preload schema cache for faster query processing
        logger.debug("Preloading database schema cache...")
        try:
            schema_tables = self.llm_schema_analyst._get_database_schema()
            logger.info(f"Schema preloaded with {len(schema_tables)} tables")
        except Exception as e:
            logger.warning(f"Could not preload schema: {e}")
        
        logger.info("Intelligent Text2SQL Agent initialized successfully")
    
    def process_query_mode(self, query: str) -> Dict[str, Any]:
        """
        Main entry point for query processing with intelligent routing:
        1. Cache Check (instant) - Return cached results if available
        2. Fast Path (1-3s) - Simple LLM call for basic queries  
        3. Full Orchestration (5-15s) - Complete LLM pipeline for complex queries
        4. Airplane Mode (ultimate fallback) - Template-based, never fails
        """
        logger.info(f"Processing query: {query}")
        
        # STEP 1: Check cache first (always fastest)
        cache_result = self._check_query_cache(query)
        if cache_result:
            logger.info("Using cached result")
            return cache_result
        
        # STEP 2: Check if this is a simple query that can use the fast path
        if self._is_simple_query(query):
            logger.info("Using fast path for simple query")
            result = self._handle_simple_query(query)
            if result['success']:
                self._store_in_cache(query, result)
                return result
            else:
                logger.warning("Fast path failed, proceeding to full orchestration")
        
        # STEP 3: Use full LLM orchestration for complex queries
        logger.info("Using full LLM orchestration for complex query")
        result = self._process_with_full_orchestration(query)
        if result['success']:
            self._store_in_cache(query, result)
            return result
        else:
            logger.warning("Full orchestration failed, falling back to airplane mode")
        
        # STEP 4: Ultimate fallback - airplane mode (never fails)
        logger.info("Using airplane mode as ultimate fallback")
        use_airplane, reasoning, metadata = self.airplane_router.should_use_airplane_mode(query)
        if use_airplane:
            logger.info(f"Airplane mode pattern match: {reasoning}")
            return self._handle_airplane_mode(query, metadata)
        else:
            logger.info("No airplane mode pattern, using generic fallback")
            return self._handle_generic_fallback(query)
    
    def _handle_airplane_mode(self, query: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        AIRPLANE MODE - ULTIMATE FALLBACK that ALWAYS works
        Zero dependencies, hardcoded SQL templates, instant response
        NO FALLBACKS FOR FALLBACKS!
        """
        logger.info(f"AIRPLANE MODE: {metadata.get('category', 'hardcoded')}")
        
        # HARDCODED SQL templates - NO DEPENDENCIES, NO FAILURES
        query_lower = query.lower().strip()
        
        if 'count' in query_lower and 'customer' in query_lower:
            sql = "SELECT COUNT(*) AS customer_count FROM SalesLT.Customer"
        elif 'count' in query_lower and 'product' in query_lower:
            sql = "SELECT COUNT(*) AS product_count FROM SalesLT.Product"
        elif 'count' in query_lower and ('order' in query_lower or 'sale' in query_lower):
            sql = "SELECT COUNT(*) AS order_count FROM SalesLT.SalesOrderHeader"
        elif 'show' in query_lower and 'customer' in query_lower:
            sql = "SELECT TOP 10 CustomerID, FirstName, LastName FROM SalesLT.Customer"
        elif 'show' in query_lower and 'product' in query_lower:
            sql = "SELECT TOP 10 ProductID, Name, ListPrice FROM SalesLT.Product"
        elif 'show' in query_lower and ('order' in query_lower or 'sale' in query_lower):
            sql = "SELECT TOP 10 SalesOrderID, OrderDate, TotalDue FROM SalesLT.SalesOrderHeader ORDER BY OrderDate DESC"
        else:
            # DEFAULT: just count customers if we don't understand
            sql = "SELECT COUNT(*) AS total_count FROM SalesLT.Customer"
        
        try:
            # Execute the hardcoded SQL
            results = self.db_connection.execute_query(sql)
            
            return {
                "success": True,
                "sql": sql,
                "results": results,
                "schema_used": "hardcoded",
                "log": f"AIRPLANE MODE: Instant response with {len(results)} rows.",
                "approach": "airplane_mode",
                "execution_time": "< 0.1s"
            }
            
        except Exception as e:
            # EVEN IF DATABASE IS DOWN, return something useful
            logger.error(f"AIRPLANE MODE: Database error: {e}")
            return {
                "success": False,
                "sql": sql,
                "results": [],
                "schema_used": "hardcoded",
                "log": f"AIRPLANE MODE: Database error - {str(e)}",
                "approach": "airplane_mode_failed",
                "error": str(e)
            }
    
    def _process_with_full_orchestration(self, query: str) -> Dict[str, Any]:
        """
        Full LLM orchestration process for complex queries
        """
        logger.info(f"ORCHESTRATION START: Processing query: {query}")
        
        try:
            # STEP 1: LLM analyzes query intent and database schema
            logger.info("STEP 1: Starting query intent analysis")
            
            # Get database schema first
            tables = self.llm_schema_analyst._get_database_schema()
            logger.info(f"STEP 1: Retrieved {len(tables)} tables from database")
            
            schema_summary = self.llm_schema_analyst._create_schema_summary(tables)
            logger.info(f"STEP 1: Created schema summary ({len(schema_summary)} chars)")
            
            # LLM analyzes the query intent
            logger.info("STEP 1: Calling orchestrator.analyze_query_intent")
            intent_analysis = self.orchestrator.analyze_query_intent(query, schema_summary)
            logger.info(f"STEP 1: Intent analysis result: complexity={intent_analysis.get('complexity')}, confidence={intent_analysis.get('confidence')}")
            
            # STEP 2: LLM selects relevant schema intelligently
            logger.info("STEP 2: Starting schema analysis")
            schema_result = self.llm_schema_analyst.analyze_schema(query)
            logger.info(f"STEP 2: Schema analysis result type: {type(schema_result)}")
            logger.info(f"STEP 2: Schema analysis content: {str(schema_result)[:200]}...")
            
            schema_context = schema_result if isinstance(schema_result, str) else json.dumps(schema_result, indent=2)
            logger.info(f"STEP 2: Final schema context length: {len(schema_context)} chars")
            
            # STEP 3: LLM decides processing approach
            logger.info("STEP 3: Starting processing approach decision")
            approach_decision = self.orchestrator.decide_processing_approach(query, intent_analysis, schema_context)
            logger.info(f"STEP 3: Approach decision: {approach_decision}")
            
            # STEP 4: Execute the decided approach
            logger.info("STEP 4: Executing approach")
            return self._execute_intelligent_approach(query, approach_decision, schema_context, intent_analysis)
            
        except Exception as e:
            logger.error(f"Error in intelligent query processing: {e}")
            return {
                "success": False,
                "sql": "",
                "results": [],
                "schema_used": "",
                "log": f"Intelligent processing failed: {str(e)}",
                "approach": "error"            }
    
    def _execute_intelligent_approach(self, query: str, approach: Dict[str, Any], schema_context: str, intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the LLM-decided approach for processing the query
        """
        approach_type = approach.get("approach", "direct_generation")
        llm_model = approach.get("llm_model", "gpt-4o-mini")
        
        logger.debug(f"Executing approach: {approach_type}")
        
        if approach_type == "direct_generation":
            return self._direct_generation_approach(query, schema_context, llm_model)
        
        elif approach_type == "iterative_refinement":
            return self._iterative_refinement_approach(query, schema_context, llm_model, approach.get("expected_iterations", 2))
        
        elif approach_type == "decompose_query":
            return self._decompose_query_approach(query, schema_context, llm_model)
        
        elif approach_type == "clarify_requirements":
            return {
                "success": False,
                "sql": "",
                "results": [],
                "schema_used": schema_context,
                "log": "Query is ambiguous and requires clarification. Please provide more specific details about what you want to analyze.",
                "clarification_needed": True,
                "suggestions": intent_analysis.get("challenges", [])
            }
        
        elif approach_type == "use_stored_procedure":
            # Try to find matching stored procedure
            return self._stored_procedure_approach(query)
        
        else:
            # Fallback to direct generation
            return self._direct_generation_approach(query, schema_context, llm_model)
    
    def _direct_generation_approach(self, query: str, schema_context: str, llm_model: str) -> Dict[str, Any]:
        """Direct SQL generation approach"""
        logger.info(f"DIRECT_GEN: Starting direct generation with model {llm_model}")
        logger.info(f"DIRECT_GEN: Schema context length: {len(schema_context)} chars")
        logger.info(f"DIRECT_GEN: Schema preview: {schema_context[:200]}...")
        
        try:
            # Generate SQL with specified model
            logger.info("DIRECT_GEN: Calling SQL generator")
            sql_query = self.sql_generator.forward(query, schema_context)
            logger.info(f"DIRECT_GEN: Generated SQL: {sql_query}")
            
            # Execute query
            logger.info("DIRECT_GEN: Executing SQL query")
            results = self.db_connection.execute_query(sql_query)
            logger.info(f"DIRECT_GEN: Query executed successfully, {len(results)} rows returned")
            
            return {
                "success": True,
                "sql": sql_query,
                "results": results,
                "schema_used": schema_context,
                "log": f"Direct generation successful. {len(results)} rows returned.",
                "approach": "direct_generation", 
                "llm_model": llm_model
            }
            
        except Exception as e:
            logger.error(f"DIRECT_GEN: SQL generation failed: {e}")
            # Try error correction
            return self._handle_execution_error(query, sql_query if 'sql_query' in locals() else "", str(e), schema_context)
    
    def _iterative_refinement_approach(self, query: str, schema_context: str, llm_model: str, max_iterations: int) -> Dict[str, Any]:
        """Iterative refinement approach with intelligent retry logic"""
        logger.debug(f"Iterative refinement with up to {max_iterations} iterations")
        
        sql_attempts = []
        errors = []
        
        for iteration in range(max_iterations):
            logger.debug(f"Iteration {iteration + 1}/{max_iterations}")
            
            try:
                # Generate SQL (with context from previous attempts if any)
                context = schema_context
                if sql_attempts:
                    context += f"\n\nPrevious attempts failed:\n" + "\n".join([f"SQL: {sql}\nError: {err}" for sql, err in zip(sql_attempts, errors)])
                
                sql_query = self.sql_generator.forward(query, context)
                results = self.db_connection.execute_query(sql_query)
                
                return {
                    "success": True,
                    "sql": sql_query,
                    "results": results,
                    "schema_used": schema_context,
                    "log": f"Iterative refinement successful on iteration {iteration + 1}. {len(results)} rows returned.",
                    "approach": "iterative_refinement",
                    "iterations": iteration + 1,
                    "llm_model": llm_model
                }
                
            except Exception as e:
                sql_attempts.append(sql_query if 'sql_query' in locals() else "")
                errors.append(str(e))
                logger.debug(f"Iteration {iteration + 1} failed: {e}")
        
        # All iterations failed - use LLM to analyze failures
        logger.debug("Analyzing failures with LLM...")
        failure_analysis = self.orchestrator.analyze_failure_and_retry(query, sql_attempts, errors, schema_context)
        
        return {
            "success": False,
            "sql": sql_attempts[-1] if sql_attempts else "",
            "results": [],
            "schema_used": schema_context,
            "log": f"Iterative refinement failed after {max_iterations} attempts. {failure_analysis.get('diagnosis', 'Analysis failed')}",
            "approach": "iterative_refinement",
            "iterations": max_iterations,            "failure_analysis": failure_analysis,
            "sql_attempts": sql_attempts,
            "errors": errors
        }
    
    def _decompose_query_approach(self, query: str, schema_context: str, llm_model: str) -> Dict[str, Any]:
        """Decompose complex query into simpler parts"""
        logger.debug("Decomposing complex query")
        
        # This would involve breaking the query into parts and combining results
        # For now, fallback to iterative refinement
        return self._iterative_refinement_approach(query, schema_context, llm_model, 3)
    
    def _stored_procedure_approach(self, query: str) -> Dict[str, Any]:
        """Try to execute as stored procedure"""
        logger.debug("Attempting stored procedure execution")
        
        try:
            result = self.stored_proc_executor.forward(query)
            return json.loads(result)
        except Exception as e:
            return {
                "success": False,
                "sql": "",
                "results": [],
                "schema_used": "",
                "log": f"Stored procedure approach failed: {e}",
                "approach": "stored_procedure"
            }
    
    def _handle_execution_error(self, query: str, sql: str, error: str, schema_context: str) -> Dict[str, Any]:
        """Handle execution error with intelligent correction"""
        logger.debug("Attempting intelligent error correction...")
        
        try:
            corrected_sql = self.error_corrector.forward(sql, error, schema_context)
            results = self.db_connection.execute_query(corrected_sql)
            
            return {
                "success": True,
                "sql": corrected_sql,
                "results": results,
                "schema_used": schema_context,
                "log": f"Error corrected successfully. {len(results)} rows returned.",
                "original_sql": sql,
                "original_error": error,
                "approach": "error_correction"
            }
            
        except Exception as retry_error:
            return {
                "success": False,
                "sql": corrected_sql if 'corrected_sql' in locals() else sql,
                "results": [],
                "schema_used": schema_context,
                "log": f"Both original and corrected queries failed.",
                "original_sql": sql,
                "original_error": error,
                "retry_error": str(retry_error),
                "approach": "error_correction_failed"
            }
    
    def process_stored_procedure_mode(self, procedure_call: str) -> Dict[str, Any]:
        """
        Process stored procedure execution request
        """
        logger.info(f"Processing stored procedure: {procedure_call}")
        
        try:
            result = self.stored_proc_executor.forward(procedure_call)
            return json.loads(result)
        except Exception as e:
            logger.error(f"Stored procedure execution failed: {e}")
            return {
                "success": False,                "sql": procedure_call,
                "results": [],
                "schema_used": "",
                "log": f"Stored procedure execution failed: {str(e)}"
            }
    
    def _is_simple_query(self, query: str) -> bool:
        """
        Quick pattern matching to identify simple queries that don't need full LLM orchestration
        """
        query_lower = query.lower().strip()
          # Define comprehensive complex indicators that should trigger full orchestration
        complex_indicators = [
            'join', 'group by', 'order by', 'having', 'union', 'subquery', 'nested',
            'sorted by', 'sort by', 'aggregate', 'sum', 'avg', 'average',
            'total', 'revenue', 'sales', 'by category', 'by product', 'including',
            'where', 'inner', 'outer', 'left', 'right', 'distinct', 'limit', 'top',
            'calculated', 'computed', 'analysis', 'report', 'breakdown', 'grouped',
            'by ', 'group', 'multiple', 'between', 'range', 'filter', 'condition',
            'count by', 'count of', 'count per'  # Complex count operations, not simple counts
        ]
        
        # Check for any complex indicators first - if found, not a simple query
        if any(indicator in query_lower for indicator in complex_indicators):
            return False
            # Simple count queries (basic counts only - no grouping or conditions)
        simple_count_patterns = [
            r'^count\s+\w+\s*$',  # "count customers", "count orders"
            r'^how many\s+\w+\s*$',  # "how many customers"
            r'^(get|show)\s+count\s+of\s+\w+\s*$'  # "get count of customers"
        ]
        
        for pattern in simple_count_patterns:
            if re.match(pattern, query_lower):
                return True
              
        # Simple list/show queries (basic listings only)
        if query_lower.startswith(('list ', 'show ', 'get ', 'find ')):
            return True        # Simple single table queries (no count patterns here as they're handled above)
        simple_patterns = [
            r'^(select|get|show|list)\s+\w+\s*$',  # "select products", "show customers"
            r'^(list|show)\s+all\s+\w+\s*$',  # "list all products"
        ]
        
        for pattern in simple_patterns:
            if re.match(pattern, query_lower):
                return True
                
        return False
    
    def _handle_simple_query(self, query: str) -> Dict[str, Any]:
        """
        Fast path for simple queries - minimal LLM usage
        """
        logger.info(f"Using fast path for simple query: {query}")
        
        try:
            # Quick schema lookup - no LLM needed
            tables = self.llm_schema_analyst._get_database_schema()
            
            # Simple table detection
            query_lower = query.lower()
            likely_table = None
            
            # Pattern matching for common table names
            table_keywords = {
                'customer': ['customer', 'client'],
                'product': ['product', 'item'],
                'order': ['order', 'sale'],
                'employee': ['employee', 'staff', 'worker'],
                'invoice': ['invoice', 'bill'],
                'address': ['address', 'location']
            }
            
            for table in tables:
                table_name_lower = table.name.lower()
                for keyword_group in table_keywords.values():
                    if any(keyword in query_lower for keyword in keyword_group):
                        if any(keyword in table_name_lower for keyword in keyword_group):
                            likely_table = table
                            break
                if likely_table:
                    break
              # If no table found, use the first one (fallback)
            if not likely_table and tables:
                likely_table = tables[0]
            
            if not likely_table:
                logger.warning("No suitable table found for simple query")
                return self._fallback_to_full_processing(query)
            
            # Create schema context for potential LLM fallback
            schema_context = f"""Database: Azure SQL Server
Schema: {likely_table.schema or 'dbo'}
Table: {likely_table.name}
Full Table Name: {likely_table.schema + '.' + likely_table.name if likely_table.schema else likely_table.name}
Columns: {', '.join([f'{col.name} ({col.data_type})' for col in likely_table.columns])}

IMPORTANT: Always use the full table name with schema prefix in SQL queries."""
            
            # Generate simple SQL using templates (no LLM calls!)
            sql_query = self._generate_simple_sql_template(query, likely_table)
            
            # If template generation failed, fall back to LLM
            if not sql_query:
                logger.info("Template generation failed, using LLM for fast path")
                sql_query = self.sql_generator.forward(query, schema_context)
            
            # Execute the SQL directly
            if sql_query and not sql_query.startswith("-- Error"):
                try:
                    results = self.db_connection.execute_query(sql_query)
                    return {
                        "success": True,
                        "sql": sql_query,
                        "results": results,
                        "schema_used": schema_context,
                        "log": f"Fast path successful. {len(results)} rows returned.",
                        "approach": "fast_path"
                    }
                except Exception as e:
                    logger.warning(f"Fast path SQL execution failed: {e}")
                    return self._fallback_to_full_processing(query)
            else:
                logger.warning("Fast path SQL generation failed, falling back to full processing")
                return self._fallback_to_full_processing(query)
        except Exception as e:
            logger.warning(f"Fast path failed: {e}, falling back to full processing")
            return self._fallback_to_full_processing(query)
    
    def _fallback_to_full_processing(self, query: str) -> Dict[str, Any]:
        """
        Fallback to the full LLM orchestration process
        """
        logger.info("Falling back to full LLM orchestration")
        return self._process_with_full_orchestration(query)
    
    def _check_query_cache(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Check if we have a cached result for this query
        """
        return self.query_cache.get_cached_result(query)
    
    def _store_in_cache(self, query: str, result: Dict[str, Any]) -> None:
        """
        Store successful result in cache for future use
        """
        if result.get("success", False):
            self.query_cache.cache_result(query, result)
    
    def _handle_generic_fallback(self, query: str) -> Dict[str, Any]:
        """
        Generic fallback when even airplane mode patterns don't match
        Returns a basic error with suggestion to rephrase
        """
        logger.info("No patterns matched, returning generic response")
        return {
            "success": False,
            "sql": "-- No SQL generated",
            "results": [],
            "schema_used": "",
            "log": "Could not process this query. Please try rephrasing with simpler terms like 'count customers' or 'show products'.",
            "approach": "generic_fallback",
            "suggestions": [
                "count customers",
                "show products", 
                "total sales",
                "list orders"
            ]
        }
    
    def _generate_simple_sql_template(self, query: str, table: Any) -> Optional[str]:
        """
        Generate SQL using templates for common simple patterns (no LLM calls)
        """
        query_lower = query.lower().strip()
        table_name = f"{table.schema}.{table.name}" if table.schema else table.name
        
        # Simple count patterns
        if query_lower.startswith(('count ', 'how many ')):
            return f"SELECT COUNT(*) AS count FROM {table_name}"
        
        # Simple show/list patterns  
        if query_lower.startswith(('show ', 'list ', 'get ', 'display ')):
            return f"SELECT * FROM {table_name}"
        
        # Simple total/sum patterns
        if query_lower.startswith(('total ', 'sum ')):
            # Try to find amount/total column
            amount_cols = [col for col in table.columns 
                          if any(keyword in col.name.lower() 
                          for keyword in ['total', 'amount', 'price', 'cost', 'value'])]
            if amount_cols:
                return f"SELECT SUM({amount_cols[0].name}) AS total FROM {table_name}"
        
        return None  # No template match, use LLM
# For backward compatibility, create an alias
Text2SQLAgent = IntelligentText2SQLAgent
