"""Security Tests。"""
import pytest
from core.security import (
    check_request_size, sanitize_log, sanitize_error_message,
    validate_file_path, mask_api_key,
)

class TestSecurity:
    def test_check_request_size_ok(self):
        assert check_request_size("small data")

    def test_check_request_size_too_large(self):
        assert not check_request_size("x" * (10 * 1024 * 1024 + 1))

    def test_sanitize_log(self):
        data = {"api_key": "sk-secret123", "name": "test", "password": "pw"}
        clean = sanitize_log(data)
        assert clean["api_key"] == "***REDACTED***"
        assert clean["password"] == "***REDACTED***"
        assert clean["name"] == "test"

    def test_sanitize_error_message(self):
        msg = "Error at C:\\Users\\hechao\\secret with sk-abcdef1234567890abcdef1234567890"
        clean = sanitize_error_message(msg)
        assert "C:\\" not in clean and "C:" not in clean
        assert "***API_KEY***" in clean

    def test_validate_file_path(self):
        import tempfile
        base = tempfile.mkdtemp()
        assert validate_file_path(base, base)
        assert not validate_file_path("C:\\Windows\\System32", base)

    def test_mask_api_key(self):
        result = mask_api_key("sk-abcdefghijklmnop")
        assert "..." in result
        assert mask_api_key("") == "***"
