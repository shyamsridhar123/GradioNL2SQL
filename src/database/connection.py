"""Azure SQL Server database connection manager with retry logic and connection pooling."""

import pyodbc
import logging
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple, Generator
from threading import Lock
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import DatabaseConfig

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Azure SQL Server connection manager with connection pooling and retry logic."""
    
    def __init__(self, config: DatabaseConfig):
        """Initialize database connection manager."""
        self.config = config
        self._engine: Optional[Engine] = None
        self._lock = Lock()
        
        # Connection pool settings
        self._pool_size = 10
        self._max_overflow = 20
        self._pool_timeout = 30
        self._pool_recycle = 3600  # 1 hour
        
        logger.info("DatabaseConnection initialized")
    
    @property
    def engine(self) -> Engine:
        """Get SQLAlchemy engine with connection pooling."""
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    self._create_engine()
        return self._engine
    
    def _create_engine(self) -> None:
        """Create SQLAlchemy engine with connection pooling."""
        try:
            connection_url = self.config.get_sqlalchemy_url()
            
            # Create engine with connection pooling
            self._engine = create_engine(
                connection_url,
                poolclass=QueuePool,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_timeout=self._pool_timeout,
                pool_recycle=self._pool_recycle,
                pool_pre_ping=True,  # Validates connections before use
                echo=False,  # Set to True for SQL debugging
                execution_options={
                    "isolation_level": "READ_COMMITTED"
                }
            )
            
            logger.info("SQLAlchemy engine created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create database engine: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((pyodbc.Error, sqlalchemy.exc.SQLAlchemyError))
    )
    def test_connection(self) -> bool:
        """Test database connection with retry logic."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                
                if test_value == 1:
                    logger.info("Database connection test successful")
                    return True
                else:
                    logger.error("Database connection test failed: unexpected result")
                    return False
                    
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise
    
    @contextmanager
    def get_connection(self) -> Generator[sqlalchemy.engine.Connection, None, None]:
        """Get database connection with automatic cleanup."""
        conn = None
        try:
            conn = self.engine.connect()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((pyodbc.Error, sqlalchemy.exc.SQLAlchemyError))
    )
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute SELECT query with retry logic."""
        try:
            with self.get_connection() as conn:
                if params:
                    result = conn.execute(text(query), params)
                else:
                    result = conn.execute(text(query))
                
                # Convert result to list of dictionaries
                rows = []
                for row in result:
                    rows.append(dict(row._mapping))
                
                logger.debug(f"Query executed successfully, returned {len(rows)} rows")
                return rows
                
        except Exception as e:
            logger.error(f"Query execution failed: {query[:100]}... Error: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((pyodbc.Error, sqlalchemy.exc.SQLAlchemyError))
    )
    def execute_non_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Execute non-SELECT query (INSERT, UPDATE, DELETE) with retry logic."""
        try:
            with self.get_connection() as conn:
                with conn.begin():  # Use transaction
                    if params:
                        result = conn.execute(text(query), params)
                    else:
                        result = conn.execute(text(query))
                    
                    affected_rows = result.rowcount
                    logger.debug(f"Non-query executed successfully, affected {affected_rows} rows")
                    return affected_rows
                    
        except Exception as e:
            logger.error(f"Non-query execution failed: {query[:100]}... Error: {e}")
            raise
    
    def execute_batch(self, queries: List[Tuple[str, Optional[Dict[str, Any]]]]) -> List[int]:
        """Execute multiple queries in a transaction."""
        try:
            with self.get_connection() as conn:
                with conn.begin():
                    results = []
                    for query, params in queries:
                        if params:
                            result = conn.execute(text(query), params)
                        else:
                            result = conn.execute(text(query))
                        results.append(result.rowcount)
                    
                    logger.debug(f"Batch execution completed successfully, {len(queries)} queries")
                    return results
                    
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get Azure SQL Server information."""
        try:
            query = """
            SELECT 
                @@VERSION as version,
                @@SERVERNAME as server_name,
                DB_NAME() as database_name,
                SYSTEM_USER as current_user,
                GETDATE() as current_time
            """
            
            result = self.execute_query(query)
            if result:
                return result[0]
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get server info: {e}")
            return {}
    
    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            logger.info("Database connections closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
