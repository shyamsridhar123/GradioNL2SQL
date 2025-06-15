"""Test Azure SQL Server connection."""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from database.config import DatabaseConfig
from database.connection import DatabaseConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_azure_sql_connection():
    """Test connection to Azure SQL Server."""
    try:
        print("🔍 Testing Azure SQL Server Connection...")
          # Load configuration from environment
        # Since you have username/password, we'll use SQL authentication
        config = DatabaseConfig.from_env(use_managed_identity=False)
        
        print(f"📊 Server: {config.server}")
        print(f"📊 Database: {config.database}")
        print(f"🔐 Using Managed Identity: {config.use_managed_identity}")
        
        # Create connection
        with DatabaseConnection(config) as db:
            print("🔗 Testing basic connection...")
            
            # Test connection
            if db.test_connection():
                print("✅ Connection successful!")
                
                # Get server info
                print("\n📈 Server Information:")
                server_info = db.get_server_info()
                for key, value in server_info.items():
                    print(f"   {key}: {value}")
                
                # Test schema inspection
                print("\n🔍 Testing schema inspection...")
                from database.schema_inspector import SchemaInspector
                
                inspector = SchemaInspector(db)
                
                # Get all tables
                tables = inspector.get_all_tables()
                print(f"📊 Found {len(tables)} tables:")
                
                for table in tables[:5]:  # Show first 5 tables
                    print(f"   • {table.schema}.{table.name} ({len(table.columns)} columns)")
                    
                    # Show first few columns
                    for col in table.columns[:3]:
                        nullable = "NULL" if col.is_nullable else "NOT NULL"
                        pk = " [PK]" if col.is_primary_key else ""
                        fk = " [FK]" if col.is_foreign_key else ""
                        print(f"     - {col.name}: {col.data_type} {nullable}{pk}{fk}")
                
                if len(tables) > 5:
                    print(f"   ... and {len(tables) - 5} more tables")
                
                print("✅ Schema inspection successful!")
                
            else:
                print("❌ Connection test failed!")
                return False
                
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n💡 Make sure to:")
        print("   1. Set your environment variables in .env file")
        print("   2. Install required packages: pip install -r requirements.txt")
        print("   3. Configure Azure SQL Server firewall rules")
        print("   4. Set up Managed Identity if using Azure-hosted resources")
        return False
    
    return True

if __name__ == "__main__":
    success = test_azure_sql_connection()
    sys.exit(0 if success else 1)
