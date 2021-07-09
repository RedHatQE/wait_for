# -*- coding: utf-8 -*-
import pytest

from wait_for import wait_for, TimedOutError


class MyError(Exception):
    """A sample exception for use by the tests in this module."""


def raise_my_error():
    """Raise ``MyError``."""
    raise MyError()


def test_handle_exception_v1():
    """Don't set ``handle_exception``.

    An exception raised by the waited-upon function should bubble up.
    """
    with pytest.raises(MyError):
        wait_for(raise_my_error)


def test_handle_exception_v2():
    """Set ``handle_exception`` to false.

    An exception raised by the waited-upon function should bubble up.
    """
    with pytest.raises(MyError):
        wait_for(raise_my_error, handle_exception=False)


def test_handle_exception_v3():
    """Set ``handle_exception`` to true.

    An exception raised by the waited-upon function should not bubble up, and a
    ``TimedOutError`` should be raised instead.
    """
    with pytest.raises(TimedOutError):
        wait_for(raise_my_error, handle_exception=True, num_sec=0.1)


def test_handle_exception_silent_failure_v1():
    """Set both ``handle_exception`` and ``silent_failure`` to true.

    The time spent calling the waited-upon function should be returned.
    """
    _, num_sec = _call_handle_exception_silent_failure()
    assert isinstance(num_sec, float)


def test_reraise_exception():
    with pytest.raises(MyError):
        wait_for(raise_my_error, handle_exception=True, num_sec=0.1, raise_original=True)


def _call_handle_exception_silent_failure():
    return wait_for(
        raise_my_error,
        handle_exception=True,
        num_sec=0.1,
        silent_failure=True,
    )
