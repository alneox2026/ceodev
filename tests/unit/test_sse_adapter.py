from services.agent_gateway.app.services.sse_adapter import format_sse


def test_format_sse_emits_expected_frame() -> None:
    payload = format_sse("token", {"text": "hello"})
    assert payload.startswith("event: token\n")
    assert 'data: {"text": "hello"}' in payload
    assert payload.endswith("\n\n")

