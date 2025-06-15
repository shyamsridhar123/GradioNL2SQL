"""
Stored Procedure Tool for Smolagents
Executes only whitelisted stored procedures with validated parameters
"""

from smolagents import Tool
import sys
import os
from typing import Dict, Any, List

# Add parent directory to path to import database modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.connection import DatabaseConnection
from database.config import DatabaseConfig

class StoredProcedureTool(Tool):
    name = "stored_procedure_executor"
    description =    """
    Executes whitelisted stored procedures on Azure SQL Server with validated parameters.
    Only pre-approved procedures can be executed for security.    """
    inputs = {
        "procedure_name": {
            "type": "string",
            "description": "Name of the stored procedure to execute"
        },
        "parameters": {
            "type": "string",
            "description": "JSON string of parameters for the stored procedure",
            "nullable": True
        }
    }
    output_type = "string"

    def __init__(self):
        super().__init__()
        # Initialize database connection - use Azure AD authentication
        self.config = DatabaseConfig.from_env(use_managed_identity=True)
        self.db_connection = DatabaseConnection(self.config)
        
        # Whitelist of allowed stored procedures
        self.whitelisted_procedures = [
            "usp_GenerateMonthlyReport",
            "usp_GetCustomerSummary", 
            "usp_GetSalesReport",
            "usp_GetProductAnalysis"
        ]
        
    def forward(self, procedure_name: str, parameters: str = "{}") -> str:
        """
        Execute whitelisted stored procedure with parameters
        """
        try:
            # Validate procedure is whitelisted
            if procedure_name not in self.whitelisted_procedures:
                return f"Error: Stored procedure '{procedure_name}' is not whitelisted for execution."
            
            # Parse parameters
            try:
                import json
                params = json.loads(parameters) if parameters else {}
            except json.JSONDecodeError:
                return "Error: Invalid JSON format for parameters."
            
            # Build procedure call
            if params:
                param_list = ", ".join([f"@{key} = :{key}" for key in params.keys()])
                sql = f"EXEC {procedure_name} {param_list}"
            else:
                sql = f"EXEC {procedure_name}"
            
            # Execute stored procedure
            results = self.db_connection.execute_query(sql, params)
            
            if results:
                # Format results as text
                result_text = f"Executed: {procedure_name}\n"
                result_text += f"Rows returned: {len(results)}\n"
                result_text += "Results:\n"
                
                # Show first few rows
                for i, row in enumerate(results[:10]):
                    result_text += f"Row {i+1}: {dict(row)}\n"
                
                if len(results) > 10:
                    result_text += f"... and {len(results) - 10} more rows\n"
                
                return result_text
            else:
                return f"Stored procedure '{procedure_name}' executed successfully. No rows returned."
                
        except Exception as e:
            return f"Error executing stored procedure: {str(e)}"
    
    def get_whitelisted_procedures(self) -> List[str]:
        """
        Return list of whitelisted procedures
        """
        return self.whitelisted_procedures.copy()
