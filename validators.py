"""
Input validation and sanitization for Gimmie app
"""
import re
from urllib.parse import urlparse
from html import escape
from decimal import Decimal, InvalidOperation

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

def sanitize_string(value, max_length=None):
    """Sanitize string input to prevent XSS"""
    if not value:
        return value
    
    # Remove any null bytes
    value = value.replace('\x00', '')
    
    # Escape HTML entities
    value = escape(value)
    
    # Trim whitespace
    value = value.strip()
    
    # Enforce max length
    if max_length and len(value) > max_length:
        raise ValidationError(f"Value exceeds maximum length of {max_length} characters")
    
    return value

def validate_name(name):
    """Validate item name"""
    if not name or not name.strip():
        raise ValidationError("Name is required")
    
    name = sanitize_string(name, max_length=255)
    
    # Check for minimum length
    if len(name) < 1:
        raise ValidationError("Name must be at least 1 character")
    
    # Check for suspicious patterns (e.g., only special characters)
    if not re.search(r'[a-zA-Z0-9]', name):
        raise ValidationError("Name must contain at least one letter or number")
    
    return name

def validate_cost(cost):
    """Validate cost field"""
    if cost is None or cost == '':
        return None
    
    try:
        # Convert to Decimal for precise money handling
        if isinstance(cost, str):
            # Remove any currency symbols and whitespace
            cost = re.sub(r'[^\d.-]', '', cost)
        
        decimal_cost = Decimal(str(cost))
        
        # Check if positive
        if decimal_cost < 0:
            raise ValidationError("Cost must be a positive number")
        
        # Check for reasonable maximum (1 million)
        if decimal_cost > 1000000:
            raise ValidationError("Cost exceeds maximum allowed value")
        
        # Check for too many decimal places
        if decimal_cost.as_tuple().exponent < -2:
            raise ValidationError("Cost can have at most 2 decimal places")
        
        return float(decimal_cost)
    
    except (InvalidOperation, ValueError):
        raise ValidationError("Cost must be a valid number")

def validate_url(url):
    """Validate URL field"""
    if not url:
        return None
    
    url = url.strip()
    
    # Check length
    if len(url) > 2000:
        raise ValidationError("URL exceeds maximum length of 2000 characters")
    
    # Basic URL validation
    try:
        result = urlparse(url)
        
        # Check for scheme
        if not result.scheme:
            # Try adding https:// if no scheme
            url = 'https://' + url
            result = urlparse(url)
        
        # Validate scheme
        if result.scheme not in ['http', 'https', 'ftp']:
            raise ValidationError("URL must use http, https, or ftp protocol")
        
        # Check for netloc (domain)
        if not result.netloc:
            raise ValidationError("Invalid URL format")
        
        # Basic domain validation
        domain = result.netloc.lower()
        if not re.match(r'^[a-z0-9.-]+$', domain.split(':')[0]):
            raise ValidationError("Invalid domain in URL")
        
        return url
    
    except Exception:
        raise ValidationError("Invalid URL format")

def validate_type(item_type):
    """Validate item type"""
    if item_type not in ['want', 'need']:
        raise ValidationError("Type must be either 'want' or 'need'")
    return item_type

def validate_added_by(added_by):
    """Validate added_by field"""
    if not added_by:
        return 'Unknown'
    
    added_by = sanitize_string(added_by, max_length=100)
    
    if len(added_by) < 1:
        return 'Unknown'
    
    return added_by

def validate_item_data(data):
    """Validate all item data"""
    validated = {}
    
    # Required fields
    validated['name'] = validate_name(data.get('name'))
    
    # Optional fields
    validated['cost'] = validate_cost(data.get('cost'))
    validated['link'] = validate_url(data.get('link'))
    validated['type'] = validate_type(data.get('type', 'want'))
    validated['added_by'] = validate_added_by(data.get('added_by'))
    
    return validated