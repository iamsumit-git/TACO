"""
tests/test_slicer.py — Unit tests for the context window slicer.

5 tests as specified in the execution plan.
"""
import pytest
from app.services.slicer import slice_messages


def make_messages(count: int, start_role: str = "user") -> list:
    """Helper: generate alternating user/assistant messages."""
    roles = ["user", "assistant"]
    if start_role == "assistant":
        roles = ["assistant", "user"]
    return [
        {"role": roles[i % 2], "content": f"Message {i+1}"}
        for i in range(count)
    ]


def test_under_window_unchanged():
    """Test 1: 5 messages, window=10 → returned unchanged, was_sliced=False."""
    messages = make_messages(5)
    result = slice_messages(messages, window_size=10)

    assert result.was_sliced is False
    assert result.original_count == 5
    assert result.sent_count == 5
    assert len(result.messages) == 5


def test_over_window_trimmed():
    """Test 2: 15 messages, window=10 → trimmed to 10, was_sliced=True."""
    messages = make_messages(15)
    result = slice_messages(messages, window_size=10)

    assert result.was_sliced is True
    assert result.original_count == 15
    # sent_count is ≤ window_size (may be 9 or 10 after pair check)
    assert result.sent_count <= 10
    assert result.sent_count >= 9


def test_system_message_preserved():
    """Test 3: System message + 15 conversation messages → system preserved, ~10 convo kept."""
    system_msg = {"role": "system", "content": "You are a helpful assistant."}
    convo_msgs = make_messages(15)
    messages = [system_msg] + convo_msgs

    result = slice_messages(messages, window_size=10)

    assert result.was_sliced is True
    assert result.messages[0]["role"] == "system", "System message must be first"
    assert result.messages[0]["content"] == "You are a helpful assistant."
    # Should have system + ≤10 convo messages
    assert len(result.messages) <= 11
    assert len(result.messages) >= 10  # system + at least 9 convo


def test_no_mid_pair_cut():
    """Test 4: window=10 with odd starting offset — never starts on an assistant message."""
    # 15 messages: alternating user/assistant starting with user
    # Last 10 would be: positions 5–14 → 5=user, 6=assistant, ... 14=assistant
    # If window=9 (odd), starting at assistant should be dropped
    messages = make_messages(15)
    result = slice_messages(messages, window_size=9)

    # First non-system message in result should always be 'user', not 'assistant'
    if result.messages:
        first_role = result.messages[0]["role"]
        assert first_role in ("user", "system"), (
            f"Conversation must start with user or system, got '{first_role}'"
        )


def test_empty_messages_no_error():
    """Test 5: Empty messages list → returned as-is, no error."""
    result = slice_messages([], window_size=10)

    assert result.was_sliced is False
    assert result.original_count == 0
    assert result.sent_count == 0
    assert result.messages == []
