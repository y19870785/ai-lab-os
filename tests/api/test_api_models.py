"""API + CLI Tests。"""

class TestAPIModels:
    def test_chat_request(self):
        from api.models import ChatRequest
        req = ChatRequest(user_input="Hello")
        assert req.application_name == "ceo-assistant"

    def test_chat_response(self):
        from api.models import ChatResponse
        resp = ChatResponse(answer="Hi", mode="mock")
        assert resp.mode == "mock"

class TestCLIImports:
    def test_cli_main_module(self):
        import cli.main
        assert cli.main.COMMANDS is not None

    def test_health_command_exists(self):
        import cli.commands.health_cmd
        assert hasattr(cli.commands.health_cmd, "run")
