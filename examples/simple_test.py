"""
Test script to check environment and basic functionality
"""
import os
print("Environment variables check:")
print(f"AZURE_OPENAI_API_KEY: {'SET' if os.getenv('AZURE_OPENAI_API_KEY') else 'NOT SET'}")
print(f"AZURE_OPENAI_ENDPOINT: {os.getenv('AZURE_OPENAI_ENDPOINT', 'NOT SET')}")

# Check all possible database variable names
db_vars = [
    'DATABASE_SERVER', 'AZURE_SQL_SERVER', 'SQL_SERVER',
    'DATABASE_NAME', 'AZURE_SQL_DATABASE', 'SQL_DATABASE',
    'DATABASE_USERNAME', 'AZURE_SQL_USERNAME', 'SQL_USERNAME',
    'DATABASE_PASSWORD', 'AZURE_SQL_PASSWORD', 'SQL_PASSWORD'
]

print("\nDatabase variables:")
for var in db_vars:
    value = os.getenv(var)
    if value:
        # Mask password
        if 'PASSWORD' in var:
            print(f"{var}: {'*' * len(value)}")
        else:
            print(f"{var}: {value}")
    else:
        print(f"{var}: NOT SET")

print(f"\nAll environment variables containing 'SQL' or 'DATABASE':")
for key in sorted(os.environ.keys()):
    if any(word in key.upper() for word in ['SQL', 'DATABASE', 'SERVER']):
        value = os.environ[key]
        # Mask sensitive values
        if any(word in key.upper() for word in ['PASSWORD', 'KEY', 'SECRET']):
            value = '*' * len(value)
        print(f"  {key}: {value}")

# Test basic import
try:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
    from database.config import DatabaseConfig
    config = DatabaseConfig.from_env(use_managed_identity=False)
    print(f"✅ Database config loaded: {config.server}/{config.database}")
except Exception as e:
    print(f"❌ Database config failed: {e}")

# Test SQL cleaning function
def test_sql_cleaning():
    test_cases = [
        "```sql\nSELECT * FROM customers\n```",
        "```\nSELECT * FROM orders\n```",
        "SELECT * FROM products\n\nNote: This query returns all products",
        "\x00SELECT * FROM invalid",  # null character
        "Some explanation\nSELECT * FROM test\nMore explanation"
    ]
    
    for i, test_sql in enumerate(test_cases):
        print(f"\nTest {i+1}: {repr(test_sql[:50])}")
        # Simulate cleaning
        cleaned = test_sql.replace('\x00', '').strip()
        if cleaned.startswith("```sql"):
            cleaned = cleaned.replace("```sql", "").replace("```", "").strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.replace("```", "").strip()
        print(f"Cleaned: {repr(cleaned[:50])}")

print("\n" + "="*50)
print("SQL CLEANING TESTS")
print("="*50)
test_sql_cleaning()
