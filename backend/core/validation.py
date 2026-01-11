"""
Input validation and sanitization for security.

Provides validation utilities to prevent injection attacks and ensure
data integrity across the application.
"""
import re
import html
import logging
from typing import Any, Optional
from functools import wraps

from pydantic import BaseModel, field_validator, ConfigDict
from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ========== SECURITY PATTERNS ==========

# Patterns that might indicate injection attempts
INJECTION_PATTERNS = [
    r'<script[^>]*>.*?</script>',  # Script tags
    r'javascript:',                 # JavaScript URLs
    r'on\w+\s*=',                   # Event handlers
    r'{{.*}}',                      # Template injection
    r'\$\{.*\}',                    # Template literals
    r'SELECT\s+.*\s+FROM',          # SQL injection
    r'INSERT\s+INTO',               # SQL injection
    r'DELETE\s+FROM',               # SQL injection
    r'UPDATE\s+.*\s+SET',           # SQL injection
    r'DROP\s+TABLE',                # SQL injection
    r'UNION\s+SELECT',              # SQL injection
    r';\s*--',                      # SQL comment injection
]

# Compiled patterns for performance
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in INJECTION_PATTERNS]

# Valid file extensions for uploads
ALLOWED_EXTENSIONS = {
    'bom': {'.xlsx', '.xls', '.csv', '.pdf'},
    'image': {'.png', '.jpg', '.jpeg', '.gif', '.webp'},
    'document': {'.pdf', '.docx', '.doc', '.txt'},
}

# Maximum field lengths
MAX_LENGTHS = {
    'name': 255,
    'description': 2000,
    'notes': 5000,
    'part_number': 100,
    'email': 254,
    'url': 2048,
}


# ========== VALIDATION FUNCTIONS ==========

def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a string by escaping HTML entities and trimming.

    Args:
        value: The string to sanitize
        max_length: Optional maximum length to truncate to

    Returns:
        Sanitized string
    """
    if not value:
        return value

    # Trim whitespace
    sanitized = value.strip()

    # Escape HTML entities
    sanitized = html.escape(sanitized)

    # Truncate if needed
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def check_injection(value: str) -> bool:
    """
    Check if a string contains potential injection patterns.

    Args:
        value: The string to check

    Returns:
        True if injection patterns detected, False otherwise
    """
    if not value:
        return False

    for pattern in COMPILED_PATTERNS:
        if pattern.search(value):
            logger.warning(f"Potential injection detected: {pattern.pattern[:50]}...")
            return True

    return False


def validate_file_extension(filename: str, file_type: str = 'bom') -> bool:
    """
    Validate that a file has an allowed extension.

    Args:
        filename: The filename to check
        file_type: The type of file ('bom', 'image', 'document')

    Returns:
        True if extension is allowed, False otherwise
    """
    if not filename:
        return False

    allowed = ALLOWED_EXTENSIONS.get(file_type, set())
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    return ext in allowed


def validate_email(email: str) -> bool:
    """
    Validate an email address format.

    Args:
        email: The email to validate

    Returns:
        True if valid email format, False otherwise
    """
    if not email:
        return False

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """
    Validate a URL format and ensure it's safe.

    Args:
        url: The URL to validate

    Returns:
        True if valid and safe URL, False otherwise
    """
    if not url:
        return False

    # Check length
    if len(url) > MAX_LENGTHS['url']:
        return False

    # Check for javascript: or data: URLs
    if url.lower().startswith(('javascript:', 'data:', 'vbscript:')):
        return False

    # Basic URL pattern
    pattern = r'^https?://[a-zA-Z0-9.-]+(?:/[^\s]*)?$'
    return bool(re.match(pattern, url))


def validate_part_number(part_number: str) -> bool:
    """
    Validate a part number format.

    Args:
        part_number: The part number to validate

    Returns:
        True if valid format, False otherwise
    """
    if not part_number:
        return False

    # Check length
    if len(part_number) > MAX_LENGTHS['part_number']:
        return False

    # Allow alphanumeric with common separators
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9\-_./\s]*$'
    return bool(re.match(pattern, part_number))


# ========== PYDANTIC VALIDATORS ==========

class SecureBaseModel(BaseModel):
    """Base model with built-in security validation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    @classmethod
    def validate_no_injection(cls, v: Any) -> Any:
        """Validate that string fields don't contain injection patterns."""
        if isinstance(v, str) and check_injection(v):
            raise ValueError("Invalid characters detected in input")
        return v


class SecureNameField(BaseModel):
    """Validated name field."""
    name: str

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        if len(v) > MAX_LENGTHS['name']:
            raise ValueError(f"Name must be less than {MAX_LENGTHS['name']} characters")
        if check_injection(v):
            raise ValueError("Invalid characters in name")
        return sanitize_string(v, MAX_LENGTHS['name'])


class SecureDescriptionField(BaseModel):
    """Validated description field."""
    description: Optional[str] = None

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        if len(v) > MAX_LENGTHS['description']:
            raise ValueError(f"Description must be less than {MAX_LENGTHS['description']} characters")
        if check_injection(v):
            raise ValueError("Invalid characters in description")
        return sanitize_string(v, MAX_LENGTHS['description'])


# ========== DECORATOR ==========

def validate_input(func):
    """
    Decorator to validate request input for injection attempts.

    Use on endpoint handlers to automatically check all string inputs.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        for key, value in kwargs.items():
            if isinstance(value, str) and check_injection(value):
                logger.warning(f"Injection attempt blocked in {func.__name__}, field: {key}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid input in field: {key}"
                )
        return await func(*args, **kwargs)
    return wrapper


# ========== CONTENT SECURITY HEADERS ==========

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}
