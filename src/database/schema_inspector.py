"""Schema inspection utilities for Azure SQL Server."""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .connection import DatabaseConnection

logger = logging.getLogger(__name__)

@dataclass
class ColumnInfo:
    """Information about a database column."""
    name: str
    data_type: str
    is_nullable: bool
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    default_value: Optional[str] = None

@dataclass
class TableInfo:
    """Information about a database table."""
    schema: str
    name: str
    columns: List[ColumnInfo]
    row_count: Optional[int] = None

@dataclass
class ForeignKeyInfo:
    """Information about foreign key relationships."""
    constraint_name: str
    source_schema: str
    source_table: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str

class SchemaInspector:
    """Inspect Azure SQL Server database schema and metadata."""
    
    def __init__(self, db_connection: DatabaseConnection):
        """Initialize schema inspector."""
        self.db = db_connection
        logger.info("SchemaInspector initialized")
    
    def get_all_tables(self, schema_name: Optional[str] = None) -> List[TableInfo]:
        """Get information about all tables in the database."""
        try:
            where_clause = f"AND t.TABLE_SCHEMA = '{schema_name}'" if schema_name else ""
            
            query = f"""
            SELECT 
                t.TABLE_SCHEMA,
                t.TABLE_NAME,
                COUNT(c.COLUMN_NAME) as COLUMN_COUNT
            FROM INFORMATION_SCHEMA.TABLES t
            LEFT JOIN INFORMATION_SCHEMA.COLUMNS c ON t.TABLE_NAME = c.TABLE_NAME 
                AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            {where_clause}
            GROUP BY t.TABLE_SCHEMA, t.TABLE_NAME
            ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
            """
            
            results = self.db.execute_query(query)
            tables = []
            
            for row in results:
                # Get detailed column information for each table
                columns = self.get_table_columns(row['TABLE_SCHEMA'], row['TABLE_NAME'])
                
                table_info = TableInfo(
                    schema=row['TABLE_SCHEMA'],
                    name=row['TABLE_NAME'],
                    columns=columns
                )
                tables.append(table_info)
            
            logger.info(f"Retrieved {len(tables)} tables from database")
            return tables
            
        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            raise
    
    def get_table_columns(self, schema_name: str, table_name: str) -> List[ColumnInfo]:
        """Get detailed column information for a specific table."""
        try:
            query = """
            SELECT 
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.IS_NULLABLE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.NUMERIC_PRECISION,
                c.NUMERIC_SCALE,
                c.COLUMN_DEFAULT,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as IS_PRIMARY_KEY,
                CASE WHEN fk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as IS_FOREIGN_KEY
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku 
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA 
                AND c.TABLE_NAME = pk.TABLE_NAME 
                AND c.COLUMN_NAME = pk.COLUMN_NAME
            LEFT JOIN (
                SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku 
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
            ) fk ON c.TABLE_SCHEMA = fk.TABLE_SCHEMA 
                AND c.TABLE_NAME = fk.TABLE_NAME 
                AND c.COLUMN_NAME = fk.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = :schema_name AND c.TABLE_NAME = :table_name
            ORDER BY c.ORDINAL_POSITION
            """
            
            params = {"schema_name": schema_name, "table_name": table_name}
            results = self.db.execute_query(query, params)
            
            columns = []
            for row in results:
                column = ColumnInfo(
                    name=row['COLUMN_NAME'],
                    data_type=row['DATA_TYPE'],
                    is_nullable=row['IS_NULLABLE'] == 'YES',
                    max_length=row['CHARACTER_MAXIMUM_LENGTH'],
                    precision=row['NUMERIC_PRECISION'],
                    scale=row['NUMERIC_SCALE'],
                    is_primary_key=bool(row['IS_PRIMARY_KEY']),
                    is_foreign_key=bool(row['IS_FOREIGN_KEY']),
                    default_value=row['COLUMN_DEFAULT']
                )
                columns.append(column)
            
            return columns
            
        except Exception as e:
            logger.error(f"Failed to get columns for {schema_name}.{table_name}: {e}")
            raise
    
    def get_foreign_keys(self, schema_name: Optional[str] = None) -> List[ForeignKeyInfo]:
        """Get foreign key relationships in the database."""
        try:
            where_clause = f"AND tc.TABLE_SCHEMA = '{schema_name}'" if schema_name else ""
            
            query = f"""
            SELECT 
                tc.CONSTRAINT_NAME,
                tc.TABLE_SCHEMA as SOURCE_SCHEMA,
                tc.TABLE_NAME as SOURCE_TABLE,
                kcu.COLUMN_NAME as SOURCE_COLUMN,
                ccu.TABLE_SCHEMA as TARGET_SCHEMA,
                ccu.TABLE_NAME as TARGET_TABLE,
                ccu.COLUMN_NAME as TARGET_COLUMN
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu 
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu 
                ON ccu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
            {where_clause}
            ORDER BY tc.TABLE_SCHEMA, tc.TABLE_NAME, kcu.COLUMN_NAME
            """
            
            results = self.db.execute_query(query)
            
            foreign_keys = []
            for row in results:
                fk = ForeignKeyInfo(
                    constraint_name=row['CONSTRAINT_NAME'],
                    source_schema=row['SOURCE_SCHEMA'],
                    source_table=row['SOURCE_TABLE'],
                    source_column=row['SOURCE_COLUMN'],
                    target_schema=row['TARGET_SCHEMA'],
                    target_table=row['TARGET_TABLE'],
                    target_column=row['TARGET_COLUMN']
                )
                foreign_keys.append(fk)
            
            logger.info(f"Retrieved {len(foreign_keys)} foreign key relationships")
            return foreign_keys
            
        except Exception as e:
            logger.error(f"Failed to get foreign keys: {e}")
            raise
    
    def get_table_sample_data(self, schema_name: str, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample data from a table."""
        try:
            query = f"SELECT TOP {limit} * FROM [{schema_name}].[{table_name}]"
            results = self.db.execute_query(query)
            
            logger.debug(f"Retrieved {len(results)} sample rows from {schema_name}.{table_name}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to get sample data from {schema_name}.{table_name}: {e}")
            raise
    
    def get_database_schema_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of the database schema."""
        try:
            # Get all tables
            tables = self.get_all_tables()
            
            # Get foreign keys
            foreign_keys = self.get_foreign_keys()
            
            # Create summary
            schema_summary = {
                "total_tables": len(tables),
                "schemas": {},
                "foreign_keys": len(foreign_keys),
                "tables": []
            }
            
            # Group tables by schema
            schema_counts = {}
            for table in tables:
                if table.schema not in schema_counts:
                    schema_counts[table.schema] = 0
                schema_counts[table.schema] += 1
                
                # Add table info to summary
                table_summary = {
                    "schema": table.schema,
                    "name": table.name,
                    "column_count": len(table.columns),
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.data_type,
                            "nullable": col.is_nullable,
                            "primary_key": col.is_primary_key,
                            "foreign_key": col.is_foreign_key
                        }
                        for col in table.columns
                    ]
                }
                schema_summary["tables"].append(table_summary)
            
            schema_summary["schemas"] = schema_counts
            
            logger.info(f"Generated database schema summary: {len(tables)} tables across {len(schema_counts)} schemas")
            return schema_summary
            
        except Exception as e:
            logger.error(f"Failed to generate schema summary: {e}")
            raise
    
    def search_tables_by_name(self, search_term: str) -> List[TableInfo]:
        """Search for tables by name pattern."""
        try:
            query = """
            SELECT DISTINCT
                t.TABLE_SCHEMA,
                t.TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES t
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            AND (t.TABLE_NAME LIKE :search_pattern OR t.TABLE_SCHEMA LIKE :search_pattern)
            ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
            """
            
            search_pattern = f"%{search_term}%"
            params = {"search_pattern": search_pattern}
            results = self.db.execute_query(query, params)
            
            tables = []
            for row in results:
                columns = self.get_table_columns(row['TABLE_SCHEMA'], row['TABLE_NAME'])
                table_info = TableInfo(
                    schema=row['TABLE_SCHEMA'],
                    name=row['TABLE_NAME'],
                    columns=columns
                )
                tables.append(table_info)
            
            logger.info(f"Found {len(tables)} tables matching pattern '{search_term}'")
            return tables
            
        except Exception as e:
            logger.error(f"Failed to search tables by name '{search_term}': {e}")
            raise
