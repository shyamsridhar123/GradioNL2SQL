"""
Schema Analyst Tool for Smolagents
Extracts relevant schema details from Azure SQL (tables, columns, relationships)
"""

from smolagents import Tool
import sys
import os
from typing import Dict, Any

# Add parent directory to path to import database modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.connection import DatabaseConnection
from database.config import DatabaseConfig
from database.schema_inspector import SchemaInspector

class SchemaAnalystTool(Tool):
    name = "schema_analyst"
    description =    """
    Analyzes the Azure SQL database schema to find relevant tables, columns, and relationships
    for a given user query. Returns structured schema information needed for SQL generation.
    """
    inputs = {
        "user_query": {
            "type": "string", 
            "description": "The user's natural language query to analyze for relevant schema"
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
        # Initialize database connection
        self.config = DatabaseConfig.from_env(use_managed_identity=False)
        self.db_connection = DatabaseConnection(self.config)
        self.schema_inspector = SchemaInspector(self.db_connection)
        
        # Cache schema to avoid repeated DB calls
        self._schema_cache = None
        self._load_schema_cache()
        
    def _load_schema_cache(self):
        """Load and cache the complete schema once"""
        try:
            self._schema_cache = self.schema_inspector.get_all_tables()
            print(f"✅ Schema cache loaded: {len(self._schema_cache)} tables")
        except Exception as e:
            print(f"❌ Failed to load schema cache: {e}")
            self._schema_cache = []
    def forward(self, user_query: str) -> str:
        """
        Analyze user query and return relevant schema information
        """
        try:
            # Get all tables from cache
            all_tables = self._schema_cache if self._schema_cache else []
            
            if not all_tables:
                return "No tables found in database schema"
            
            # Improved keyword matching to find relevant tables
            relevant_tables = []
            query_lower = user_query.lower()
            
            # Define keyword mappings for common business terms
            keyword_mappings = {
                'customer': ['customer', 'client', 'user', 'buyer'],
                'order': ['order', 'purchase', 'transaction', 'sale'],  
                'product': ['product', 'item', 'goods', 'inventory'],
                'sales': ['sales', 'revenue', 'order', 'purchase'],
                'region': ['region', 'territory', 'area', 'location', 'address', 'state', 'city'],
                'category': ['category', 'type', 'class', 'group'],
                'price': ['price', 'cost', 'amount', 'total', 'due', 'value'],
                'date': ['date', 'time', 'when', 'period']
            }
            
            # Score tables based on relevance
            table_scores = {}
            
            for table in all_tables:
                score = 0
                table_name_lower = table.name.lower()
                
                # Direct table name match
                if table_name_lower in query_lower:
                    score += 10
                
                # Check against keyword mappings
                for concept, keywords in keyword_mappings.items():
                    if any(keyword in query_lower for keyword in keywords):
                        if concept in table_name_lower:
                            score += 8
                        # Check column names too
                        for col in table.columns:
                            if concept in col.name.lower():
                                score += 5
                
                # Column name matches
                for col in table.columns:
                    col_name_lower = col.name.lower()
                    if col_name_lower in query_lower:
                        score += 6
                    # Partial matches for common terms
                    for word in query_lower.split():
                        if len(word) > 3 and word in col_name_lower:
                            score += 3
                
                if score > 0:
                    table_scores[table] = score
            
            # If no matches found, return all tables (let SQL generation decide)
            if not table_scores:
                print(f"⚠️ No relevant tables found for query: {user_query}")
                print(f"Available tables: {[t.name for t in all_tables]}")
                relevant_tables = all_tables  # Return all tables
            else:
                # Sort by score and take top matches
                relevant_tables = [table for table, score in sorted(table_scores.items(), key=lambda x: x[1], reverse=True)][:5]
            
            # Format schema information
            schema_info = []
            for table in relevant_tables[:5]:  # Limit to 5 most relevant tables
                table_info = f"Table: {table.schema}.{table.name}\n"
                for col in table.columns:
                    pk_marker = " [PK]" if col.is_primary_key else ""
                    fk_marker = " [FK]" if col.is_foreign_key else ""
                    nullable = "NULL" if col.is_nullable else "NOT NULL"
                    table_info += f"  - {col.name}: {col.data_type} {nullable}{pk_marker}{fk_marker}\n"
                schema_info.append(table_info)
            
            if schema_info:
                return "RELEVANT SCHEMA:\n" + "\n".join(schema_info)
            else:
                return "No relevant tables found"
            
        except Exception as e:
            return f"Error analyzing schema: {str(e)}"
