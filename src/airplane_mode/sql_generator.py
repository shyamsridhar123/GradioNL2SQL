"""
Airplane Mode SQL Generator
Fast template-based SQL generation without LLM calls
"""

import re
from typing import Dict, Any, List, Optional
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.logging_config import get_logger

logger = get_logger("airplane_mode.sql_generator")

class AirplaneModeSQLGenerator:
    """
    Fast SQL generation using templates and business rules
    """
    
    def __init__(self):
        # SQL templates for common query patterns
        self.sql_templates = {
            'show_all_customers': {
                'pattern': r'show\s+(all\s+)?customers?',
                'template': "SELECT * FROM {customer_table} ORDER BY {customer_id}",
                'tables_needed': ['customer']
            },
            'show_all_products': {
                'pattern': r'show\s+(all\s+)?products?',
                'template': "SELECT * FROM {product_table} ORDER BY {product_id}",
                'tables_needed': ['product']
            },
            'show_all_orders': {
                'pattern': r'show\s+(all\s+)?(orders?|sales?)',
                'template': "SELECT * FROM {order_table} ORDER BY {order_date} DESC",
                'tables_needed': ['order', 'sales']
            },
            'count_customers': {
                'pattern': r'(how\s+many|count)\s+customers?',
                'template': "SELECT COUNT(*) as customer_count FROM {customer_table}",
                'tables_needed': ['customer']
            },
            'count_products': {
                'pattern': r'(how\s+many|count)\s+products?',
                'template': "SELECT COUNT(*) as product_count FROM {product_table}",
                'tables_needed': ['product']
            },
            'total_sales': {
                'pattern': r'total\s+sales?',
                'template': "SELECT SUM({amount_column}) as total_sales FROM {sales_table}",
                'tables_needed': ['sales', 'order']
            },
            'sales_by_customer': {
                'pattern': r'sales?\s+by\s+customers?',
                'template': """
                SELECT c.{customer_name}, SUM(s.{amount_column}) as total_sales
                FROM {customer_table} c
                JOIN {sales_table} s ON c.{customer_id} = s.{customer_id}
                GROUP BY c.{customer_id}, c.{customer_name}
                ORDER BY total_sales DESC
                """,
                'tables_needed': ['customer', 'sales']
            },
            'sales_by_region': {
                'pattern': r'sales?\s+by\s+region',
                'template': """
                SELECT a.{region_column}, SUM(s.{amount_column}) as total_sales
                FROM {sales_table} s
                JOIN {customer_table} c ON s.{customer_id} = c.{customer_id}
                JOIN {address_table} a ON c.{address_id} = a.{address_id}
                GROUP BY a.{region_column}
                ORDER BY total_sales DESC
                """,
                'tables_needed': ['sales', 'customer', 'address']
            },
            'sales_by_product': {
                'pattern': r'sales?\s+by\s+products?',
                'template': """
                SELECT p.{product_name}, SUM(sd.{quantity_column} * sd.{price_column}) as total_sales
                FROM {product_table} p
                JOIN {sales_detail_table} sd ON p.{product_id} = sd.{product_id}
                GROUP BY p.{product_id}, p.{product_name}
                ORDER BY total_sales DESC
                """,
                'tables_needed': ['product', 'sales_detail']
            }
        }
        
        # Common column name patterns
        self.column_patterns = {
            'customer_id': ['customerid', 'customer_id', 'custid', 'id'],
            'customer_name': ['customername', 'customer_name', 'name', 'fullname', 'firstname'],
            'product_id': ['productid', 'product_id', 'id'],
            'product_name': ['productname', 'product_name', 'name', 'title'],
            'order_id': ['orderid', 'order_id', 'salesorderid', 'id'],
            'order_date': ['orderdate', 'order_date', 'date', 'created_date', 'salesorderdate'],
            'amount_column': ['total', 'amount', 'totalprice', 'subtotal', 'totaldue'],
            'quantity_column': ['quantity', 'qty', 'orderqty'],
            'price_column': ['price', 'unitprice', 'listprice'],            'address_id': ['addressid', 'address_id', 'id'],
            'region_column': ['region', 'state', 'stateprovince', 'country', 'territory']
        }
    
    def _find_table_by_type(self, tables: List[Any], table_type: str) -> Optional[Any]:
        """Find table by business type (customer, product, etc.)"""
        type_patterns = {
            'customer': ['customer', 'client', 'user', 'person'],
            'product': ['product', 'item', 'catalog'],
            'sales': ['sales', 'order'],
            'order': ['order', 'sales'],
            'sales_detail': ['orderdetail', 'salesorderdetail', 'detail'],
            'address': ['address', 'location']
        }
        
        patterns = type_patterns.get(table_type, [table_type])
        
        for table in tables:
            # Handle both dictionary and object formats
            if isinstance(table, dict):
                table_name_lower = table.get('name', '').lower()
            else:
                table_name_lower = table.name.lower()
                
            for pattern in patterns:
                if pattern in table_name_lower:                    return table
        return None
    
    def _find_column_by_pattern(self, table: Any, column_type: str) -> Optional[str]:
        """Find column by pattern matching"""
        patterns = self.column_patterns.get(column_type, [column_type])
        
        # Handle both dictionary and object formats
        if isinstance(table, dict):
            columns = table.get('columns', [])
        else:
            columns = table.columns
            
        for col in columns:
            # Handle both dictionary and object formats for columns
            if isinstance(col, dict):
                col_name_lower = col.get('name', '').lower()
                col_name = col.get('name', '')
            else:
                col_name_lower = col.name.lower()
                col_name = col.name
                
            for pattern in patterns:
                if pattern in col_name_lower:
                    return col_name
          # If no pattern match, return first column for ID types
        if column_type.endswith('_id') and columns:
            # Look for primary key first
            for col in columns:
                if isinstance(col, dict):
                    if col.get('primary_key', False):
                        return col.get('name', '')
                else:
                    if col.is_primary_key:
                        return col.name
            # Fallback to first column
            if isinstance(columns[0], dict):
                return columns[0].get('name', '')
            else:
                return columns[0].name
        
        return None
    
    def generate_sql_fast(self, query: str, tables: List[Any]) -> str:
        """
        Generate SQL using templates and pattern matching
        """
        start_time = __import__('time').time()
        
        try:
            query_lower = query.lower().strip()
            
            # Find matching template
            for template_name, config in self.sql_templates.items():
                if re.search(config['pattern'], query_lower):
                    logger.info(f"Airplane mode: matched template '{template_name}'")
                    
                    # Find required tables
                    table_mappings = {}
                    column_mappings = {}
                    
                    for table_type in config['tables_needed']:
                        table = self._find_table_by_type(tables, table_type)
                        if table:
                            table_key = f"{table_type}_table"
                            # Handle both dictionary and object formats
                            if isinstance(table, dict):
                                table_name = table.get('name', '')
                                table_schema = table.get('schema', '')
                            else:
                                table_name = table.name
                                table_schema = table.schema
                            table_mappings[table_key] = f"{table_schema}.{table_name}"
                            
                            # Find columns for this table
                            for column_type in self.column_patterns.keys():
                                if column_type.startswith(table_type) or column_type in ['amount_column', 'quantity_column', 'price_column', 'region_column']:
                                    column = self._find_column_by_pattern(table, column_type)
                                    if column:
                                        column_mappings[column_type] = column
                    
                    # Generate SQL from template
                    template_sql = config['template']
                    
                    # Replace table placeholders
                    for key, value in table_mappings.items():
                        template_sql = template_sql.replace(f"{{{key}}}", value)
                    
                    # Replace column placeholders
                    for key, value in column_mappings.items():
                        template_sql = template_sql.replace(f"{{{key}}}", value)
                    
                    # Clean up any remaining placeholders
                    template_sql = re.sub(r'\{[^}]+\}', 'UNKNOWN_COLUMN', template_sql)
                    
                    # Format and clean SQL
                    formatted_sql = ' '.join(template_sql.split())
                    
                    processing_time = __import__('time').time() - start_time
                    
                    result = f"-- AIRPLANE MODE SQL (⚡ {processing_time:.3f}s)\n"
                    result += f"-- Template: {template_name}\n"
                    result += f"-- Pattern: {config['pattern']}\n\n"
                    result += formatted_sql
                    
                    return result
            
            # No template matched - generate basic SELECT
            if tables:
                main_table = tables[0]  # Use first table as fallback
                processing_time = __import__('time').time() - start_time
                result = f"-- AIRPLANE MODE FALLBACK SQL (⚡ {processing_time:.3f}s)\n"
                result += f"-- No specific template matched, showing basic query\n\n"
                result += f"SELECT * FROM {main_table['schema']}.{main_table['name']} ORDER BY 1"
                
                return result
            
            return "-- No tables available for SQL generation"
            
        except Exception as e:
            logger.error(f"Debug: Error details: {str(e)}")
            logger.error(f"Debug: Exception type: {type(e)}")
            import traceback
            logger.error(f"Debug: Full traceback: {traceback.format_exc()}")
            return f"-- Airplane mode SQL generation error: {str(e)}"
        
    def generate_sql(self, query: str, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate SQL using airplane mode and return structured result
        Compatible with intelligent agent expectations
        """
        try:            # Extract tables from schema_info
            tables = schema_info.get("relevant_tables", [])
            
            # Generate SQL using the fast method
            sql_result = self.generate_sql_fast(query, tables)
            
            # Check if generation was successful
            if sql_result and not sql_result.startswith("-- No tables") and not sql_result.startswith("-- Airplane mode SQL generation error"):
                return {
                    "success": True,
                    "sql": sql_result,
                    "explanation": "SQL generated using airplane mode templates",
                    "method": "airplane_mode",
                    "confidence": 0.9
                }
            else:
                return {
                    "success": False,
                    "sql": "",
                    "explanation": f"Airplane mode generation failed: {sql_result}",
                    "method": "airplane_mode",
                    "confidence": 0.0
                }
                
        except Exception as e:
            return {
                "success": False,
                "sql": "",
                "explanation": f"Error in airplane mode SQL generation: {str(e)}",
                "method": "airplane_mode",
                "confidence": 0.0
            }
