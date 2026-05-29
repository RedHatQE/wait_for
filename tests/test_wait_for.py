"""Tests for wait_for() and wait_for_decorator().

Organised by concept:
- Function type variants (method, lambda, builtin, partial)
- timeout / num_sec parameter variants
- fail_condition variants (default, callable, set)
- Optional parameters (silent_failure, log_on_loop, expo, fail_func)
- Error and message reporting
- wait_for_decorator usage
"""

from __future__ import annotations

import time
from datetime import timedelta
from functools import partial
from unittest.mock import MagicMock, patch

import pytest

from wait_for import TimedOutError, wait_for, wait_for_decorator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class Incrementor:
    value: int = 0

    def increment_with_sleep(self) -> int:
        time.sleep(0.1)
        self.value += 1
        return self.value


class CallableObject:
    """Callable instance without a ``__name__`` attribute."""

    def __call__(self) -> bool:
        return True


def _always_false() -> bool:
    return False


def _always_true() -> bool:
    return True


# ---------------------------------------------------------------------------
# Function type variants
# ---------------------------------------------------------------------------


def test_method_as_func() -> None:
    """A regular bound method is accepted as the waited-upon function."""
    incman = Incrementor()
    out, elapsed = wait_for(incman.increment_with_sleep, fail_condition=0, delay=0.05, num_sec=2)
    assert out == 1
    assert elapsed < 1


def test_lambda_as_func() -> None:
    """A lambda expression is accepted as the waited-upon function."""
    incman = Incrementor()
    out, elapsed = wait_for(
        lambda self: self.increment_with_sleep() > 10, [incman], delay=0.05, num_sec=5
    )
    assert out is True
    assert elapsed < 2


def test_builtin_as_func() -> None:
    """A C builtin (bool) is accepted as the waited-upon function."""
    incman = Incrementor()
    out, elapsed = wait_for(bool, [incman], delay=0.5, num_sec=2)
    assert out is True
    assert elapsed < 2


def test_callable_object_as_func() -> None:
    """A callable object (instance with __call__) is accepted as the waited-upon function."""
    result = wait_for(CallableObject(), num_sec=1)
    assert result.out is True


def test_callable_object_in_partial() -> None:
    """A functools.partial wrapping a callable object works without AttributeError."""
    func = partial(CallableObject())
    result = wait_for(func, num_sec=1)
    assert result.out is True


def test_partial_as_func() -> None:
    """A functools.partial wrapping a lambda is accepted as the waited-upon function."""
    incman = Incrementor()
    func = partial(lambda: incman.increment_with_sleep() > 10)
    with pytest.raises(TimedOutError):
        wait_for(func, num_sec=2, delay=1)


# ---------------------------------------------------------------------------
# timeout / num_sec parameter variants
# ---------------------------------------------------------------------------


def test_timeout_as_int() -> None:
    """``timeout`` accepts an int, which is cast to float seconds."""
    result = wait_for(_always_true, timeout=1)
    assert result.out is True


def test_timeout_as_float() -> None:
    """``timeout`` accepts a float number of seconds."""
    result = wait_for(_always_true, timeout=0.5)
    assert result.out is True


def test_timeout_as_string() -> None:
    """``timeout`` accepts a human-readable duration string (e.g. '2s')."""
    incman = Incrementor()
    func = partial(lambda: incman.increment_with_sleep() > 10)
    with pytest.raises(TimedOutError):
        wait_for(func, timeout="2s", delay=1)


def test_timeout_as_timedelta() -> None:
    """``timeout`` accepts a :class:`datetime.timedelta`."""
    with pytest.raises(TimedOutError):
        wait_for(_always_false, timeout=timedelta(seconds=0.1), delay=0.05)


def test_timeout_unknown_type_raises() -> None:
    """``timeout`` with an unsupported type raises ``ValueError``."""
    with pytest.raises(ValueError, match="Timeout got an unknown value"):
        wait_for(_always_false, timeout=object())


@pytest.mark.parametrize("value", ["2", "1.5"])
def test_num_sec_as_string(value: str) -> None:
    """``num_sec`` also accepts a string representation of a number."""
    incman = Incrementor()
    func = partial(lambda: incman.increment_with_sleep() > 10)
    with pytest.raises(TimedOutError):
        wait_for(func, num_sec=value)


# ---------------------------------------------------------------------------
# fail_condition variants
# ---------------------------------------------------------------------------


def test_callable_fail_condition() -> None:
    """``fail_condition`` accepts a callable that receives the polled result."""
    incman = Incrementor()
    with pytest.raises(TimedOutError):
        wait_for(
            incman.increment_with_sleep,
            fail_condition=lambda value: value <= 10,
            num_sec=2,
            delay=1,
        )


