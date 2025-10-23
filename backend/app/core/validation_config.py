"""
Validation configuration and settings.

This module provides centralized configuration for validation rules,
error messages, and validation behavior across the application.
"""

from dataclasses import dataclass
from typing import Dict, List, Set


@dataclass
class ValidationConfig:
    """Configuration class for validation settings."""

    # Password requirements
    MIN_PASSWORD_LENGTH: int = 8
    MAX_PASSWORD_LENGTH: int = 128
    REQUIRE_UPPERCASE: bool = True
    REQUIRE_LOWERCASE: bool = True
    REQUIRE_DIGIT: bool = True
    REQUIRE_SPECIAL_CHAR: bool = True
    ALLOWED_SPECIAL_CHARS: str = "@$!%*?&"

    # Username requirements
    MIN_USERNAME_LENGTH: int = 3
    MAX_USERNAME_LENGTH: int = 50
    USERNAME_PATTERN: str = r'^[a-zA-Z0-9_-]{3,50}$'

    # File and folder requirements
    MAX_FILENAME_LENGTH: int = 255
    MAX_FOLDER_NAME_LENGTH: int = 255

    # URL validation
    ALLOWED_URL_SCHEMES: List[str] = None
    BLOCK_LOCALHOST_URLS: bool = True

    # Rate limiting
    DEFAULT_RATE_LIMIT: int = 120  # requests per minute
    AUTH_RATE_LIMIT: int = 10      # auth requests per minute
    STRICT_RATE_LIMIT: int = 5     # sensitive operations per minute

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.ALLOWED_URL_SCHEMES is None:
            self.ALLOWED_URL_SCHEMES = ['http', 'https']


# Global validation configuration instance
validation_config = ValidationConfig()


class ValidationMessages:
    """Centralized validation error messages."""

    # Password messages
    PASSWORD_TOO_SHORT = f"Password must be at least {validation_config.MIN_PASSWORD_LENGTH} characters long"
    PASSWORD_TOO_LONG = f"Password cannot exceed {validation_config.MAX_PASSWORD_LENGTH} characters"
    PASSWORD_TOO_COMMON = "Password is too common"
    PASSWORD_MISSING_UPPERCASE = "Password must contain at least one uppercase letter"
    PASSWORD_MISSING_LOWERCASE = "Password must contain at least one lowercase letter"
    PASSWORD_MISSING_DIGIT = "Password must contain at least one digit"
    PASSWORD_MISSING_SPECIAL = f"Password must contain at least one special character ({validation_config.ALLOWED_SPECIAL_CHARS})"
    PASSWORD_REQUIREMENTS = (
        f"Password must contain at least one uppercase letter, "
        f"one lowercase letter, one digit, and one special character ({validation_config.ALLOWED_SPECIAL_CHARS})"
    )
    PASSWORDS_DO_NOT_MATCH = "Passwords do not match"
    PASSWORD_SAME_AS_CURRENT = "New password must be different from current password"

    # Username messages
    USERNAME_EMPTY = "Username cannot be empty"
    USERNAME_INVALID_FORMAT = (
        f"Username must be {validation_config.MIN_USERNAME_LENGTH}-{validation_config.MAX_USERNAME_LENGTH} characters long and contain only "
        "letters, numbers, hyphens, and underscores"
    )
    USERNAME_RESERVED = "Username is reserved"

    # Email messages
    EMAIL_EMPTY = "Email cannot be empty"
    EMAIL_DISPOSABLE = "Disposable email addresses are not allowed"

    # File and folder messages
    FILENAME_EMPTY = "Filename cannot be empty"
    FILENAME_TOO_LONG = f"Filename cannot exceed {validation_config.MAX_FILENAME_LENGTH} characters"
    FILENAME_INVALID_CHARS = "Filename contains invalid characters. Avoid: < > : \" / \\ | ? * and control characters"
    FILENAME_RESERVED = "Filename uses a reserved name"

    FOLDER_NAME_EMPTY = "Folder name cannot be empty or only whitespace"
    FOLDER_NAME_TOO_LONG = f"Folder name cannot exceed {validation_config.MAX_FOLDER_NAME_LENGTH} characters"
    FOLDER_NAME_WHITESPACE = "Folder name cannot have leading or trailing whitespace"

    # URL messages
    URL_INVALID_FORMAT = "Invalid URL format"
    URL_MISSING_PROTOCOL = "URL must include protocol (http:// or https://)"
    URL_INVALID_PROTOCOL = "URL must use HTTP or HTTPS protocol"
    URL_MISSING_DOMAIN = "URL must include domain"
    URL_LOCALHOST_NOT_ALLOWED = "Localhost URLs are not allowed"

    # Phone messages
    PHONE_INVALID_FORMAT = "Invalid phone number format. Use international format: +1234567890"

    # Color messages
    COLOR_INVALID_FORMAT = "Invalid hex color format. Use #RRGGBB or #RGB"

    # General messages
    VALUE_MUST_BE_POSITIVE = "Value must be positive"
    DATE_MUST_BE_FUTURE = "Date must be in the future"
    INVALID_UUID_FORMAT = "Invalid UUID format"
    INVALID_UUID_TYPE = "Invalid UUID type"


