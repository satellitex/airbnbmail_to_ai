"""Compatibility module for the LLM analyzer.

This module re-exports the LLMAnalyzer from the new modular structure
to maintain backward compatibility.
"""

import warnings

from airbnmail_to_ai.parser.llm import LLMAnalyzer
from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)

# Issue a deprecation warning
warnings.warn(
    "The module airbnmail_to_ai.parser.llm_analyzer is deprecated. "
    "Please use airbnmail_to_ai.parser.llm.LLMAnalyzer instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Log deprecation warning as well
logger.warning(
    "Using deprecated module airbnmail_to_ai.parser.llm_analyzer. "
    "Please update your imports to use airbnmail_to_ai.parser.llm.LLMAnalyzer."
)

# Re-export the analyzer
__all__ = ["LLMAnalyzer"]
