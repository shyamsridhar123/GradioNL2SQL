"""
Database Connection and SQL Query Diagnostic Tool
Helps debug connection issues and SQL formatting problems
"""

import sys
import os
import re
from typing import Dict, Any

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.connection import DatabaseConnection
from database.config import DatabaseConfig
from database.schema_inspector import SchemaInspector
from utils.logging_config import setup_logging, get_logger

# Setup logging
setup_logging(log_level="DEBUG", log_file="logs/diagnostic.log")
logger = get_logger("text2sql.diagnostic")

def validate_sql_query(sql: str) -> Dict[str, Any]:
    """
    Validate SQL query for common issues that cause HY090 errors
    """
    issues = []
    
    # Check for empty or None query
    if not sql or sql.strip() == "":
        issues.append("Query is empty or None")
        return {"valid": False, "issues": issues}
    
    # Check for null characters
    if '\x00' in sql:
        issues.append("Query contains null characters")
    
    # Check for very long lines that might cause buffer issues
    lines = sql.split('\n')
    for i, line in enumerate(lines):
        if len(line) > 4000:
            issues.append(f"Line {i+1} is too long ({len(line)} chars)")
    
    # Check for malformed SQL patterns
    sql_lower = sql.lower().strip()
    
    # Must start with valid SQL command
    valid_starts = ['select', 'with', 'insert', 'update', 'delete', 'create', 'alter', 'drop']
    if not any(sql_lower.startswith(start) for start in valid_starts):
        issues.append("Query doesn't start with valid SQL command")
    
    # Check for unmatched parentheses
    open_parens = sql.count('(')
    close_parens = sql.count(')')
    if open_parens != close_parens:
        issues.append(f"Unmatched parentheses: {open_parens} open, {close_parens} close")
    
    # Check for unmatched quotes
    single_quotes = sql.count("'")
    if single_quotes % 2 != 0:
        issues.append("Unmatched single quotes")
    
    # Check for common encoding issues
    try:
        sql.encode('utf-8')
    except UnicodeEncodeError:
        issues.append("Query contains invalid Unicode characters")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "length": len(sql),
        "lines": len(lines)
    }

def test_basic_connection():
    """Test basic database connection"""
    print("\n" + "="*60)
    print("TESTING BASIC DATABASE CONNECTION")
    print("="*60)
    
    try:
        config = DatabaseConfig.from_env(use_managed_identity=False)
        db_connection = DatabaseConnection(config)
        
        print("✅ Database config loaded")
        print(f"Server: {config.server}")
        print(f"Database: {config.database}")
        print(f"Driver: {config.driver}")
        
        # Test connection
        if db_connection.test_connection():
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed: {str(e)}")
        logger.error("Connection test failed", exc_info=True)
        return False

def test_simple_query():
    """Test simple SELECT 1 query"""
    print("\n" + "="*60)
    print("TESTING SIMPLE QUERY")
    print("="*60)
    
    try:
        config = DatabaseConfig.from_env(use_managed_identity=False)
        db_connection = DatabaseConnection(config)
        
        # Test very simple query
        simple_queries = [
            "SELECT 1 as test",
            "SELECT GETDATE() as current_time",
            "SELECT @@VERSION as version"
        ]
        
        for query in simple_queries:
            print(f"\nTesting: {query}")
            try:
                results = db_connection.execute_query(query)
                print(f"✅ Success: {len(results)} rows returned")
                if results:
                    print(f"   Result: {results[0]}")
            except Exception as e:
                print(f"❌ Failed: {str(e)}")
                
    except Exception as e:
        print(f"❌ Simple query test failed: {str(e)}")
        logger.error("Simple query test failed", exc_info=True)

def test_schema_inspection():
    """Test schema inspection functionality"""
    print("\n" + "="*60)
    print("TESTING SCHEMA INSPECTION")
    print("="*60)
    
    try:
        config = DatabaseConfig.from_env(use_managed_identity=False)
        db_connection = DatabaseConnection(config)
        schema_inspector = SchemaInspector(db_connection)
        
        # Get all tables
        tables = schema_inspector.get_all_tables()
        print(f"✅ Found {len(tables)} tables")
        
        # Show first few tables
        for i, table in enumerate(tables[:3]):
            print(f"   {i+1}. {table.schema}.{table.name} ({len(table.columns)} columns)")
            
        return tables
        
    except Exception as e:
        print(f"❌ Schema inspection failed: {str(e)}")
        logger.error("Schema inspection failed", exc_info=True)
        return []

def test_sql_generation_and_validation():
    """Test SQL generation and validate the output"""
    print("\n" + "="*60)
    print("TESTING SQL GENERATION AND VALIDATION")
    print("="*60)
    
    try:
        # Import SQL generation tool
        from tools.sql_generation_tool import SQLGenerationTool
        
        sql_tool = SQLGenerationTool()
        
        # Test with simple query
        user_query = "Show me all customers"
        schema_info = "Table: dbo.Customers\n  - CustomerID: int NOT NULL [PK]\n  - CustomerName: varchar(100) NOT NULL"
        
        print(f"User Query: {user_query}")
        print("Generating SQL...")
        
        generated_sql = sql_tool.forward(user_query, schema_info)
        print(f"Generated SQL:\n{generated_sql}")
        
        # Validate the generated SQL
        validation = validate_sql_query(generated_sql)
        print(f"\nSQL Validation:")
        print(f"Valid: {validation['valid']}")
        print(f"Length: {validation['length']} characters")
        print(f"Lines: {validation['lines']}")
        
        if validation['issues']:
            print("Issues found:")
            for issue in validation['issues']:
                print(f"  - {issue}")
        
        # Try to execute the generated SQL
        if validation['valid']:
            print("\nTesting execution...")
            try:
                config = DatabaseConfig.from_env(use_managed_identity=False)
                db_connection = DatabaseConnection(config)
                
                results = db_connection.execute_query(generated_sql)
                print(f"✅ Execution successful: {len(results)} rows")
                
            except Exception as e:
                print(f"❌ Execution failed: {str(e)}")
                
                # Log the exact SQL that failed
                print(f"\nFailed SQL (hex): {generated_sql.encode('utf-8').hex()}")
                
    except Exception as e:
        print(f"❌ SQL generation test failed: {str(e)}")
        logger.error("SQL generation test failed", exc_info=True)

def main():
    """Run all diagnostic tests"""
    print("Text2SQL Database Diagnostic Tool")
    print("="*60)
    
    # Test 1: Basic connection
    connection_ok = test_basic_connection()
    
    # Test 2: Simple queries
    if connection_ok:
        test_simple_query()
        
        # Test 3: Schema inspection
        tables = test_schema_inspection()
        
        # Test 4: SQL generation and validation
        if tables:
            test_sql_generation_and_validation()
    
    print("\n" + "="*60)
    print("DIAGNOSTIC COMPLETE")
    print("="*60)
    print("Check logs/diagnostic.log for detailed information")

if __name__ == "__main__":
    main()