def test_set_fail_condition_success() -> None:
    """``fail_condition`` as a set: waiting ends when the result is not in the set."""
    counter = [0]

    def increment() -> int:
        counter[0] += 1
        return counter[0]

    result = wait_for(increment, fail_condition={0, 1, 2}, delay=0, num_sec=5)
    assert result.out == 3


def test_set_fail_condition_timeout() -> None:
    """``fail_condition`` as a set: times out when the result is always in the set."""
    with pytest.raises(TimedOutError):
        wait_for(_always_false, fail_condition={False}, num_sec=0.1, delay=0.05)


# ---------------------------------------------------------------------------
# Optional parameters
# ---------------------------------------------------------------------------


def test_silent_failure() -> None:
    """``silent_failure=True`` returns a ``WaitForResult`` instead of raising on timeout."""
    incman = Incrementor()
    _, elapsed = wait_for(
        lambda self: self.increment_with_sleep() > 100,
        [incman],
        delay=0.05,
        num_sec=1,
        silent_failure=True,
    )
    assert elapsed >= 1
    assert elapsed < 2


def test_log_on_loop() -> None:
    """``log_on_loop=True`` emits an info log on each polling iteration."""
    logger = MagicMock()
    result = wait_for(_always_true, log_on_loop=True, logger=logger, num_sec=1)
    assert result.out is True
    logger.info.assert_called()


def test_expo_delay() -> None:
    """``expo=True`` doubles the inter-poll delay after each failed attempt."""
    with pytest.raises(TimedOutError):
        wait_for(_always_false, expo=True, num_sec=0.15, delay=0.01)


def test_fail_func() -> None:
    """``fail_func`` is called after each unsuccessful polling attempt."""
    fail_func = MagicMock()
    with pytest.raises(TimedOutError):
        wait_for(_always_false, fail_func=fail_func, num_sec=0.15, delay=0.05)
    assert fail_func.call_count >= 1


def test_fail_func_called_when_func_exhausts_timeout() -> None:
    """``fail_func`` is invoked even when ``func()`` itself consumes the timeout budget.

    The ``remaining <= 0`` early-exit branch must call ``fail_func`` before
    breaking, preserving the same callback behavior the original loop had
    (which had no early break and always reached ``fail_func``).
    """
    fail_func = MagicMock()

    def slow_fail() -> bool:
        time.sleep(0.3)
        return False

    with pytest.raises(TimedOutError):
        wait_for(slow_fail, fail_func=fail_func, num_sec=0.1, delay=0)
    assert fail_func.call_count == 1


# ---------------------------------------------------------------------------
# Error and message reporting
# ---------------------------------------------------------------------------


def test_timeout_raises_timed_out_error() -> None:
    """A ``TimedOutError`` is raised when the condition is never met within the timeout."""
    incman = Incrementor()
    with pytest.raises(TimedOutError):
        wait_for(
            lambda self: self.increment_with_sleep() > 10,
            [incman],
            num_sec=1,
            message="never_reached",
        )


@patch("wait_for.default_hidden_logger.error")
def test_lambda_source_code_in_timeout_error(error_logger: MagicMock) -> None:
    """Lambda source code appears in both the ``TimedOutError`` message and the error log."""
    incman = Incrementor()
    with pytest.raises(TimedOutError) as excinfo:
        wait_for(lambda self: self.increment_with_sleep() > 10, [incman], num_sec=1)

    expected = "lambda self: self.increment_with_sleep() > 10"
    assert expected in str(excinfo.value)

    error_log_messages = [call[0][0] % call[0][1] for call in error_logger.call_args_list]
    for message in error_log_messages:
        if expected in message:
            break
    else:
        pytest.fail("The error log does not contain the lambda source code")


def test_builtin_timeout_error_message() -> None:
    """Timeout error for a C builtin uses the plain message form (no filename/line number).

    ``bool([])`` always returns ``False`` (the default ``fail_condition``), so ``wait_for``
    times out.  Because ``bool`` is a C builtin it has no ``__code__`` attribute,
    exercising the else-branch of the filename/line_no guard in the timeout path.
    """
    with pytest.raises(TimedOutError) as exc_info:
        wait_for(bool, [[]], num_sec=0.05, delay=0.01)
    assert "Could not do" in str(exc_info.value)


# ---------------------------------------------------------------------------
# wait_for_decorator
# ---------------------------------------------------------------------------


