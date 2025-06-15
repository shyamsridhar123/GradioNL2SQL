"""
Enterprise-Grade LLM Schema Analyst Tool
Best practices: Connection pooling, lazy loading, circuit breaker, multi-level caching
"""

import os
import sys
import json
import hashlib
import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from openai import AzureOpenAI

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.connection import DatabaseConnection
from database.config import DatabaseConfig
from database.schema_inspector import SchemaInspector
from utils.logging_config import get_logger

logger = get_logger("text2sql.enterprise_schema_analyst")

@dataclass
class CacheEntry:
    """Cache entry with TTL and metadata"""
    data: Any
    timestamp: float
    ttl: float
    access_count: int = 0
    last_access: float = 0

class CircuitBreaker:
    """Circuit breaker for database operations"""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60, expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        with self._lock:
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e
    
    def _should_attempt_reset(self):
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'

class EnterpriseSchemaCache:
    """Enterprise-grade caching with TTL, LRU, and background refresh"""
    
    def __init__(self, default_ttl=3600, max_size=1000):
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cache-refresh")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache with access tracking"""
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            current_time = time.time()
            
            # Check if expired
            if current_time - entry.timestamp > entry.ttl:
                del self._cache[key]
                return None
            
            # Update access metrics
            entry.access_count += 1
            entry.last_access = current_time
            
            return entry.data
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache with TTL"""
        with self._lock:
            if len(self._cache) >= self.max_size:
                self._evict_lru()
            
            self._cache[key] = CacheEntry(
                data=value,
                timestamp=time.time(),
                ttl=ttl or self.default_ttl,
                access_count=1,
                last_access=time.time()
            )
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry"""
        if not self._cache:
            return
        
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_access)
        del self._cache[lru_key]
    
    def background_refresh(self, key: str, refresh_func, *args, **kwargs) -> None:
        """Refresh cache entry in background"""
        self._executor.submit(self._refresh_entry, key, refresh_func, *args, **kwargs)
    
    def _refresh_entry(self, key: str, refresh_func, *args, **kwargs) -> None:
        """Background refresh implementation"""
        try:
            new_value = refresh_func(*args, **kwargs)
            self.set(key, new_value)
            logger.info(f"Background refreshed cache key: {key}")
        except Exception as e:
            logger.error(f"Background refresh failed for key {key}: {e}")

