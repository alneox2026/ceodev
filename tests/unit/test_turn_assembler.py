from services.agent_gateway.app.services.turn_assembler import TurnAssembler


def test_turn_assembler_collects_text_and_usage() -> None:
    assembler = TurnAssembler()
    assembler.add_event({"usage_metadata": {"total_token_count": 21}})
    assembler.add_text("hello")
    assembler.add_text(" world")

    assert assembler.reply_text() == "hello world"
    assert assembler.usage == {"total_token_count": 21}
    assert assembler.raw_events == [{"usage_metadata": {"total_token_count": 21}}]