class ReservedNames:
    """Collections of reserved names that cannot be used."""

    # Reserved usernames
    USERNAMES: Set[str] = {
        'admin', 'administrator', 'root', 'system', 'api', 'www',
        'mail', 'email', 'support', 'help', 'info', 'contact',
        'test', 'demo', 'guest', 'anonymous', 'null', 'undefined',
        'user', 'users', 'account', 'accounts', 'profile', 'profiles',
        'settings', 'config', 'configuration', 'dashboard', 'home',
        'login', 'logout', 'register', 'signup', 'signin', 'auth',
        'oauth', 'sso', 'security', 'privacy', 'terms', 'legal',
        'about', 'faq', 'blog', 'news', 'docs', 'documentation'
    }

    # Reserved Windows filenames
    WINDOWS_FILENAMES: Set[str] = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }

    # Disposable email domains
    DISPOSABLE_EMAIL_DOMAINS: Set[str] = {
        '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
        'mailinator.com', 'yopmail.com', 'temp-mail.org',
        'throwaway.email', 'maildrop.cc', 'sharklasers.com',
        'grr.la', 'guerrillamailblock.com', 'pokemail.net',
        'spam4.me', 'bccto.me', 'chacuo.net', 'dispostable.com',
        'fakeinbox.com', 'filzmail.com', 'get2mail.fr',
        'getairmail.com', 'getnada.com', 'harakirimail.com',
        'inboxalias.com', 'jetable.org', 'koszmail.pl',
        'kurzepost.de', 'lroid.com', 'mytemp.email',
        'no-spam.ws', 'noclickemail.com', 'nogmailspam.info',
        'nomail.xl.cx', 'notmailinator.com', 'nowmymail.com',
        'rppkn.com', 'safe-mail.net', 'selfdestructingmail.com',
        'sendspamhere.com', 'tempemail.com', 'tempemail.net',
        'tempinbox.com', 'tempmail.it', 'tempmail2.com',
        'tempmailaddress.com', 'tempymail.com', 'thankyou2010.com',
        'trash-mail.at', 'trashmail.at', 'trashmail.com',
        'trashmail.org', 'trbvm.com', 'wegwerfmail.de',
        'wegwerfmail.net', 'wegwerfmail.org', 'wh4f.org',
        'yopmail.fr', 'yopmail.net', 'zetmail.com', 'zoemail.org'
    }


class WeakPasswords:
    """Collection of commonly used weak passwords."""

    COMMON_PASSWORDS: Set[str] = {
        'password', '123456', '12345678', 'qwerty', 'abc123',
        'password123', 'admin', 'letmein', 'welcome', 'monkey',
        '1234567890', 'qwerty123', 'password1', 'admin123',
        'letmein123', 'welcome123', 'password!', 'Password1',
        'Password123', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm',
        '111111', '000000', '123123', '456456', '789789',
        'aaaaaa', 'qqqqqq', 'wwwwww', 'eeeeee', 'rrrrrr',
        'tttttt', 'yyyyyy', 'uuuuuu', 'iiiiii', 'oooooo',
        'pppppp', 'ssssss', 'dddddd', 'ffffff', 'gggggg',
        'hhhhhh', 'jjjjjj', 'kkkkkk', 'llllll', 'zzzzzz',
        'xxxxxx', 'cccccc', 'vvvvvv', 'bbbbbb', 'nnnnnn',
        'mmmmmm', 'login', 'pass', 'test', 'guest', 'user',
        'root', 'toor', 'administrator', 'changeme', 'default'
    }


def get_validation_config() -> ValidationConfig:
    """Get the global validation configuration."""
    return validation_config


def update_validation_config(**kwargs) -> None:
    """Update validation configuration settings."""
    global validation_config
    for key, value in kwargs.items():
        if hasattr(validation_config, key):
            setattr(validation_config, key, value)
        else:
            raise ValueError(f"Unknown validation config key: {key}")


def reset_validation_config() -> None:
    """Reset validation configuration to defaults."""
    global validation_config
    validation_config = ValidationConfig()
