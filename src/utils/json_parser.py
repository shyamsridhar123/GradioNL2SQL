"""
Robust JSON parsing utilities for LLM responses
"""
import json
import re
import logging
from typing import Optional, Union, Dict, List, Any

logger = logging.getLogger(__name__)

def extract_and_parse_json(content: str, expected_type: str = "object") -> Optional[Union[Dict, List]]:
    """
    Robustly extract and parse JSON from LLM response content.
    
    Args:
        content: Raw LLM response content
        expected_type: "object" for {}, "array" for [], "any" for either
    
    Returns:
        Parsed JSON object/array or None if parsing fails
    """
    if not content or not content.strip():
        logger.warning("Empty content provided for JSON parsing")
        return None
    
    content = content.strip()
    
    # Try multiple parsing strategies
    strategies = [
        _parse_direct_json,
        _parse_code_block_json,
        _parse_extracted_json,
        _parse_cleaned_json
    ]
    
    for strategy in strategies:
        try:
            result = strategy(content, expected_type)
            if result is not None:
                if expected_type == "object" and isinstance(result, dict):
                    return result
                elif expected_type == "array" and isinstance(result, list):
                    return result
                elif expected_type == "any":
                    return result
        except Exception as e:
            logger.debug(f"JSON parsing strategy failed: {strategy.__name__}: {e}")
            continue
    
    logger.warning(f"All JSON parsing strategies failed for content: {content[:200]}...")
    return None

def _parse_direct_json(content: str, expected_type: str) -> Optional[Union[Dict, List]]:
    """Try to parse content directly as JSON"""
    return json.loads(content)

def _parse_code_block_json(content: str, expected_type: str) -> Optional[Union[Dict, List]]:
    """Extract JSON from markdown code blocks"""
    # Look for ```json blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', content, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    
    # Look for ``` blocks without language specifier
    code_match = re.search(r'```\s*(\{.*?\}|\[.*?\])\s*```', content, re.DOTALL)
    if code_match:
        return json.loads(code_match.group(1))
    
    return None

def _parse_extracted_json(content: str, expected_type: str) -> Optional[Union[Dict, List]]:
    """Extract JSON using improved regex patterns"""
    if expected_type in ["object", "any"]:
        # More precise object extraction
        patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested objects
            r'\{[^{}]+\}'  # Simple objects
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                try:
                    result = json.loads(match)
                    if isinstance(result, dict):
                        return result
                except:
                    continue
    
    if expected_type in ["array", "any"]:
        # More precise array extraction
        patterns = [
            r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]',  # Nested arrays
            r'\[[^\[\]]+\]'  # Simple arrays
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                try:
                    result = json.loads(match)
                    if isinstance(result, list):
                        return result
                except:
                    continue
    
    return None

def _parse_cleaned_json(content: str, expected_type: str) -> Optional[Union[Dict, List]]:
    """Clean content and try to parse as JSON"""
    # Remove common LLM artifacts
    cleaned = content
    
    # Remove markdown formatting
    cleaned = re.sub(r'```(?:json)?', '', cleaned)
    cleaned = re.sub(r'```', '', cleaned)
    
    # Remove explanatory text before/after JSON
    if expected_type in ["object", "any"] and '{' in cleaned:
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        if start >= 0 and end > start:
            cleaned = cleaned[start:end]
    elif expected_type in ["array", "any"] and '[' in cleaned:
        start = cleaned.find('[')
        end = cleaned.rfind(']') + 1
        if start >= 0 and end > start:
            cleaned = cleaned[start:end]
    
    # Remove trailing commas and fix common issues
    cleaned = re.sub(r',\s*}', '}', cleaned)
    cleaned = re.sub(r',\s*]', ']', cleaned)
    
    try:
        return json.loads(cleaned.strip())
    except:
        return None

def validate_json_structure(data: Dict, required_keys: List[str]) -> bool:
    """
    Validate that a parsed JSON object has required keys
    
    Args:
        data: Parsed JSON object
        required_keys: List of required key names
    
    Returns:
        True if all required keys are present
    """
    if not isinstance(data, dict):
        return False
    
    return all(key in data for key in required_keys)

def create_fallback_response(response_type: str, **kwargs) -> Dict[str, Any]:
    """
    Create a fallback response when JSON parsing fails
    
    Args:
        response_type: Type of response ("intent", "schema", "approach", "failure")
        **kwargs: Additional parameters for specific response types
    
    Returns:
        Fallback response dictionary
    """
    if response_type == "intent":
        return {
            "complexity": kwargs.get("complexity", "medium"),
            "confidence": 0.5,
            "strategy": "direct_sql",
            "reasoning": "Fallback analysis due to parsing failure",
            "key_entities": [],
            "requires_joins": False,
            "estimated_rows": 100        }
    elif response_type == "approach":
        complexity = kwargs.get("complexity", "medium")
        import os
        default_model = os.getenv("DEFAULT_AGENT_MODEL", "gpt-4.1")
        complex_model = os.getenv("COMPLEX_AGENT_MODEL", "o4-mini")
        return {
            "approach": "direct_generation",
            "llm_model": complex_model if complexity == "complex" else default_model,
            "expected_iterations": 1,
            "confidence": 0.6,
            "reasoning": "Fallback approach selection"
        }
    elif response_type == "failure":
        return {
            "should_retry": False,
            "diagnosis": "Could not analyze failures due to parsing error",
            "confidence": 0.0,
            "alternative_approach": "Use airplane mode fallback"
        }
    else:
        return {"error": "Unknown response type", "fallback": True}
