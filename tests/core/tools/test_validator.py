import pytest
from core.tools.validator import ToolValidator
from core.tools.models import ToolInfo, ToolRequest, ToolInfo, ParameterSchema
from core.tools.exceptions import ToolValidationError


class TestToolValidator:
    def test_required_field_present(self):
        info = ToolInfo(
            name="test",
            parameters=ParameterSchema(
                properties={"name": {"type": "string"}},
                required=["name"],
            ),
        )
        req = ToolRequest(tool_name="test", arguments={"name": "hello"})
        ToolValidator.validate(req, info)  # should not raise

    def test_missing_required_field(self):
        info = ToolInfo(
            name="test",
            parameters=ParameterSchema(
                properties={"name": {"type": "string"}},
                required=["name"],
            ),
        )
        req = ToolRequest(tool_name="test", arguments={})
        with pytest.raises(ToolValidationError, match="Missing required"):
            ToolValidator.validate(req, info)

    def test_type_check_string(self):
        info = ToolInfo(
            name="test",
            parameters=ParameterSchema(
                properties={"count": {"type": "integer"}},
            ),
        )
        req = ToolRequest(tool_name="test", arguments={"count": "not-a-number"})
        with pytest.raises(ToolValidationError, match="expected integer"):
            ToolValidator.validate(req, info)

    def test_type_check_passes(self):
        info = ToolInfo(
            name="test",
            parameters=ParameterSchema(
                properties={"count": {"type": "integer"}},
            ),
        )
        req = ToolRequest(tool_name="test", arguments={"count": 5})
        ToolValidator.validate(req, info)  # should not raise

    def test_no_schema_no_error(self):
        info = ToolInfo(name="test")
        req = ToolRequest(tool_name="test", arguments={"anything": "goes"})
        ToolValidator.validate(req, info)  # should not raise