class EnterpriseSchemaAnalyst:
    """Enterprise-grade schema analyst with best practices"""
    
    def __init__(self):
        # Azure OpenAI client with connection pooling
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-15-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            max_retries=3,
            timeout=30.0
        )
        
        # Model routing configuration
        self.models = {
            "fast": "gpt-4o-mini",      # Fast, cheap for simple queries
            "complex": "gpt-4"          # Slower, expensive but better for complex queries
        }
        
        # Enterprise caching
        self.schema_cache = EnterpriseSchemaCache(default_ttl=1800)  # 30 min TTL
        self.analysis_cache = EnterpriseSchemaCache(default_ttl=600)  # 10 min TTL
        
        # Circuit breaker for database operations
        self.db_circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            expected_exception=Exception
        )
        
        # Performance metrics
        self.metrics = {
            'cache_hits': 0,
            'cache_misses': 0,
            'db_calls': 0,
            'llm_calls': 0,
            'total_queries': 0
        }
        
        logger.info("Enterprise Schema Analyst initialized with connection pooling and caching")
    
    def _get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        return DatabaseConfig.from_env(use_managed_identity=False)
    
    def _load_schema_with_circuit_breaker(self) -> List[Any]:
        """Load schema with circuit breaker protection"""
        def _load_schema():
            config = self._get_database_config()
            with DatabaseConnection(config) as db:
                if not db.test_connection():
                    raise Exception("Database connection test failed")
                
                inspector = SchemaInspector(db)
                tables = inspector.get_all_tables()
                self.metrics['db_calls'] += 1
                return tables
        
        return self.db_circuit_breaker.call(_load_schema)
    
    def _get_schema_cached(self) -> List[Any]:
        """Get schema with enterprise caching"""
        cache_key = "database_schema"
        
        # Try cache first
        cached_schema = self.schema_cache.get(cache_key)
        if cached_schema is not None:
            self.metrics['cache_hits'] += 1
            
            # Background refresh if cache is older than 15 minutes
            entry = self.schema_cache._cache.get(cache_key)
            if entry and (time.time() - entry.timestamp) > 900:  # 15 minutes
                self.schema_cache.background_refresh(
                    cache_key, 
                    self._load_schema_with_circuit_breaker
                )
            
            return cached_schema
        
        # Cache miss - load from database
        self.metrics['cache_misses'] += 1
        try:
            schema = self._load_schema_with_circuit_breaker()
            self.schema_cache.set(cache_key, schema, ttl=1800)  # 30 minutes
            logger.info(f"Schema cached with {len(schema)} tables")
            return schema
        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            # Try to return stale cache data if available
            stale_data = self.schema_cache._cache.get(cache_key)
            if stale_data:
                logger.warning("Returning stale schema cache due to database error")
                return stale_data.data
            return []
    
    def _analyze_query_complexity(self, query: str) -> Tuple[str, float, Dict[str, Any]]:
        """
        Enterprise query complexity analysis with detailed metrics
        Returns: (model_choice, confidence_score, analysis_details)
        """
        query_lower = query.lower()
        analysis = {
            'length': len(query),
            'word_count': len(query.split()),
            'complexity_indicators': [],
            'speed_indicators': [],
            'performance_hints': []
        }
        
        # Complexity indicators with weights
        complexity_patterns = {
            'joins': (['join', 'inner join', 'left join', 'right join', 'full join'], 3),
            'subqueries': (['subquery', 'select.*select', '\\(.*select.*\\)'], 4),
            'aggregations': (['group by', 'having', 'partition', 'window'], 2),
            'advanced_functions': (['case when', 'pivot', 'unpivot', 'recursive'], 3),
            'multiple_tables': (['from.*,', 'join.*join'], 2),
            'complex_conditions': (['and.*or', 'between.*and', 'in.*select'], 1)
        }
        
        speed_patterns = {
            'simple_requests': (['show', 'list', 'get', 'find'], -1),
            'urgent_indicators': (['quick', 'fast', 'immediate', 'asap'], 2),
            'count_only': (['count', 'total', 'sum only'], -1)
        }
        
        complexity_score = 0
        speed_requirement = 0
        
        # Analyze complexity
        for category, (patterns, weight) in complexity_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    analysis['complexity_indicators'].append(category)
                    complexity_score += weight
        
        # Analyze speed requirements
        for category, (patterns, weight) in speed_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    analysis['speed_indicators'].append(category)
                    speed_requirement += weight
        
        # Decision logic with confidence scoring
        if speed_requirement > 1 and complexity_score < 3:
            model_choice = "fast"
            confidence = 0.9
            analysis['performance_hints'].append("Using fast model for speed-critical simple query")
        elif complexity_score >= 5:
            model_choice = "complex"
            confidence = 0.95
            analysis['performance_hints'].append("Using complex model for high-complexity query")
        elif complexity_score >= 2:
            model_choice = "complex"
            confidence = 0.8
            analysis['performance_hints'].append("Using complex model for moderate complexity")
        else:
            model_choice = "fast"
            confidence = 0.85
            analysis['performance_hints'].append("Using fast model for simple query")
        
        return model_choice, confidence, analysis
    
    def analyze_schema(self, query: str) -> str:
        """
        Enterprise schema analysis with full performance optimization
        """
        start_time = time.time()
        self.metrics['total_queries'] += 1
        
        try:
            # Check analysis cache first
            cache_key = hashlib.md5(query.lower().encode()).hexdigest()
            cached_result = self.analysis_cache.get(cache_key)
            if cached_result:
                self.metrics['cache_hits'] += 1
                logger.info(f"Cache hit for query analysis: {query[:50]}...")
                return cached_result
            
            self.metrics['cache_misses'] += 1
            
            # Get schema with caching
            tables = self._get_schema_cached()
            if not tables:
                return "No database tables available (check database connection)"
            
            # Intelligent model routing
            model_choice, confidence, analysis_details = self._analyze_query_complexity(query)
            selected_model = self.models[model_choice]
            
            logger.info(f"Query analysis: {model_choice} model (confidence: {confidence:.2f})")
            logger.debug(f"Analysis details: {analysis_details}")
            
            # Create optimized schema summary
            schema_summary = self._create_schema_summary(tables, query)
            
            # System prompt for intelligent analysis
            system_prompt = self._get_analysis_system_prompt()
            user_prompt = self._create_user_prompt(query, schema_summary, analysis_details)
            
            # Call LLM with performance monitoring
            llm_start_time = time.time()
            try:
                response = self.client.chat.completions.create(
                    model=selected_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    max_tokens=1500,
                    timeout=30.0
                )
                self.metrics['llm_calls'] += 1
                llm_time = time.time() - llm_start_time
                
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                # Fallback to simple keyword matching
                return self._fallback_analysis(query, tables)
            
            # Parse and format results
            result = self._process_llm_response(
                response.choices[0].message.content.strip(),
                tables, selected_model, confidence, llm_time
            )
            
            # Cache the result
            self.analysis_cache.set(cache_key, result, ttl=600)  # 10 minutes
            
            total_time = time.time() - start_time
            logger.info(f"Schema analysis completed in {total_time:.2f}s (LLM: {llm_time:.2f}s)")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enterprise schema analysis: {e}")
            return f"Analysis error: {str(e)}"
    
    def _create_schema_summary(self, tables: List[Any], query: str) -> str:
        """Create optimized schema summary based on query"""
        # TODO: Implement smart schema filtering based on query keywords
        summary = "Database Schema:\n"
        for table in tables[:10]:  # Limit to prevent token overflow
            summary += f"\n{table.schema}.{table.name}:\n"
            for col in table.columns[:5]:  # First 5 columns
                pk = " [PK]" if col.is_primary_key else ""
                fk = " [FK]" if col.is_foreign_key else ""
                summary += f"  - {col.name}: {col.data_type}{pk}{fk}\n"
            if len(table.columns) > 5:
                summary += f"  ... and {len(table.columns) - 5} more columns\n"
        return summary
    
    def _get_analysis_system_prompt(self) -> str:
        """Get system prompt for schema analysis"""
        return """You are an enterprise database architect. Analyze user queries and database schema to identify the most relevant tables and relationships.

Return JSON:
{
    "relevant_tables": ["table1", "table2"],
    "reasoning": "Detailed explanation",
    "confidence": 0.9,
    "join_relationships": ["relationship descriptions"],
    "key_columns": ["important columns"],
    "performance_notes": ["optimization suggestions"]
}

Be intelligent about semantic mapping and consider performance implications."""
    
    def _create_user_prompt(self, query: str, schema_summary: str, analysis_details: Dict) -> str:
        """Create user prompt with context"""
        return f"""
User Query: {query}

Query Analysis: {analysis_details}

Available Schema:
{schema_summary}

Provide intelligent schema analysis for optimal SQL generation.
"""
    
    def _process_llm_response(self, llm_result: str, tables: List[Any], 
                            model: str, confidence: float, llm_time: float) -> str:
        """Process LLM response and format results"""
        try:
            analysis = json.loads(llm_result)
            relevant_table_names = analysis.get("relevant_tables", [])
            reasoning = analysis.get("reasoning", "")
            llm_confidence = analysis.get("confidence", 0.5)
            join_relationships = analysis.get("join_relationships", [])
            key_columns = analysis.get("key_columns", [])
            performance_notes = analysis.get("performance_notes", [])
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON response")
            return self._fallback_analysis(llm_result, tables)
        
        # Find actual table objects
        relevant_tables = []
        for table in tables:
            if any(name.lower() in table.name.lower() for name in relevant_table_names):
                relevant_tables.append(table)
        
        # Format enterprise result
        result = f"ENTERPRISE SCHEMA ANALYSIS\n"
        result += f"Model: {model} | Confidence: {llm_confidence:.2f} | Time: {llm_time:.2f}s\n\n"
        result += f"Analysis: {reasoning}\n\n"
        
        if join_relationships:
            result += f"Recommended Joins: {', '.join(join_relationships)}\n\n"
        
        if performance_notes:
            result += f"Performance Notes: {', '.join(performance_notes)}\n\n"
        
        result += "RELEVANT TABLES:\n"
        for table in relevant_tables[:3]:
            result += f"\nTable: {table.schema}.{table.name}\n"
            for col in table.columns:
                pk = " [PK]" if col.is_primary_key else ""
                fk = " [FK]" if col.is_foreign_key else ""
                nullable = "NULL" if col.is_nullable else "NOT NULL"
                highlight = " ★" if any(col.name.lower() in kc.lower() for kc in key_columns) else ""
                result += f"  - {col.name}: {col.data_type} {nullable}{pk}{fk}{highlight}\n"
            result += "\n"
        
        return result
    
    def _fallback_analysis(self, query_or_response: str, tables: List[Any]) -> str:
        """Fallback analysis when LLM fails"""
        logger.warning("Using fallback schema analysis")
        # Simple keyword matching fallback
        query_lower = query_or_response.lower()
        relevant_tables = []
        
        for table in tables:
            if any(word in table.name.lower() for word in query_lower.split() if len(word) > 3):
                relevant_tables.append(table)
        
        if not relevant_tables:
            relevant_tables = tables[:3]  # Return first 3 tables
        
        result = "FALLBACK SCHEMA ANALYSIS\n\n"
        for table in relevant_tables[:3]:
            result += f"Table: {table.schema}.{table.name}\n"
            for col in table.columns[:5]:
                pk = " [PK]" if col.is_primary_key else ""
                fk = " [FK]" if col.is_foreign_key else ""
                result += f"  - {col.name}: {col.data_type}{pk}{fk}\n"
            result += "\n"
        
        return result
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        total_requests = self.metrics['cache_hits'] + self.metrics['cache_misses']
        cache_hit_rate = (self.metrics['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.metrics,
            'cache_hit_rate': f"{cache_hit_rate:.1f}%",
            'circuit_breaker_state': self.db_circuit_breaker.state
        }

# Alias for backward compatibility
LLMSchemaAnalystTool = EnterpriseSchemaAnalyst
