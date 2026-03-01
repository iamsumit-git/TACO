"""
app/services/slicer.py — Context window slicer (sliding window trim).

Keeps the system message (if present) and the LAST `window_size`
conversation messages (user + assistant pairs).

Rules:
- System message is always preserved at index 0.
- windows are preserved in pairs: if window is odd, round DOWN to avoid
  cutting mid-exchange (e.g. window=10 → keep 10 messages;
  window=9 with even pair needed → keep 8).
- Returns a SlicerResult with the (possibly trimmed) message list
  and metadata about the operation.
"""
from typing import List
from dataclasses import dataclass, field


@dataclass
class SlicerResult:
    messages: List[dict]
    was_sliced: bool
    original_count: int
    sent_count: int


def slice_messages(messages: List[dict], window_size: int) -> SlicerResult:
    """
    Trim conversation messages to the last `window_size` messages.

    Args:
        messages:    Full list of message dicts with 'role' and 'content' keys.
        window_size: Maximum number of conversation messages to keep
                     (system message NOT counted against this limit).

    Returns:
        SlicerResult with trimmed messages and metadata.
    """
    if not messages:
        return SlicerResult(
            messages=[],
            was_sliced=False,
            original_count=0,
            sent_count=0,
        )

    original_count = len(messages)

    # Separate system message from conversation messages
    system_messages = [m for m in messages if m.get("role") == "system"]
    convo_messages = [m for m in messages if m.get("role") != "system"]

    if len(convo_messages) <= window_size:
        # No trimming needed
        return SlicerResult(
            messages=messages,
            was_sliced=False,
            original_count=original_count,
            sent_count=original_count,
        )

    # Trim to last window_size conversation messages
    # Preserve pairs: make sure we start on a user message (even offset)
    trimmed = convo_messages[-window_size:]

    # Ensure we never start mid-pair: if first message is 'assistant', drop it
    if trimmed and trimmed[0].get("role") == "assistant":
        trimmed = trimmed[1:]

    # Re-attach system message at the front
    final_messages = system_messages + trimmed
    sent_count = len(final_messages)

    return SlicerResult(
        messages=final_messages,
        was_sliced=True,
        original_count=original_count,
        sent_count=sent_count,
    )
