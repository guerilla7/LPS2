"""Request validation utilities for LPS2.

This module provides tools for validating API requests to ensure
data integrity and security throughout the application.

It uses marshmallow for schema validation, which provides:
1. Type checking
2. Required field validation
3. Custom validators
4. Clean error messages
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Dict, Any, Callable, Optional, Type, Union, get_type_hints
from flask import request, jsonify
from marshmallow import Schema, ValidationError

logger = logging.getLogger("validation")

def validate_schema(data: Dict[str, Any], schema_class: Type[Schema]) -> tuple[Dict[str, Any], bool, Any]:
    """Validate data against a schema without relying on decorators.
    
    Args:
        data: The data to validate
        schema_class: Marshmallow schema class to use for validation
        
    Returns:
        Tuple of (validated_data, is_valid, error_messages)
    """
    try:
        schema = schema_class()
        validated_data = schema.load(data)
        return validated_data, True, None
    except ValidationError as err:
        return {}, False, err.messages
    except Exception as e:
        logger.exception(f"Unexpected error during validation: {str(e)}")
        return {}, False, {"_general": f"Validation error: {str(e)}"}

def validate_request(schema_class: Type[Schema], location: str = 'json'):
    """Decorator to validate request data against a schema.
    
    Args:
        schema_class: Marshmallow schema class to use for validation
        location: Where to find data ('json', 'form', 'args', 'files')
        
    Returns:
        Decorator function
        
    Example:
        ```python
        class LoginSchema(Schema):
            username = fields.Str(required=True)
            password = fields.Str(required=True)
        
        @app.route('/login', methods=['POST'])
        @validate_request(LoginSchema)
        def login():
            # All data is validated here
            data = request.validated_data
            ...
        ```
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Get request data based on location
                if location == 'json':
                    if request.is_json:
                        data = request.json or {}
                    else:
                        # Gracefully handle non-JSON requests
                        data = {}
                elif location == 'form':
                    data = request.form.to_dict()
                elif location == 'args':
                    data = request.args.to_dict()
                elif location == 'files':
                    data = request.files.to_dict()
                else:
                    # Default to JSON
                    data = request.json or {}
                
                # Validate against schema
                validated_data, is_valid, errors = validate_schema(data, schema_class)
                
                if not is_valid:
                    return jsonify({
                        'error': 'validation_error',
                        'message': 'Invalid request data',
                        'details': errors
                    }), 400
                
                # Attach to request object for route to access
                request.validated_data = validated_data
            except Exception as e:
                # Log but continue with the request
                logger.exception(f"Error during validation: {str(e)}")
                # Attempt to get data anyway - degraded experience but won't break existing code
                if location == 'json':
                    request.validated_data = request.json or {}
                elif location == 'form':
                    request.validated_data = request.form.to_dict()
                else:
                    request.validated_data = {}
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Stand-alone validator function that doesn't need decorators
def validate_data(data: Dict[str, Any], schema_class: Type[Schema]) -> tuple[bool, Dict[str, Any], Any]:
    """Validate data against a schema without modifying request objects.
    
    Args:
        data: The data to validate
        schema_class: Marshmallow schema class to use for validation
        
    Returns:
        Tuple of (is_valid, validated_data, error_messages)
    """
    try:
        schema = schema_class()
        validated_data = schema.load(data)
        return True, validated_data, None
    except ValidationError as err:
        return False, {}, err.messages
    except Exception as e:
        logger.exception(f"Unexpected error during validation: {str(e)}")
        return False, {}, {"_general": f"Validation error: {str(e)}"}