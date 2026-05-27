"""Tests for the RefreshTimer class."""

from __future__ import annotations

import time

from wait_for import RefreshTimer


def test_fires_default_callback() -> None:
    """After ``time_for_refresh`` seconds, ``is_it_time()`` returns ``True``.

    Also verifies ``is_it_time()`` returns ``False`` before the timer fires,
    covering both branches of the method.
    """
    timer = RefreshTimer(time_for_refresh=0.05)
    assert not timer.is_it_time(), "timer should not have fired yet"
    time.sleep(0.15)
    assert timer.is_it_time(), "timer should have fired by now"


def test_reset_clears_flag() -> None:
    """``reset()`` sets the flag back to ``False`` and schedules a fresh timer."""
    timer = RefreshTimer(time_for_refresh=0.05)
    time.sleep(0.15)
    assert timer.is_it_time()
    timer.reset()
    assert not timer.is_it_time(), "flag should be cleared after reset"


def test_reset_before_fire_cancels_previous_timer() -> None:
    """``reset()`` before the first fire must not let the old timer set the flag."""
    timer = RefreshTimer(time_for_refresh=0.2)
    time.sleep(0.05)
    timer.reset()
    time.sleep(0.17)
    assert not timer.is_it_time(), "superseded timer must not have fired"
    time.sleep(0.08)
    assert timer.is_it_time(), "new timer should have fired"


def test_custom_callback() -> None:
    """A custom callback is invoked by the timer instead of the default flag setter."""
    results: list[bool] = []
    RefreshTimer(time_for_refresh=0.05, callback=lambda: results.append(True))
    time.sleep(0.15)
    assert len(results) >= 1, "custom callback should have been invoked"


def test_callback_receives_args_and_kwargs() -> None:
    """Positional and keyword arguments are forwarded to the callback."""
    received: list[tuple[tuple[int, ...], dict[str, str]]] = []

    def capture(*args: int, **kwargs: str) -> None:
        received.append((args, kwargs))

    RefreshTimer(0.05, capture, 1, 2, key="value")
    time.sleep(0.15)
    assert len(received) >= 1, "callback should have been invoked"
    args, kwargs = received[0]
    assert args == (1, 2)
    assert kwargs == {"key": "value"}
