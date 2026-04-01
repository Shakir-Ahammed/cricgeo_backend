"""
Utility functions for common operations
Reusable helper functions used across the application
"""

import re
from typing import Optional


def normalize_email(email: str) -> str:
    """
    Normalize email address to lowercase and strip whitespace
    
    Args:
        email: Email address to normalize
        
    Returns:
        Normalized email address
        
    Example:
        >>> normalize_email("  John.Doe@EXAMPLE.COM  ")
        "john.doe@example.com"
    """
    if not email:
        return ""
    
    return email.strip().lower()


def validate_email_format(email: str) -> bool:
    """
    Validate email format using regex
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email format is valid, False otherwise
        
    Example:
        >>> validate_email_format("user@example.com")
        True
        >>> validate_email_format("invalid-email")
        False
    """
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to maximum length with suffix
    
    Args:
        text: Text to truncate
        max_length: Maximum length (including suffix)
        suffix: Suffix to add if truncated (default "...")
        
    Returns:
        Truncated string
        
    Example:
        >>> truncate_string("This is a long text", 10)
        "This is..."
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def parse_query_param(value: Optional[str], default: any = None) -> any:
    """
    Parse query parameter with default value
    
    Args:
        value: Query parameter value
        default: Default value if parameter is None or empty
        
    Returns:
        Parsed value or default
    """
    if value is None or value == "":
        return default
    return value


def generate_pagination_metadata(
    total: int, 
    page: int, 
    page_size: int
) -> dict:
    """
    Generate pagination metadata for API responses
    
    Args:
        total: Total number of items
        page: Current page number
        page_size: Number of items per page
        
    Returns:
        Dictionary with pagination metadata
        
    Example:
        >>> generate_pagination_metadata(100, 1, 20)
        {'total': 100, 'page': 1, 'page_size': 20, 'total_pages': 5, 'has_next': True, 'has_prev': False}
    """
    total_pages = (total + page_size - 1) // page_size  # Ceiling division
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }


def sanitize_string(text: str, allow_html: bool = False) -> str:
    """
    Sanitize string by removing/escaping dangerous characters
    
    Args:
        text: Text to sanitize
        allow_html: Whether to allow HTML tags (default False)
        
    Returns:
        Sanitized string
    """
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # If HTML not allowed, escape HTML characters
    if not allow_html:
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')
    
    return text
