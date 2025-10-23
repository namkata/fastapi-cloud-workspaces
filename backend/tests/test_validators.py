"""
Unit tests for centralized validators module.

Tests cover:
- ValidationPatterns regex patterns
- CommonValidators static methods
- PasswordValidators specialized methods
- Convenience validator functions
- Edge cases and error handling
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from app.core.validators import (
    CommonValidators,
    PasswordValidators,
    ValidationPatterns,
    email_validator,
    filename_validator,
    strong_password_validator,
    username_validator,
    workspace_name_validator,
)


class TestValidationPatterns:
    """Test cases for ValidationPatterns regex patterns."""

    def test_username_pattern_valid(self):
        """Test valid username patterns."""
        valid_usernames = [
            "user123",
            "test_user",
            "my-username",
            "a1b",  # minimum length
            "a" * 50,  # maximum length
            "User123",  # mixed case
            "123user",  # starts with number
        ]

        for username in valid_usernames:
            assert ValidationPatterns.USERNAME.match(username), f"Should match: {username}"

    def test_username_pattern_invalid(self):
        """Test invalid username patterns."""
        invalid_usernames = [
            "ab",  # too short
            "a" * 51,  # too long
            "user@domain",  # invalid character
            "user.name",  # invalid character
            "user name",  # space
            "user#123",  # invalid character
            "",  # empty
            "user!",  # invalid character
        ]

        for username in invalid_usernames:
            assert not ValidationPatterns.USERNAME.match(username), f"Should not match: {username}"

    def test_strong_password_pattern_valid(self):
        """Test valid strong password patterns."""
        valid_passwords = [
            "Password123!",
            "MyStr0ng@Pass",
            "C0mplex$Pass",
            "Secure123&",
            "Valid9*Pass",
        ]

        for password in valid_passwords:
            assert ValidationPatterns.STRONG_PASSWORD.match(password), f"Should match: {password}"

    def test_strong_password_pattern_invalid(self):
        """Test invalid strong password patterns."""
        invalid_passwords = [
            "password",  # no uppercase, digit, special
            "PASSWORD",  # no lowercase, digit, special
            "Password",  # no digit, special
            "Password123",  # no special
            "Pass123!",  # too short
            "12345678",  # no letters, special
            "!@#$%^&*",  # no letters, digits
        ]

        for password in invalid_passwords:
            assert not ValidationPatterns.STRONG_PASSWORD.match(password), f"Should not match: {password}"

    def test_filename_pattern_valid(self):
        """Test valid filename patterns."""
        valid_filenames = [
            "document.txt",
            "my_file.pdf",
            "image-2023.jpg",
            "file (1).doc",
            "simple",
            "file.with.dots.txt",
        ]

        for filename in valid_filenames:
            assert ValidationPatterns.FILENAME.match(filename), f"Should match: {filename}"

    def test_filename_pattern_invalid(self):
        """Test invalid filename patterns."""
        invalid_filenames = [
            "file/path.txt",  # forward slash
            "file\\path.txt",  # backslash
            "file:name.txt",  # colon
            "file*name.txt",  # asterisk
            "file?name.txt",  # question mark
            "file<name.txt",  # less than
            "file>name.txt",  # greater than
            "file|name.txt",  # pipe
            'file"name.txt',  # quote
            "file\x00name.txt",  # null character
        ]

        for filename in invalid_filenames:
            assert not ValidationPatterns.FILENAME.match(filename), f"Should not match: {filename}"

    def test_name_pattern_valid(self):
        """Test valid name patterns (no leading/trailing spaces)."""
        valid_names = [
            "Valid Name",
            "Single",
            "Name with spaces",
            "123 Numbers",
            "Special-Characters_Here",
        ]

        for name in valid_names:
            assert ValidationPatterns.NAME.match(name), f"Should match: {name}"

    def test_name_pattern_invalid(self):
        """Test invalid name patterns (leading/trailing spaces)."""
        invalid_names = [
            " Leading space",
            "Trailing space ",
            " Both spaces ",
            "  Multiple leading",
            "Multiple trailing  ",
        ]

        for name in invalid_names:
            assert not ValidationPatterns.NAME.match(name), f"Should not match: {name}"

    def test_hex_color_pattern_valid(self):
        """Test valid hex color patterns."""
        valid_colors = [
            "#FF0000",  # 6-digit
            "#00FF00",
            "#0000FF",
            "#fff",     # 3-digit
            "#000",
            "#ABC",
            "#123456",
            "#abcdef",
        ]

        for color in valid_colors:
            assert ValidationPatterns.HEX_COLOR.match(color), f"Should match: {color}"

    def test_hex_color_pattern_invalid(self):
        """Test invalid hex color patterns."""
        invalid_colors = [
            "FF0000",    # no hash
            "#GG0000",   # invalid character
            "#FF00",     # wrong length
            "#FF00000",  # too long
            "#",         # just hash
            "red",       # color name
            "#ff00gg",   # invalid character
        ]

        for color in invalid_colors:
            assert not ValidationPatterns.HEX_COLOR.match(color), f"Should not match: {color}"

    def test_phone_pattern_valid(self):
        """Test valid phone number patterns."""
        valid_phones = [
            "+1234567890",
            "+12345678901234",  # max length
            "1234567890",       # no plus
            "+91234567",        # min length
        ]

        for phone in valid_phones:
            assert ValidationPatterns.PHONE.match(phone), f"Should match: {phone}"

    def test_phone_pattern_invalid(self):
        """Test invalid phone number patterns."""
        invalid_phones = [
            "+0123456789",      # starts with 0
            "123456",           # too short
            "+123456789012345", # too long
            "+abc1234567",      # letters
            "++1234567890",     # double plus
            "",                 # empty
        ]

        for phone in invalid_phones:
            assert not ValidationPatterns.PHONE.match(phone), f"Should not match: {phone}"


class TestCommonValidators:
    """Test cases for CommonValidators static methods."""

    def test_validate_username_success(self):
        """Test successful username validation."""
        valid_cases = [
            ("TestUser", "testuser"),
            ("user_123", "user_123"),
            ("my-name", "my-name"),
            ("  SpacedUser  ", "spaceduser"),
        ]

        for input_val, expected in valid_cases:
            result = CommonValidators.validate_username(input_val)
            assert result == expected

    def test_validate_username_empty(self):
        """Test username validation with empty input."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            CommonValidators.validate_username("")

        with pytest.raises(ValueError, match="Username cannot be empty"):
            CommonValidators.validate_username(None)

    def test_validate_username_invalid_format(self):
        """Test username validation with invalid format."""
        invalid_usernames = [
            "ab",  # too short
            "a" * 51,  # too long
            "user@domain",  # invalid character
            "user.name",  # invalid character
        ]

        for username in invalid_usernames:
            with pytest.raises(ValueError, match="Username format is invalid"):
                CommonValidators.validate_username(username)

    @patch('app.core.validators.ReservedNames')
    def test_validate_username_reserved(self, mock_reserved):
        """Test username validation with reserved names."""
        mock_reserved.USERNAMES = {"admin", "root", "system"}

        with pytest.raises(ValueError, match="Username is reserved"):
            CommonValidators.validate_username("admin")

    def test_validate_strong_password_success(self):
        """Test successful strong password validation."""
        valid_passwords = [
            "Password123!",
            "MyStr0ng@Pass",
            "C0mplex$Pass",
        ]

        for password in valid_passwords:
            result = CommonValidators.validate_strong_password(password)
            assert result == password

    def test_validate_strong_password_empty(self):
        """Test strong password validation with empty input."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            CommonValidators.validate_strong_password("")

    @patch('app.core.validators.validation_config')
    def test_validate_strong_password_too_short(self, mock_config):
        """Test strong password validation with too short password."""
        mock_config.MIN_PASSWORD_LENGTH = 8

        with pytest.raises(ValueError, match="Password must be at least"):
            CommonValidators.validate_strong_password("Pass1!")

    @patch('app.core.validators.validation_config')
    def test_validate_strong_password_too_long(self, mock_config):
        """Test strong password validation with too long password."""
        mock_config.MAX_PASSWORD_LENGTH = 20

        long_password = "A" * 21 + "1!"
        with pytest.raises(ValueError, match="Password cannot exceed"):
            CommonValidators.validate_strong_password(long_password)

    @patch('app.core.validators.WeakPasswords')
    def test_validate_strong_password_common(self, mock_weak):
        """Test strong password validation with common passwords."""
        mock_weak.COMMON_PASSWORDS = {"password123", "123456789"}

        with pytest.raises(ValueError, match="Password is too common"):
            CommonValidators.validate_strong_password("Password123")

    def test_validate_strong_password_requirements(self):
        """Test strong password validation with missing requirements."""
        test_cases = [
            ("password123!", "uppercase"),  # no uppercase
            ("PASSWORD123!", "lowercase"),  # no lowercase
            ("Password!", "digit"),         # no digit
            ("Password123", "special"),     # no special
        ]

        for password, missing in test_cases:
            with pytest.raises(ValueError, match="Password must contain"):
                CommonValidators.validate_strong_password(password)

    def test_validate_email_success(self):
        """Test successful email validation."""
        valid_emails = [
            ("Test@Example.com", "test@example.com"),
            ("  user@domain.org  ", "user@domain.org"),
            ("name.surname@company.co.uk", "name.surname@company.co.uk"),
        ]

        for input_val, expected in valid_emails:
            result = CommonValidators.validate_email(input_val)
            assert result == expected

    def test_validate_email_empty(self):
        """Test email validation with empty input."""
        with pytest.raises(ValueError, match="Email cannot be empty"):
            CommonValidators.validate_email("")

    @patch('app.core.validators.ReservedNames')
    def test_validate_email_disposable(self, mock_reserved):
        """Test email validation with disposable domains."""
        mock_reserved.DISPOSABLE_EMAIL_DOMAINS = {"tempmail.com", "10minutemail.com"}

        with pytest.raises(ValueError, match="Disposable email addresses are not allowed"):
            CommonValidators.validate_email("user@tempmail.com")

    def test_validate_filename_success(self):
        """Test successful filename validation."""
        valid_filenames = [
            "document.txt",
            "my_file.pdf",
            "image-2023.jpg",
        ]

        for filename in valid_filenames:
            result = CommonValidators.validate_filename(filename)
            assert result == filename

    def test_validate_filename_empty(self):
        """Test filename validation with empty input."""
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            CommonValidators.validate_filename("")

        with pytest.raises(ValueError, match="Filename cannot be empty"):
            CommonValidators.validate_filename("   ")

    def test_validate_filename_too_long(self):
        """Test filename validation with too long name."""
        long_filename = "a" * 256 + ".txt"
        with pytest.raises(ValueError, match="Filename cannot exceed 255 characters"):
            CommonValidators.validate_filename(long_filename)

    def test_validate_filename_invalid_characters(self):
        """Test filename validation with invalid characters."""
        invalid_filenames = [
            "file<name.txt",
            "file>name.txt",
            "file:name.txt",
            "file/name.txt",
            "file\\name.txt",
            "file|name.txt",
            "file?name.txt",
            "file*name.txt",
        ]

        for filename in invalid_filenames:
            with pytest.raises(ValueError, match="Filename contains invalid characters"):
                CommonValidators.validate_filename(filename)

    def test_validate_filename_reserved_names(self):
        """Test filename validation with reserved names."""
        reserved_names = ["CON.txt", "PRN.doc", "AUX.pdf", "NUL", "COM1.exe", "LPT1.dat"]

        for filename in reserved_names:
            with pytest.raises(ValueError, match="uses a reserved name"):
                CommonValidators.validate_filename(filename)

    def test_validate_workspace_name_success(self):
        """Test successful workspace name validation."""
        valid_names = [
            "My Workspace",
            "Project-2023",
            "Single",
            "Name_with_underscores",
        ]

        for name in valid_names:
            result = CommonValidators.validate_workspace_name(name)
            assert result == name

    def test_validate_workspace_name_empty(self):
        """Test workspace name validation with empty input."""
        with pytest.raises(ValueError, match="Name cannot be empty"):
            CommonValidators.validate_workspace_name("")

    def test_validate_workspace_name_whitespace_only(self):
        """Test workspace name validation with whitespace only."""
        with pytest.raises(ValueError, match="Name cannot be empty or only whitespace"):
            CommonValidators.validate_workspace_name("   ")

    def test_validate_workspace_name_too_long(self):
        """Test workspace name validation with too long name."""
        long_name = "a" * 256
        with pytest.raises(ValueError, match="Name cannot exceed 255 characters"):
            CommonValidators.validate_workspace_name(long_name)

    def test_validate_workspace_name_leading_trailing_spaces(self):
        """Test workspace name validation with leading/trailing spaces."""
        with pytest.raises(ValueError, match="Name cannot have leading or trailing whitespace"):
            CommonValidators.validate_workspace_name(" Name")

        with pytest.raises(ValueError, match="Name cannot have leading or trailing whitespace"):
            CommonValidators.validate_workspace_name("Name ")

    def test_validate_url_success(self):
        """Test successful URL validation."""
        valid_urls = [
            "https://example.com",
            "http://subdomain.example.org/path",
            "https://api.service.com/v1/endpoint",
        ]

        for url in valid_urls:
            result = CommonValidators.validate_url(url)
            assert result == url

    def test_validate_url_empty(self):
        """Test URL validation with empty input."""
        result = CommonValidators.validate_url("")
        assert result == ""

        result = CommonValidators.validate_url(None)
        assert result is None

    def test_validate_url_invalid_format(self):
        """Test URL validation with invalid format."""
        with pytest.raises(ValueError, match="Invalid URL format"):
            CommonValidators.validate_url("not-a-url")

    def test_validate_url_no_protocol(self):
        """Test URL validation without protocol."""
        with pytest.raises(ValueError, match="URL must include protocol"):
            CommonValidators.validate_url("example.com")

    def test_validate_url_invalid_protocol(self):
        """Test URL validation with invalid protocol."""
        with pytest.raises(ValueError, match="URL must use HTTP or HTTPS protocol"):
            CommonValidators.validate_url("ftp://example.com")

    def test_validate_url_no_domain(self):
        """Test URL validation without domain."""
        with pytest.raises(ValueError, match="URL must include domain"):
            CommonValidators.validate_url("https://")

    def test_validate_url_localhost(self):
        """Test URL validation with localhost."""
        localhost_urls = [
            "http://localhost:8000",
            "https://127.0.0.1:3000",
            "http://0.0.0.0:5000",
        ]

        for url in localhost_urls:
            with pytest.raises(ValueError, match="Localhost URLs are not allowed"):
                CommonValidators.validate_url(url)

    def test_validate_hex_color_success(self):
        """Test successful hex color validation."""
        valid_colors = [
            ("#FF0000", "#FF0000"),
            ("#fff", "#FFF"),
            ("  #abc123  ", "#ABC123"),
        ]

        for input_val, expected in valid_colors:
            result = CommonValidators.validate_hex_color(input_val)
            assert result == expected

    def test_validate_hex_color_empty(self):
        """Test hex color validation with empty input."""
        result = CommonValidators.validate_hex_color("")
        assert result == ""

    def test_validate_hex_color_invalid(self):
        """Test hex color validation with invalid format."""
        invalid_colors = [
            "FF0000",    # no hash
            "#GG0000",   # invalid character
            "#FF00",     # wrong length
        ]

        for color in invalid_colors:
            with pytest.raises(ValueError, match="Invalid hex color format"):
                CommonValidators.validate_hex_color(color)

    def test_validate_phone_number_success(self):
        """Test successful phone number validation."""
        valid_phones = [
            ("+1 (555) 123-4567", "+15551234567"),
            ("555-123-4567", "5551234567"),
            ("+44 20 7946 0958", "+442079460958"),
        ]

        for input_val, expected in valid_phones:
            result = CommonValidators.validate_phone_number(input_val)
            assert result == expected

    def test_validate_phone_number_empty(self):
        """Test phone number validation with empty input."""
        result = CommonValidators.validate_phone_number("")
        assert result == ""

    def test_validate_phone_number_invalid(self):
        """Test phone number validation with invalid format."""
        invalid_phones = [
            "123456",           # too short
            "+0123456789",      # starts with 0
            "abc1234567",       # letters
        ]

        for phone in invalid_phones:
            with pytest.raises(ValueError, match="Invalid phone number format"):
                CommonValidators.validate_phone_number(phone)

    def test_validate_positive_integer_success(self):
        """Test successful positive integer validation."""
        valid_integers = [1, 42, 1000, 999999]

        for value in valid_integers:
            result = CommonValidators.validate_positive_integer(value)
            assert result == value

    def test_validate_positive_integer_none(self):
        """Test positive integer validation with None."""
        result = CommonValidators.validate_positive_integer(None)
        assert result is None

    def test_validate_positive_integer_not_integer(self):
        """Test positive integer validation with non-integer."""
        with pytest.raises(ValueError, match="Value must be an integer"):
            CommonValidators.validate_positive_integer("123")

    def test_validate_positive_integer_not_positive(self):
        """Test positive integer validation with non-positive value."""
        with pytest.raises(ValueError, match="Value must be positive"):
            CommonValidators.validate_positive_integer(0)

        with pytest.raises(ValueError, match="Value must be positive"):
            CommonValidators.validate_positive_integer(-5)

    def test_validate_future_datetime_success(self):
        """Test successful future datetime validation."""
        future_date = datetime.utcnow() + timedelta(days=1)
        result = CommonValidators.validate_future_datetime(future_date)
        assert result == future_date

    def test_validate_future_datetime_none(self):
        """Test future datetime validation with None."""
        result = CommonValidators.validate_future_datetime(None)
        assert result is None

    def test_validate_future_datetime_past(self):
        """Test future datetime validation with past date."""
        past_date = datetime.utcnow() - timedelta(days=1)
        with pytest.raises(ValueError, match="Date must be in the future"):
            CommonValidators.validate_future_datetime(past_date)

    def test_validate_uuid_list_success(self):
        """Test successful UUID list validation."""
        uuid1 = uuid4()
        uuid2 = uuid4()

        # Test with UUID objects
        result = CommonValidators.validate_uuid_list([uuid1, uuid2])
        assert result == [uuid1, uuid2]

        # Test with string UUIDs
        result = CommonValidators.validate_uuid_list([str(uuid1), str(uuid2)])
        assert result == [uuid1, uuid2]

        # Test mixed
        result = CommonValidators.validate_uuid_list([uuid1, str(uuid2)])
        assert result == [uuid1, uuid2]

    def test_validate_uuid_list_empty(self):
        """Test UUID list validation with empty list."""
        result = CommonValidators.validate_uuid_list([])
        assert result == []

        result = CommonValidators.validate_uuid_list(None)
        assert result == []

    def test_validate_uuid_list_invalid_string(self):
        """Test UUID list validation with invalid string UUID."""
        with pytest.raises(ValueError, match="Invalid UUID format"):
            CommonValidators.validate_uuid_list(["not-a-uuid"])

    def test_validate_uuid_list_invalid_type(self):
        """Test UUID list validation with invalid type."""
        with pytest.raises(ValueError, match="Invalid UUID type"):
            CommonValidators.validate_uuid_list([123])


class TestPasswordValidators:
    """Test cases for PasswordValidators specialized methods."""

    def test_validate_password_match_success(self):
        """Test successful password match validation."""
        values = {"password": "secret123"}
        result = PasswordValidators.validate_password_match("secret123", values)
        assert result == "secret123"

    def test_validate_password_match_failure(self):
        """Test password match validation failure."""
        values = {"password": "secret123"}
        with pytest.raises(ValueError, match="Passwords do not match"):
            PasswordValidators.validate_password_match("different", values)

    def test_validate_password_match_no_password_field(self):
        """Test password match validation when password field is missing."""
        values = {}
        result = PasswordValidators.validate_password_match("secret123", values)
        assert result == "secret123"

    def test_validate_password_match_custom_field(self):
        """Test password match validation with custom password field."""
        values = {"new_password": "secret123"}
        result = PasswordValidators.validate_password_match(
            "secret123", values, password_field="new_password"
        )
        assert result == "secret123"

    def test_validate_current_password_different_success(self):
        """Test successful current password different validation."""
        values = {"current_password": "old_secret"}
        result = PasswordValidators.validate_current_password_different("new_secret", values)
        assert result == "new_secret"

    def test_validate_current_password_different_failure(self):
        """Test current password different validation failure."""
        values = {"current_password": "same_secret"}
        with pytest.raises(ValueError, match="New password must be different from current password"):
            PasswordValidators.validate_current_password_different("same_secret", values)

    def test_validate_current_password_different_no_current(self):
        """Test current password different validation when current password is missing."""
        values = {}
        result = PasswordValidators.validate_current_password_different("new_secret", values)
        assert result == "new_secret"


class TestConvenienceValidators:
    """Test cases for convenience validator functions."""

    @patch('app.core.validators.validator')
    def test_username_validator(self, mock_validator):
        """Test username validator function."""
        mock_validator.return_value = MagicMock()

        result = username_validator("username")

        mock_validator.assert_called_once_with("username", allow_reuse=True)
        mock_validator.return_value.assert_called_once_with(CommonValidators.validate_username)

    @patch('app.core.validators.validator')
    def test_strong_password_validator(self, mock_validator):
        """Test strong password validator function."""
        mock_validator.return_value = MagicMock()

        result = strong_password_validator("password")

        mock_validator.assert_called_once_with("password", allow_reuse=True)
        mock_validator.return_value.assert_called_once_with(CommonValidators.validate_strong_password)

    @patch('app.core.validators.validator')
    def test_email_validator(self, mock_validator):
        """Test email validator function."""
        mock_validator.return_value = MagicMock()

        result = email_validator("email")

        mock_validator.assert_called_once_with("email", allow_reuse=True)
        mock_validator.return_value.assert_called_once_with(CommonValidators.validate_email)

    @patch('app.core.validators.validator')
    def test_filename_validator(self, mock_validator):
        """Test filename validator function."""
        mock_validator.return_value = MagicMock()

        result = filename_validator("filename")

        mock_validator.assert_called_once_with("filename", allow_reuse=True)
        mock_validator.return_value.assert_called_once_with(CommonValidators.validate_filename)

    @patch('app.core.validators.validator')
    def test_workspace_name_validator(self, mock_validator):
        """Test workspace name validator function."""
        mock_validator.return_value = MagicMock()

        result = workspace_name_validator("name")

        mock_validator.assert_called_once_with("name", allow_reuse=True)
        mock_validator.return_value.assert_called_once_with(CommonValidators.validate_workspace_name)

    @patch('app.core.validators.validator')
    def test_convenience_validators_default_field_names(self, mock_validator):
        """Test convenience validators with default field names."""
        mock_validator.return_value = MagicMock()

        # Test default field names
        username_validator()
        strong_password_validator()
        email_validator()
        filename_validator()
        workspace_name_validator()

        # Verify calls with default field names
        expected_calls = [
            (("username", ), {"allow_reuse": True}),
            (("password", ), {"allow_reuse": True}),
            (("email", ), {"allow_reuse": True}),
            (("filename", ), {"allow_reuse": True}),
            (("name", ), {"allow_reuse": True}),
        ]

        assert mock_validator.call_count == 5
        for i, (args, kwargs) in enumerate(expected_calls):
            assert mock_validator.call_args_list[i] == ((args[0],), kwargs)


class TestValidatorsIntegration:
    """Integration tests for validators."""

    def test_username_validation_flow(self):
        """Test complete username validation flow."""
        # Valid case
        result = CommonValidators.validate_username("TestUser123")
        assert result == "testuser123"

        # Invalid cases
        with pytest.raises(ValueError):
            CommonValidators.validate_username("")

        with pytest.raises(ValueError):
            CommonValidators.validate_username("ab")

        with pytest.raises(ValueError):
            CommonValidators.validate_username("user@domain")

    def test_password_validation_flow(self):
        """Test complete password validation flow."""
        # Valid case
        result = CommonValidators.validate_strong_password("SecurePass123!")
        assert result == "SecurePass123!"

        # Invalid cases
        with pytest.raises(ValueError):
            CommonValidators.validate_strong_password("weak")

        with pytest.raises(ValueError):
            CommonValidators.validate_strong_password("NoSpecialChar123")

    def test_email_validation_flow(self):
        """Test complete email validation flow."""
        # Valid case
        result = CommonValidators.validate_email("User@Example.COM")
        assert result == "user@example.com"

        # Invalid cases
        with pytest.raises(ValueError):
            CommonValidators.validate_email("")

    def test_filename_validation_flow(self):
        """Test complete filename validation flow."""
        # Valid case
        result = CommonValidators.validate_filename("document.txt")
        assert result == "document.txt"

        # Invalid cases
        with pytest.raises(ValueError):
            CommonValidators.validate_filename("")

        with pytest.raises(ValueError):
            CommonValidators.validate_filename("file/path.txt")

        with pytest.raises(ValueError):
            CommonValidators.validate_filename("CON.txt")

    def test_workspace_name_validation_flow(self):
        """Test complete workspace name validation flow."""
        # Valid case
        result = CommonValidators.validate_workspace_name("My Project")
        assert result == "My Project"

        # Invalid cases
        with pytest.raises(ValueError):
            CommonValidators.validate_workspace_name("")

        with pytest.raises(ValueError):
            CommonValidators.validate_workspace_name(" Leading space")

        with pytest.raises(ValueError):
            CommonValidators.validate_workspace_name("Trailing space ")

    def test_multiple_validators_together(self):
        """Test using multiple validators together."""
        # Simulate a user registration scenario
        username = CommonValidators.validate_username("NewUser123")
        password = CommonValidators.validate_strong_password("SecurePass123!")
        email = CommonValidators.validate_email("NewUser@Example.com")

        assert username == "newuser123"
        assert password == "SecurePass123!"
        assert email == "newuser@example.com"

        # Test password confirmation
        values = {"password": password}
        confirmed = PasswordValidators.validate_password_match(password, values)
        assert confirmed == password
