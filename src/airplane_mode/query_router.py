"""
Airplane Mode Query Router
Decides when to use fast hardcoded mode vs intelligent LLM mode
"""

import re
from typing import Dict, Any, Tuple
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.logging_config import get_logger

logger = get_logger("airplane_mode.router")

class AirplaneModeRouter:
    """
    Intelligent router that decides between airplane mode (fast) and LLM mode (intelligent)
    """
    
    def __init__(self):
        # Patterns that can be handled by airplane mode (hardcoded)
        self.airplane_patterns = {
            'simple_show': [
                r'show\s+(all\s+)?tables?',
                r'list\s+(all\s+)?tables?',
                r'show\s+schema',
                r'describe\s+database'
            ],
            'basic_select': [
                r'show\s+(all\s+)?(customers?|users?)',
                r'show\s+(all\s+)?(products?|items?)',
                r'show\s+(all\s+)?(orders?|sales?)',
                r'list\s+(all\s+)?(customers?|products?|orders?)'
            ],
            'simple_count': [
                r'how\s+many\s+(customers?|products?|orders?)',
                r'count\s+(customers?|products?|orders?)',
                r'total\s+(customers?|products?|orders?)'
            ],
            'basic_aggregates': [
                r'total\s+sales?',
                r'sum\s+of\s+sales?',
                r'show\s+sales?\s+by\s+(region|customer|product)',
                r'sales?\s+by\s+(region|customer|product)'
            ]
        }
        
        # Complex patterns that need LLM intelligence
        self.llm_required_patterns = [
            r'complex\s+join',
            r'nested\s+query',
            r'subquery',
            r'case\s+when',
            r'window\s+function',
            r'recursive',
            r'pivot',
            r'calculate.*formula',
            r'if.*then.*else',
            r'multiple\s+conditions.*and.*or'
        ]
    
    def should_use_airplane_mode(self, query: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Determine if query can be handled by airplane mode
        
        Returns:
            (use_airplane_mode, reasoning, metadata)
        """
        query_lower = query.lower().strip()
        
        # Check if query explicitly requires LLM
        for pattern in self.llm_required_patterns:
            if re.search(pattern, query_lower):
                return False, f"Complex pattern detected: {pattern}", {"complexity": "high"}
        
        # Check if query can be handled by airplane mode
        for category, patterns in self.airplane_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return True, f"Simple pattern matched: {category}", {
                        "category": category,
                        "pattern": pattern,
                        "confidence": 0.9
                    }
        
        # Default: use LLM for unknown patterns
        return False, "Unknown pattern, using LLM for safety", {"complexity": "unknown"}
    
    def get_airplane_handler(self, query: str) -> str:
        """
        Get the appropriate airplane mode handler for the query
        """
        _, _, metadata = self.should_use_airplane_mode(query)
        return metadata.get("category", "basic_select")
