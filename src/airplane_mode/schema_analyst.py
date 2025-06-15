"""
Airplane Mode Schema Analyst
Fast hardcoded schema analysis without LLM calls
"""

import sys
import os
from typing import Dict, Any, List
import re

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.connection import DatabaseConnection
from database.config import DatabaseConfig
from database.schema_inspector import SchemaInspector
from utils.logging_config import get_logger

logger = get_logger("airplane_mode.schema_analyst")

class AirplaneModeSchemaAnalyst:
    """
    Fast schema analysis using hardcoded business logic and keyword matching
    """    
    def __init__(self, offline_mode=True):
        self._schema_cache = None
        self.offline_mode = offline_mode  # Force offline mode for speed
        
        # Business domain mappings (hardcoded but fast)
        self.domain_mappings = {
            'customer': {
                'tables': ['customer', 'person', 'user', 'client', 'account'],
                'keywords': ['customer', 'client', 'user', 'buyer', 'person', 'account']
            },
            'sales': {
                'tables': ['sales', 'order', 'transaction', 'purchase', 'invoice'],
                'keywords': ['sales', 'sell', 'order', 'purchase', 'transaction', 'revenue', 'invoice']
            },
            'product': {
                'tables': ['product', 'item', 'inventory', 'catalog'],
                'keywords': ['product', 'item', 'goods', 'inventory', 'catalog', 'merchandise']
            },
            'region': {
                'tables': ['address', 'location', 'territory', 'region', 'state', 'country'],
                'keywords': ['region', 'location', 'address', 'territory', 'state', 'country', 'city', 'area']            },
            'category': {
                'tables': ['category', 'type', 'classification'],
                'keywords': ['category', 'type', 'class', 'group', 'classification']
            }
        }
    
    def _get_schema_fast(self) -> List[Any]:
        """Get schema with fallback to hardcoded knowledge when DB fails"""
        if self._schema_cache is not None:
            return self._schema_cache
        
        # If offline mode is enabled, skip database entirely
        if self.offline_mode:
            logger.info("Airplane mode: Using hardcoded schema (offline mode)")
            self._schema_cache = self._get_hardcoded_schema()
            return self._schema_cache
            
        try:
            config = DatabaseConfig.from_env(use_managed_identity=False)
            with DatabaseConnection(config) as db:
                inspector = SchemaInspector(db)
                tables = inspector.get_all_tables()
                self._schema_cache = tables
                logger.info(f"Airplane mode: cached {len(tables)} tables from DB")
                return tables
        except Exception as e:
            logger.warning(f"DB unavailable ({e}), using hardcoded schema knowledge")
            # Return hardcoded schema knowledge when DB is unavailable
            self._schema_cache = self._get_hardcoded_schema()
            return self._schema_cache
    
    def _get_hardcoded_schema(self) -> List[Any]:
        """Hardcoded schema knowledge for offline mode"""
        from types import SimpleNamespace
        
        # Simulate table objects with known schema
        tables = []
        
        # Customer table
        customer_cols = [
            SimpleNamespace(name="CustomerID", data_type="int", is_primary_key=True, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="FirstName", data_type="nvarchar", is_primary_key=False, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="LastName", data_type="nvarchar", is_primary_key=False, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="CompanyName", data_type="nvarchar", is_primary_key=False, is_foreign_key=False, is_nullable=True),
        ]
        tables.append(SimpleNamespace(schema="SalesLT", name="Customer", columns=customer_cols))
        
        # SalesOrderHeader table
        order_header_cols = [
            SimpleNamespace(name="SalesOrderID", data_type="int", is_primary_key=True, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="CustomerID", data_type="int", is_primary_key=False, is_foreign_key=True, is_nullable=False),
            SimpleNamespace(name="OrderDate", data_type="datetime", is_primary_key=False, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="TotalDue", data_type="money", is_primary_key=False, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="ShipToAddressID", data_type="int", is_primary_key=False, is_foreign_key=True, is_nullable=True),
        ]
        tables.append(SimpleNamespace(schema="SalesLT", name="SalesOrderHeader", columns=order_header_cols))
        
        # SalesOrderDetail table  
        order_detail_cols = [
            SimpleNamespace(name="SalesOrderID", data_type="int", is_primary_key=True, is_foreign_key=True, is_nullable=False),
            SimpleNamespace(name="SalesOrderDetailID", data_type="int", is_primary_key=True, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="ProductID", data_type="int", is_primary_key=False, is_foreign_key=True, is_nullable=False),
            SimpleNamespace(name="OrderQty", data_type="smallint", is_primary_key=False, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="UnitPrice", data_type="money", is_primary_key=False, is_foreign_key=False, is_nullable=False),
        ]
        tables.append(SimpleNamespace(schema="SalesLT", name="SalesOrderDetail", columns=order_detail_cols))
        
        # Address table
        address_cols = [
            SimpleNamespace(name="AddressID", data_type="int", is_primary_key=True, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="AddressLine1", data_type="nvarchar", is_primary_key=False, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="City", data_type="nvarchar", is_primary_key=False, is_foreign_key=False, is_nullable=False),
            SimpleNamespace(name="StateProvince", data_type="nvarchar", is_primary_key=False, is_foreign_key=False, is_nullable=False),
        ]
        tables.append(SimpleNamespace(schema="SalesLT", name="Address", columns=address_cols))
        
        logger.info(f"Using hardcoded schema: {len(tables)} tables")
        return tables
    
    def analyze_schema_fast(self, query: str) -> str:
        """
        Fast schema analysis using hardcoded business rules
        """
        start_time = __import__('time').time()
        
        try:
            # Get schema
            tables = self._get_schema_fast()
            if not tables:
                return "No tables available"
            
            query_lower = query.lower()
            relevant_tables = []
            analysis_reasoning = []
            
            # Fast domain-based matching
            for domain, config in self.domain_mappings.items():
                domain_score = 0
                
                # Check keywords in query
                for keyword in config['keywords']:
                    if keyword in query_lower:
                        domain_score += 1
                        analysis_reasoning.append(f"Found {domain} keyword: '{keyword}'")
                
                # If domain is relevant, find matching tables
                if domain_score > 0:
                    for table in tables:
                        table_name_lower = table.name.lower()
                        schema_name_lower = table.schema.lower() if table.schema else ""
                        
                        # Check table name matches
                        for table_pattern in config['tables']:
                            if (table_pattern in table_name_lower or 
                                table_pattern in schema_name_lower):
                                if table not in relevant_tables:
                                    relevant_tables.append(table)
                                    analysis_reasoning.append(f"Matched {domain} table: {table.schema}.{table.name}")
            
            # If no domain matches, do simple keyword matching
            if not relevant_tables:
                analysis_reasoning.append("No domain matches, using keyword fallback")
                query_words = [word for word in query_lower.split() if len(word) > 3]
                
                for table in tables:
                    table_match_score = 0
                    table_name_lower = table.name.lower()
                    
                    for word in query_words:
                        if word in table_name_lower:
                            table_match_score += 1
                        
                        # Check column names too
                        for col in table.columns[:5]:  # First 5 columns only for speed
                            if word in col.name.lower():
                                table_match_score += 0.5
                    
                    if table_match_score > 0:
                        relevant_tables.append((table, table_match_score))
                
                # Sort by score and take top matches
                if relevant_tables:
                    relevant_tables = [table for table, score in 
                                     sorted(relevant_tables, key=lambda x: x[1], reverse=True)[:3]]
            
            # Format result
            if not relevant_tables:
                # Return first few tables as fallback
                relevant_tables = tables[:3]
                analysis_reasoning.append("No matches found, showing first 3 tables")
            
            processing_time = __import__('time').time() - start_time
            
            result = f"AIRPLANE MODE SCHEMA ANALYSIS (⚡ {processing_time:.3f}s)\n\n"
            result += f"Analysis: {' | '.join(analysis_reasoning)}\n\n"
            result += "RELEVANT TABLES:\n"
            
            for table in relevant_tables[:3]:  # Limit to 3 for speed
                result += f"\nTable: {table.schema}.{table.name}\n"
                
                # Show key columns first (PK, FK, then others)
                pk_cols = [col for col in table.columns if col.is_primary_key]
                fk_cols = [col for col in table.columns if col.is_foreign_key]
                other_cols = [col for col in table.columns 
                             if not col.is_primary_key and not col.is_foreign_key]
                
                # Display in priority order, limit to 5 total
                display_cols = (pk_cols + fk_cols + other_cols)[:5]
                
                for col in display_cols:
                    pk = " [PK]" if col.is_primary_key else ""
                    fk = " [FK]" if col.is_foreign_key else ""
                    nullable = "NULL" if col.is_nullable else "NOT NULL"
                    result += f"  - {col.name}: {col.data_type} {nullable}{pk}{fk}\n"
                
                if len(table.columns) > 5:
                    result += f"  ... and {len(table.columns) - 5} more columns\n"
            
            return result
            
        except Exception as e:
            return f"Airplane mode error: {str(e)}"
        
    def analyze_schema_for_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze schema for a specific query and return structured data
        Used by the intelligent agent
        """
        try:
            # Get the fast schema analysis result  
            schema_text = self.analyze_schema_fast(query)
            
            # Get hardcoded schema for structured data
            tables = self._get_hardcoded_schema()
            
            # Extract relevant table info based on query
            query_lower = query.lower()
            relevant_tables = []
            
            # Simple keyword matching for table relevance
            for table in tables:
                table_name = table.name.lower()
                if (table_name in query_lower or 
                    any(keyword in query_lower for keyword in ['customer', 'product', 'order', 'sale']
                        if keyword in table_name)):
                    relevant_tables.append({
                        'name': table.name,
                        'schema': table.schema, 
                        'columns': [{
                            'name': col.name,
                            'type': col.data_type,
                            'nullable': col.is_nullable,
                            'primary_key': col.is_primary_key,
                            'foreign_key': col.is_foreign_key
                        } for col in table.columns[:10]]  # Limit columns for speed
                    })
            
            return {
                'schema_text': schema_text,
                'relevant_tables': relevant_tables,
                'analysis_method': 'airplane_mode',
                'processing_time_ms': 1  # Always fast in airplane mode
            }
            
        except Exception as e:
            logger.error(f"Schema analysis error: {e}")
            return {
                'schema_text': f"Error: {str(e)}",
                'relevant_tables': [],
                'analysis_method': 'airplane_mode_error',
                'processing_time_ms': 1
            }