def test_decorator_with_kwargs() -> None:
    """``@wait_for_decorator(...)`` invoked with keyword arguments."""
    incman = Incrementor()

    @wait_for_decorator(fail_condition=0, delay=0.05, num_sec=2)
    def a_test() -> int:
        return incman.increment_with_sleep()

    assert a_test.out == 1
    assert a_test.duration < 1


def test_decorator_with_empty_parens() -> None:
    """``@wait_for_decorator()`` invoked with empty parentheses uses defaults."""
    incman = Incrementor()

    @wait_for_decorator(num_sec=2)
    def a_test() -> bool:
        return incman.increment_with_sleep() != 0

    assert a_test.out is True
    assert a_test.duration < 1


def test_decorator_bare() -> None:
    """``@wait_for_decorator`` applied without parentheses uses defaults."""

    @wait_for_decorator(num_sec=2)
    def succeeds() -> bool:
        return True

    assert succeeds.out is True


# ---------------------------------------------------------------------------
# func_kwargs parameter
# ---------------------------------------------------------------------------


def test_func_kwargs_forwarded() -> None:
    """``func_kwargs`` are forwarded as keyword arguments to the polled function."""

    def check(*, threshold: int) -> int:
        return threshold

    result = wait_for(check, func_kwargs={"threshold": 42}, num_sec=1)
    assert result.out == 42


def test_func_kwargs_combined_with_func_args() -> None:
    """Both ``func_args`` and ``func_kwargs`` are forwarded together."""

    def add(a: int, b: int, *, offset: int = 0) -> int:
        return a + b + offset

    result = wait_for(add, func_args=[1, 2], func_kwargs={"offset": 10}, num_sec=1)
    assert result.out == 13


# ---------------------------------------------------------------------------
# timeout=None fallback
# ---------------------------------------------------------------------------


def test_timeout_none_falls_through_to_num_sec() -> None:
    """``timeout=None`` is treated as if timeout was not provided; ``num_sec`` is used."""
    with pytest.raises(TimedOutError):
        wait_for(_always_false, timeout=None, num_sec=0.1, delay=0.05)


# ---------------------------------------------------------------------------
# Invalid time string
# ---------------------------------------------------------------------------


def test_invalid_time_string_raises_value_error() -> None:
    """An unparseable ``timeout`` string raises ``ValueError``."""
    with pytest.raises(ValueError, match="Could not parse"):
        wait_for(_always_true, timeout="not a valid time string xyz")


# ---------------------------------------------------------------------------
# WaitForResult tuple interface
# ---------------------------------------------------------------------------


def test_wait_for_result_index_access() -> None:
    """``WaitForResult`` supports index-based access for backward compatibility."""
    result = wait_for(_always_true, num_sec=1)
    assert result[0] is True
    assert isinstance(result[1], float)


def test_wait_for_result_attribute_access() -> None:
    """``WaitForResult`` supports attribute-based access."""
    result = wait_for(_always_true, num_sec=1)
    assert result.out is True
    assert isinstance(result.duration, float)


def test_wait_for_result_unpacking() -> None:
    """``WaitForResult`` supports tuple unpacking."""
    out, duration = wait_for(_always_true, num_sec=1)
    assert out is True
    assert isinstance(duration, float)


# ---------------------------------------------------------------------------
# Sleep overshoot capping
# ---------------------------------------------------------------------------


def test_expo_sleep_does_not_overshoot_timeout() -> None:
    """With ``expo=True``, elapsed time must not significantly exceed ``num_sec``.

    The exponential delay doubles each iteration and can grow well past the
    remaining time budget.  The wait loop should cap each sleep to the time
    left so the total wall-clock duration stays close to ``num_sec``.
    """
    num_sec = 2.0
    tolerance = 0.5
    _, duration = wait_for(
        _always_false,
        expo=True,
        delay=0.1,
        num_sec=num_sec,
        silent_failure=True,
    )
    assert duration <= num_sec + tolerance, (
        f"Expected <= {num_sec + tolerance}s, but waited {duration:.2f}s"
    )


def test_large_fixed_delay_does_not_overshoot_timeout() -> None:
    """A fixed ``delay`` larger than ``num_sec`` must not cause a long overshoot.

    When delay exceeds the remaining budget, the sleep should be capped so
    the total elapsed time stays close to ``num_sec``.
    """
    num_sec = 0.5
    tolerance = 0.5
    _, duration = wait_for(
        _always_false,
        delay=10,
        num_sec=num_sec,
        silent_failure=True,
    )
    assert duration <= num_sec + tolerance, (
        f"Expected <= {num_sec + tolerance}s, but waited {duration:.2f}s"
    )
