"""
Quick SQL Generation Test
Generate SQL and inspect it for issues
"""

import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_sql_generation():
    """Quick test of SQL generation"""
    try:
        from tools.sql_generation_tool import SQLGenerationTool
        
        print("Testing SQL Generation...")
        sql_tool = SQLGenerationTool()
        
        # Simple test query
        user_query = "Show total sales by region for the current year"
        schema_info = """Table: dbo.Orders
  - OrderID: int NOT NULL [PK]
  - CustomerID: int NOT NULL [FK]
  - OrderDate: datetime NOT NULL
  - TotalAmount: decimal(10,2) NOT NULL

Table: dbo.Customers  
  - CustomerID: int NOT NULL [PK]
  - CustomerName: varchar(100) NOT NULL
  - Region: varchar(50) NOT NULL"""
        
        print(f"Query: {user_query}")
        print("Generating SQL...")
        
        sql_result = sql_tool.forward(user_query, schema_info)
        
        print("="*60)
        print("GENERATED SQL:")
        print("="*60)
        print(sql_result)
        print("="*60)
        
        # Check for common issues
        print(f"SQL Length: {len(sql_result)}")
        print(f"SQL Type: {type(sql_result)}")
        print(f"Contains null chars: {'\\x00' in sql_result}")
        print(f"Starts with: '{sql_result[:20]}...'")
        print(f"Ends with: '...{sql_result[-20:]}'")
        
        # Show hex representation of first/last chars
        if sql_result:
            print(f"First 50 chars (hex): {sql_result[:50].encode('utf-8').hex()}")
            print(f"Last 50 chars (hex): {sql_result[-50:].encode('utf-8').hex()}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sql_generation()
