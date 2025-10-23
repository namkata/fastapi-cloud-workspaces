"""
Enhanced Pydantic validators for the FastAPI application.

This module provides custom validators and validation utilities that can be
reused across different schemas to ensure consistent validation behavior.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
from uuid import UUID

from app.core.validation_config import (
    ReservedNames,
    ValidationMessages,
    WeakPasswords,
    validation_config,
)
from pydantic import validator


class ValidationPatterns:
    """Common regex patterns for validation."""

    # Username: 3-50 chars, alphanumeric, hyphens, underscores
    USERNAME = re.compile(r'^[a-zA-Z0-9_-]{3,50}$')

    # Strong password: min 8 chars, at least 1 upper, 1 lower, 1 digit, 1 special
    STRONG_PASSWORD = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')

    # File name: no path separators or special chars
    FILENAME = re.compile(r'^[^<>:"/\\|?*\x00-\x1f]+$')

    # Workspace/folder name: 1-255 chars, no leading/trailing spaces
    NAME = re.compile(r'^[^\s].*[^\s]$|^[^\s]$')

    # Hex color code
    HEX_COLOR = re.compile(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$')

    # Phone number (international format)
    PHONE = re.compile(r'^\+?[1-9]\d{1,14}$')


class CommonValidators:
    """Collection of reusable validators."""

    @staticmethod
    def validate_username(v: str) -> str:
        """
        Validate username format.

        Rules:
        - 3-50 characters
        - Only letters, numbers, hyphens, underscores
        - Case insensitive (converted to lowercase)
        """
        if not v:
            raise ValueError(ValidationMessages.USERNAME_EMPTY)

        v = v.strip().lower()

        if not ValidationPatterns.USERNAME.match(v):
            raise ValueError(ValidationMessages.USERNAME_INVALID_FORMAT)

        # Reserved usernames
        if v in ReservedNames.USERNAMES:
            raise ValueError(ValidationMessages.USERNAME_RESERVED)

        return v

    @staticmethod
    def validate_strong_password(v: str) -> str:
        """
        Validate password strength.

        Rules:
        - Minimum 8 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 digit
        - At least 1 special character (@$!%*?&)
        """
        if not v:
            raise ValueError('Password cannot be empty')

        if len(v) < validation_config.MIN_PASSWORD_LENGTH:
            raise ValueError(ValidationMessages.PASSWORD_TOO_SHORT)

        if len(v) > validation_config.MAX_PASSWORD_LENGTH:
            raise ValueError(ValidationMessages.PASSWORD_TOO_LONG)

        # Check for common weak passwords
        if v.lower() in WeakPasswords.COMMON_PASSWORDS:
            raise ValueError(ValidationMessages.PASSWORD_TOO_COMMON)

        # Check character requirements
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in validation_config.ALLOWED_SPECIAL_CHARS for c in v)

        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(ValidationMessages.PASSWORD_REQUIREMENTS)

        return v

    @staticmethod
    def validate_email(v: str) -> str:
        """
        Validate and normalize email address.

        Rules:
        - Valid email format (handled by EmailStr)
        - Normalized to lowercase
        - Domain validation
        """
        if not v:
            raise ValueError(ValidationMessages.EMAIL_EMPTY)

        v = v.strip().lower()

        # Additional domain validation
        domain = v.split('@')[1] if '@' in v else ''

        # Block common disposable email domains
        if domain in ReservedNames.DISPOSABLE_EMAIL_DOMAINS:
            raise ValueError(ValidationMessages.EMAIL_DISPOSABLE)

        return v

    @staticmethod
    def validate_filename(v: str) -> str:
        """
        Validate file name.

        Rules:
        - Not empty
        - No path separators or special characters
        - Maximum 255 characters
        """
        if not v or not v.strip():
            raise ValueError('Filename cannot be empty')

        v = v.strip()

        if len(v) > 255:
            raise ValueError('Filename cannot exceed 255 characters')

        if not ValidationPatterns.FILENAME.match(v):
            raise ValueError(
                'Filename contains invalid characters. '
                'Avoid: < > : " / \\ | ? * and control characters'
            )

        # Check for reserved names (Windows)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }

        name_without_ext = v.split('.')[0].upper()
        if name_without_ext in reserved_names:
            raise ValueError(f'Filename "{v}" uses a reserved name')

        return v

    @staticmethod
    def validate_workspace_name(v: str) -> str:
        """
        Validate workspace/folder name.

        Rules:
        - 1-255 characters
        - No leading/trailing whitespace
        - Not empty after trimming
        """
        if not v:
            raise ValueError('Name cannot be empty')

        original = v
        v = v.strip()

        if not v:
            raise ValueError('Name cannot be empty or only whitespace')

        if len(v) > 255:
            raise ValueError('Name cannot exceed 255 characters')

        if v != original:
            raise ValueError('Name cannot have leading or trailing whitespace')

        return v

    @staticmethod
    def validate_url(v: str) -> str:
        """
        Validate URL format.

        Rules:
        - Valid URL format
        - HTTPS preferred for external URLs
        - No localhost in production
        """
        if not v:
            return v

        v = v.strip()

        try:
            parsed = urlparse(v)
        except Exception:
            raise ValueError('Invalid URL format')

        if not parsed.scheme:
            raise ValueError('URL must include protocol (http:// or https://)')

        if parsed.scheme not in ['http', 'https']:
            raise ValueError('URL must use HTTP or HTTPS protocol')

        if not parsed.netloc:
            raise ValueError('URL must include domain')

        # Security checks
        if parsed.netloc.lower() in ['localhost', '127.0.0.1', '0.0.0.0']:
            raise ValueError('Localhost URLs are not allowed')

        return v

    @staticmethod
    def validate_hex_color(v: str) -> str:
        """
        Validate hex color code.

        Rules:
        - Format: #RRGGBB or #RGB
        - Case insensitive
        """
        if not v:
            return v

        v = v.strip().upper()

        if not ValidationPatterns.HEX_COLOR.match(v):
            raise ValueError('Invalid hex color format. Use #RRGGBB or #RGB')

        return v

    @staticmethod
    def validate_phone_number(v: str) -> str:
        """
        Validate phone number.

        Rules:
        - International format preferred
        - 7-15 digits
        - Optional + prefix
        """
        if not v:
            return v

        # Remove spaces, hyphens, parentheses
        v = re.sub(r'[\s\-\(\)]', '', v.strip())

        if not ValidationPatterns.PHONE.match(v):
            raise ValueError(
                'Invalid phone number format. '
                'Use international format: +1234567890'
            )

        return v

    @staticmethod
    def validate_positive_integer(v: int, field_name: str = 'Value') -> int:
        """Validate positive integer."""
        if v is None:
            return v

        if not isinstance(v, int):
            raise ValueError(f'{field_name} must be an integer')

        if v <= 0:
            raise ValueError(f'{field_name} must be positive')

        return v

    @staticmethod
    def validate_future_datetime(v: datetime, field_name: str = 'Date') -> datetime:
        """Validate that datetime is in the future."""
        if v is None:
            return v

        if v <= datetime.utcnow():
            raise ValueError(f'{field_name} must be in the future')

        return v

    @staticmethod
    def validate_uuid_list(v: List[Union[str, UUID]]) -> List[UUID]:
        """Validate list of UUIDs."""
        if not v:
            return []

        result = []
        for item in v:
            if isinstance(item, str):
                try:
                    result.append(UUID(item))
                except ValueError:
                    raise ValueError(f'Invalid UUID format: {item}')
            elif isinstance(item, UUID):
                result.append(item)
            else:
                raise ValueError(f'Invalid UUID type: {type(item)}')

        return result


class PasswordValidators:
    """Specialized password validation utilities."""

    @staticmethod
    def validate_password_match(confirm_password: str, values: Dict[str, Any], password_field: str = 'password') -> str:
        """Validate that password confirmation matches."""
        if password_field in values and confirm_password != values[password_field]:
            raise ValueError('Passwords do not match')
        return confirm_password

    @staticmethod
    def validate_current_password_different(new_password: str, values: Dict[str, Any]) -> str:
        """Validate that new password is different from current."""
        if 'current_password' in values and new_password == values['current_password']:
            raise ValueError('New password must be different from current password')
        return new_password


# Convenience functions for common validation patterns
def username_validator(field_name: str = 'username'):
    """Create a username validator for a specific field."""
    return validator(field_name, allow_reuse=True)(CommonValidators.validate_username)

def strong_password_validator(field_name: str = 'password'):
    """Create a strong password validator for a specific field."""
    return validator(field_name, allow_reuse=True)(CommonValidators.validate_strong_password)

def email_validator(field_name: str = 'email'):
    """Create an email validator for a specific field."""
    return validator(field_name, allow_reuse=True)(CommonValidators.validate_email)

def filename_validator(field_name: str = 'filename'):
    """Create a filename validator for a specific field."""
    return validator(field_name, allow_reuse=True)(CommonValidators.validate_filename)

def workspace_name_validator(field_name: str = 'name'):
    """Create a workspace name validator for a specific field."""
    return validator(field_name, allow_reuse=True)(CommonValidators.validate_workspace_name)
