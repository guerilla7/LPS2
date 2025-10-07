"""User management utilities.

This module provides functionality for user management, including:
- Secure password handling and validation
- User creation, validation, and management
- Password policy enforcement
"""

import re
import secrets
import string
from typing import Dict, Any, Optional, List, Tuple
from werkzeug.security import generate_password_hash, check_password_hash

# Password requirements
MIN_PASSWORD_LENGTH = 8
REQUIRE_UPPER = True
REQUIRE_LOWER = True
REQUIRE_DIGITS = True
REQUIRE_SPECIAL = True
SPECIAL_CHARS = string.punctuation

def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password strength against security requirements.
    
    Args:
        password: The password to validate
        
    Returns:
        Tuple of (is_valid, list_of_failure_reasons)
    """
    errors = []
    
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
        
    if REQUIRE_UPPER and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
        
    if REQUIRE_LOWER and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
        
    if REQUIRE_DIGITS and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")
        
    if REQUIRE_SPECIAL and not any(c in SPECIAL_CHARS for c in password):
        errors.append(f"Password must contain at least one special character ({SPECIAL_CHARS})")
        
    return len(errors) == 0, errors

def generate_secure_password() -> str:
    """Generate a secure random password that meets all requirements."""
    while True:
        # Generate a 16-character password with at least one character from each required group
        password = ''.join([
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(SPECIAL_CHARS),
            *[secrets.choice(string.ascii_letters + string.digits + SPECIAL_CHARS) 
              for _ in range(12)]
        ])
        
        # Shuffle to avoid predictable pattern
        password_list = list(password)
        secrets.SystemRandom().shuffle(password_list)
        password = ''.join(password_list)
        
        # Ensure it meets all requirements (should always be true, but double-check)
        is_valid, _ = validate_password_strength(password)
        if is_valid:
            return password

def hash_password(password: str) -> str:
    """
    Hash a password securely using Werkzeug's generate_password_hash.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Securely hashed password
    """
    # Using pbkdf2:sha256 with 50000 iterations (Werkzeug's default method)
    return generate_password_hash(password)

def verify_password(stored_hash: str, provided_password: str) -> bool:
    """
    Verify a password against a stored hash.
    
    Args:
        stored_hash: Previously hashed password
        provided_password: Plain text password to verify
        
    Returns:
        True if password matches, False otherwise
    """
    return check_password_hash(stored_hash, provided_password)

def normalize_username(username: str) -> str:
    """
    Normalize a username for consistent comparisons.
    
    Args:
        username: Raw username
        
    Returns:
        Normalized username
    """
    return username.strip().lower()