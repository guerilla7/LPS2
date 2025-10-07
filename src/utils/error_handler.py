"""Common error handling utilities for LPS2.

This module provides standardized error handling patterns,
error codes, and helper functions for returning errors to clients.
"""
from flask import jsonify
from typing import Dict, Any, Tuple, Union, Optional
import logging
import traceback

logger = logging.getLogger("lps2")

# Standard error codes
class ErrorCode:
    """Standard error codes for the application."""
    # Authentication errors (1000-1099)
    AUTH_REQUIRED = 1001
    INVALID_CREDENTIALS = 1002
    SESSION_EXPIRED = 1003
    INSUFFICIENT_PERMISSIONS = 1004
    CSRF_MISSING = 1005
    CSRF_INVALID = 1006
    
    # Rate limiting errors (1100-1199)
    RATE_LIMIT_EXCEEDED = 1101
    
    # Input validation errors (1200-1299)
    INVALID_INPUT = 1201
    MISSING_REQUIRED_FIELD = 1202
    INVALID_FORMAT = 1203
    
    # Server errors (1500-1599)
    INTERNAL_ERROR = 1500
    SERVICE_UNAVAILABLE = 1501
    DATABASE_ERROR = 1502
    EXTERNAL_SERVICE_ERROR = 1503
    
    # Content errors (1300-1399)
    CONTENT_BLOCKED = 1301
    CONTENT_NOT_FOUND = 1302


def error_response(message: str, 
                   code: int, 
                   http_status: int = 400, 
                   details: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], int]:
    """Create a standardized error response.
    
    Args:
        message: Human-readable error message
        code: Application-specific error code
        http_status: HTTP status code to return
        details: Additional error details (optional)
        
    Returns:
        Tuple of (response_dict, http_status_code)
    """
    response = {
        "error": True,
        "message": message,
        "code": code
    }
    
    if details:
        response["details"] = details
        
    return jsonify(response), http_status


def log_error(error_type: str, message: str, exception: Optional[Exception] = None) -> None:
    """Log an error with consistent formatting.
    
    Args:
        error_type: Category/type of error
        message: Error message
        exception: Optional exception object
    """
    error_log = f"[{error_type}] {message}"
    
    if exception:
        error_log += f"\nException: {str(exception)}"
        error_log += f"\nTraceback: {traceback.format_exc()}"
        
    logger.error(error_log)


def handle_request_exception(e: Exception) -> Tuple[Dict[str, Any], int]:
    """Global exception handler for unhandled exceptions.
    
    Args:
        e: The exception object
        
    Returns:
        Standardized error response
    """
    log_error("UNHANDLED", "Unhandled exception in request", e)
    
    return error_response(
        message="An unexpected error occurred while processing your request.",
        code=ErrorCode.INTERNAL_ERROR,
        http_status=500
    )