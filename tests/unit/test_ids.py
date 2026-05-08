from common.ids import new_event_id, new_thread_id, new_turn_id, validate_agent_id


def test_generated_ids_have_expected_prefixes() -> None:
    assert new_thread_id().startswith("thread-")
    assert new_turn_id().startswith("turn-")
    assert new_event_id().startswith("evt-")


def test_validate_agent_id_normalizes_value() -> None:
    assert validate_agent_id(" Maxima ") == "maxima"

