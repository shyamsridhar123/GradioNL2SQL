"""Database configuration for Azure SQL Server."""

import os
from dataclasses import dataclass
from typing import Optional
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
import logging

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Configuration class for Azure SQL Server connection."""
    
    server: str
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    driver: str = "SQL Server"
    encrypt: bool = False  # Disable encryption for basic driver
    trust_server_certificate: bool = True
    connection_timeout: int = 30
    command_timeout: int = 30
    use_managed_identity: bool = True
    
    @classmethod
    def from_env(cls, use_managed_identity: bool = False) -> "DatabaseConfig":  # Changed default to False
        """Create configuration from environment variables."""
        # Support multiple naming conventions for environment variables
        server = (os.getenv("DATABASE_SERVER") or 
                 os.getenv("AZURE_SQL_SERVER") or 
                 os.getenv("SQL_SERVER"))
        
        database = (os.getenv("DATABASE_NAME") or 
                   os.getenv("AZURE_SQL_DATABASE") or 
                   os.getenv("SQL_DATABASE"))
        
        username = None
        password = None
        
        # Always try to get username/password from env first
        username = (os.getenv("DATABASE_USERNAME") or 
                   os.getenv("AZURE_SQL_USERNAME") or 
                   os.getenv("SQL_USERNAME"))
        password = (os.getenv("DATABASE_PASSWORD") or 
                   os.getenv("AZURE_SQL_PASSWORD") or 
                   os.getenv("SQL_PASSWORD"))
        
        # If we have username/password, don't use managed identity
        if username and password:
            use_managed_identity = False
        
        if not use_managed_identity:
            if not username or not password:
                # Only use managed identity if no credentials provided
                use_managed_identity = True
                
        # Get driver with fallback options - use modern ODBC driver for Azure SQL
        driver = (os.getenv("DATABASE_DRIVER") or 
                 os.getenv("SQL_DRIVER") or 
                 "ODBC Driver 18 for SQL Server")  # Use ODBC Driver 18 which is installed
        
        config = cls(
            server=server or "",
            database=database or "",
            username=username,
            password=password,
            driver=driver,
            use_managed_identity=use_managed_identity,
            connection_timeout=int(os.getenv("AZURE_SQL_CONNECTION_TIMEOUT", "30")),
            command_timeout=int(os.getenv("AZURE_SQL_COMMAND_TIMEOUT", "30")),
            trust_server_certificate=os.getenv("TRUST_SERVER_CERTIFICATE", "false").lower() == "true"
        )
        
        if not config.server or not config.database:
            available_vars = [k for k in os.environ.keys() if any(x in k.upper() for x in ['SQL', 'DATABASE', 'SERVER'])]
            raise ValueError(
                f"Database server and database name are required. "
                f"Available environment variables: {available_vars}"
            )
        
        logger.info(f"Database config created for server: {config.server}, database: {config.database}")
        return config
    
    def get_connection_string(self) -> str:
        """Generate connection string for Azure SQL Server."""
        if self.use_managed_identity:
            # Using Managed Identity - no username/password needed
            conn_str = (
                f"Driver={{{self.driver}}};"
                f"Server=tcp:{self.server},1433;"
                f"Database={self.database};"
                f"Encrypt={'yes' if self.encrypt else 'no'};"
                f"TrustServerCertificate={'yes' if self.trust_server_certificate else 'no'};"
                f"Connection Timeout={self.connection_timeout};"
                f"Authentication=ActiveDirectoryMsi;"
            )
        else:
            # Using SQL authentication
            if not self.username or not self.password:
                raise ValueError("Username and password are required when not using managed identity")            
            conn_str = (
                f"Driver={{{self.driver}}};"
                f"Server=tcp:{self.server},1433;"
                f"Database={self.database};"
                f"Uid={self.username};"
                f"Pwd={self.password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout={self.connection_timeout};"
            )
        
        return conn_str
    
    def get_sqlalchemy_url(self) -> str:
        """Generate SQLAlchemy URL for Azure SQL Server."""
        import urllib.parse
        
        if self.use_managed_identity:
            # For Azure AD authentication - check if we have a specific user
            azure_ad_user = os.getenv("AZURE_AD_USER")
            
            if azure_ad_user:
                # External/Guest user authentication
                params = {
                    "driver": self.driver,
                    "server": self.server,
                    "database": self.database,
                    "UID": azure_ad_user,
                    "Encrypt": "yes",
                    "TrustServerCertificate": "yes" if self.trust_server_certificate else "no",
                    "Connection Timeout": str(self.connection_timeout),
                    "Authentication": "ActiveDirectoryPassword",
                    "PWD": os.getenv("AZURE_AD_PASSWORD", "")
                }
            else:
                # Managed identity authentication (for Azure VMs/Functions)
                params = {
                    "driver": self.driver,
                    "server": self.server,
                    "database": self.database,
                    "Encrypt": "yes",
                    "TrustServerCertificate": "yes" if self.trust_server_certificate else "no",
                    "Connection Timeout": str(self.connection_timeout),
                    "Authentication": "ActiveDirectoryMsi"
                }              # Build proper ODBC connection string for Azure AD
            odbc_string = ";".join([f"{k}={v}" for k, v in params.items()])
            encoded_string = urllib.parse.quote_plus(odbc_string)
            return f"mssql+pyodbc:///?odbc_connect={encoded_string}"
            
        else:
            # SQL authentication
            if not self.username or not self.password:
                raise ValueError("Username and password are required when not using managed identity")
            
            # Use ODBC connection string format for SQL authentication
            params = {
                "driver": self.driver,
                "server": f"tcp:{self.server},1433",
                "database": self.database,
                "uid": self.username,
                "pwd": self.password,
                "Encrypt": "yes",
                "TrustServerCertificate": "no",
                "Connection Timeout": str(self.connection_timeout)
            }
            
            # Build ODBC connection string
            odbc_string = ";".join([f"{k}={v}" for k, v in params.items()])
            encoded_string = urllib.parse.quote_plus(odbc_string)
            return f"mssql+pyodbc:///?odbc_connect={encoded_string}"
