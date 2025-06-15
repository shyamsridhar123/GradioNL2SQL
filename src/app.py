"""
Gradio UI f# Initialize the Intelligent Agent
logger.info("Initializing Int        # Create comprehensive log message
        log_lines = [
            f"**Status:** {'Success' if success else 'Failed'}",
            f"**Query:** {user_input}",
            f"**Results:** {len(results)} rows returned" if success else "**Error occurred**",
            f"**Details:** {log_message}"
        ]t Text2SQL Agent...")
text2sql_agent = IntelligentText2SQLAgent()
logger.info("Intelligent Text2SQL Agent initialized successfully")ntelligent Text2SQL Agent
Clean, simple interface for natural language to SQL conversion
"""

import gradio as gr
import pandas as pd
import json
from typing import Dict, Any, List
from agents.intelligent_agent import IntelligentText2SQLAgent
from utils.logging_config import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO", log_file="logs/text2sql_app.log")
logger = get_logger("text2sql.app")

# Initialize the Intelligent Agent
logger.info("Initializing Intelligent Text2SQL Agent...")
text2sql_agent = IntelligentText2SQLAgent()
logger.info("Intelligent Text2SQL Agent initialized successfully")

def safe_str_conversion(value: Any) -> str:
    """
    Safely convert any value to string, handling encoding issues
    
    Args:
        value: The value to convert to string
        
    Returns:
        String representation of the value
    """
    if value is None:
        return ""
    
    try:
        # If it's already a string, check if it has encoding issues
        if isinstance(value, str):
            return value
        
        # If it's bytes, decode with error handling
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8')
            except UnicodeDecodeError:
                # Try with different encodings or use error handling
                try:
                    return value.decode('latin-1')
                except UnicodeDecodeError:
                    # Last resort: replace problematic bytes
                    return value.decode('utf-8', errors='replace')
        
        # For other types, convert to string
        return str(value)
    
    except Exception as e:
        # If all else fails, return a safe representation
        return f"<Unable to display: {type(value).__name__}>"


def format_results_for_display(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Format query results for Gradio Dataframe display
    
    Args:
        results: List of dictionaries from database query
        
    Returns:
        pandas DataFrame for Gradio display
    """
    if not results:
        return pd.DataFrame({"Message": ["No results returned"]})
    
    try:
        # Convert to DataFrame
        df = pd.DataFrame(results)
        
        # Convert any datetime objects to strings with proper encoding handling
        for col in df.columns:
            if df[col].dtype == 'object':
                # Handle potential encoding issues by converting each value individually
                df[col] = df[col].apply(lambda x: safe_str_conversion(x))
        
        logger.info(f"Formatted {len(results)} rows with {len(df.columns)} columns for display")
        return df
    
    except Exception as e:
        logger.error(f"Error formatting results: {e}")
        return pd.DataFrame({"Error": [f"Could not format results: {str(e)}"]})

def handle_user_query(user_input: str) -> tuple:
    """
    Handle user query and return results for Gradio interface
    
    Args:
        user_input: The user's natural language query
        
    Returns:
        Tuple of (sql_code, results_dataframe, log_message)
    """
    if not user_input or not user_input.strip():
        return "-- No query provided", pd.DataFrame({"Message": ["Please enter a query"]}), "No input provided"
    
    logger.info(f"Processing query: {user_input[:100]}...")
    
    try:
        # Process the query using the intelligent agent
        result = text2sql_agent.process_query_mode(user_input)
        
        # Extract components
        sql_code = result.get("sql", "No SQL generated")
        results = result.get("results", [])
        success = result.get("success", False)
        log_message = result.get("log", "No log information")
        
        # Format results for display
        results_df = format_results_for_display(results)
        
        # Create comprehensive log message
        log_lines = [
            f"**Status:** {'Success' if success else 'Failed'}",
            f"**Query:** {user_input}",
            f"**Results:** {len(results)} rows returned" if success else "**Error occurred**",
            f"**Details:** {log_message}"
        ]
        
        if "schema_used" in result:
            log_lines.append(f"**Schema:** {len(result['schema_used'])} characters")
        
        if "error_corrected" in result:
            log_lines.append(f"**Error Correction:** Applied")
            log_lines.append(f"**Original Error:** {result['error_corrected']}")
        
        formatted_log = "\n\n".join(log_lines)
        
        logger.info(f"Query processed successfully. Success: {success}, Rows: {len(results)}")
        
        return sql_code, results_df, formatted_log
        
    except Exception as e:
        error_msg = f"Application error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        error_log = f"""
**Status:** Application Error
**Query:** {user_input}
**Error:** {error_msg}
**Suggestion:** Please try a simpler query or check the logs for more details.
"""
        
        return f"-- Error processing query: {error_msg}", pd.DataFrame({"Error": [error_msg]}), error_log

# Gradio UI layout
with gr.Blocks(title="Intelligent Text2SQL Agent", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Intelligent Text2SQL Agent")
    gr.Markdown("Convert natural language queries into SQL using intelligent LLM orchestration")
    
    with gr.Row():
        user_input = gr.Textbox(
            label="Your Natural Language Query",
            placeholder="e.g., Show me the top 10 customers by revenue",
            lines=3,
            scale=4
        )
        submit_btn = gr.Button("Submit", variant="primary", scale=1, size="lg")
    
    with gr.Row():
        sql_out = gr.Code(label="Generated SQL", language="sql", lines=10)
    
    with gr.Row():
        results_out = gr.Dataframe(label="Results", wrap=True)
    
    with gr.Row():
        log_out = gr.Markdown(label="Execution Log", value="Ready to process queries...")
    
    # Event handlers
    submit_btn.click(
        handle_user_query,
        inputs=[user_input],
        outputs=[sql_out, results_out, log_out]
    )
    
    user_input.submit(
        handle_user_query,
        inputs=[user_input],
        outputs=[sql_out, results_out, log_out]
    )

def main():
    logger.info("Starting Gradio application...")    
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        debug=True
    )

if __name__ == "__main__":
    main()
