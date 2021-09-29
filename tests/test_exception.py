from itertools import cycle
from typing import Union, Type

import pytest

from wait_for import wait_for, TimedOutError


class MyError(Exception):
    """A sample exception for use by the tests in this module."""


class AnotherError(Exception):
    """A sample exception for use by the tests in this module."""


def raise_(*exceptions: Union[Exception, Type[Exception]], default=MyError):
    _exceptions = cycle(exceptions or [default])

    def raisable():
        raise next(_exceptions)
    return raisable


def test_handle_exception_v1():
    """Don't set ``handle_exception``.

    An exception raised by the waited-upon function should bubble up.
    """
    with pytest.raises(MyError):
        wait_for(raise_(MyError))


def test_handle_exception_v2():
    """Set ``handle_exception`` to false.

    An exception raised by the waited-upon function should bubble up.
    """
    with pytest.raises(MyError):
        wait_for(raise_(MyError), handle_exception=False)


def test_handle_exception_v3():
    """Set ``handle_exception`` to true.

    An exception raised by the waited-upon function should not bubble up, and a
    ``TimedOutError`` should be raised instead.
    """
    with pytest.raises(TimedOutError):
        wait_for(raise_(MyError), handle_exception=True, num_sec=0.1)


def test_handle_exception_raises_TimedOutError_from_occured_exception():
    """Set ``handle_exception`` to true.

    An exception raised by the waited-upon function should not bubble up, and a
    ``TimedOutError`` should be raised from function-occurred exception instead.
    """
    try:
        wait_for(raise_(MyError), handle_exception=True, num_sec=0.1)
    except TimedOutError as timeout_exception:
        assert isinstance(timeout_exception.__cause__, MyError)
    else:
        assert False, "Wasn't raised"


def test_handle_specific_exception():
    """Set ``handle_exception`` to ``MyError``.

    An exception raised by the waited-upon function should not bubble up, and a
    ``TimedOutError`` should be raised.
    """
    with pytest.raises(TimedOutError):
        wait_for(raise_(MyError), handle_exception=MyError, num_sec=0.1)


def test_handle_specific_exception_in_iterable():
    """Set ``handle_exception`` to ``(MyError,)``.

    An exception raised by the waited-upon function should not bubble up, and a
    ``TimedOutError`` should be raised.
    """
    with pytest.raises(TimedOutError):
        wait_for(raise_(MyError), handle_exception=(MyError,), num_sec=0.1)


def test_handle_specific_exception_from_general_one():
    """Set ``handle_exception`` to ``(Exception,)``.

    An exception raised by the waited-upon function should not bubble up, and a
    ``TimedOutError`` should be raised.
    """
    with pytest.raises(TimedOutError):
        wait_for(raise_(MyError), handle_exception=(Exception,), num_sec=0.1)


def test_handle_specific_exceptions_in_iterable():
    """Set ``handle_exception`` to ``(MyError, AnotherError,)``.

    An exception raised by the waited-upon function should not bubble up, and a
    ``TimedOutError`` should be raised.
    """
    with pytest.raises(TimedOutError):
        wait_for(raise_(MyError, AnotherError, MyError(), AnotherError()),
                 handle_exception=(MyError, AnotherError,),
                 num_sec=0.1)


@pytest.mark.parametrize('handle_exception', [
    cycle([1, ]),
    'foo_string',
    (MyError('Here'), AnotherError('There'))
])
def test_handle_exception_in_iterable_containing_not_exception_types_are_interpreted_as_True(
        handle_exception
):
    """Set ``handle_exception`` to non-empty iterable containing non-Exception types instances.

    An exception raised by the waited-upon function should not bubble up, and a
    ``TimedOutError`` should be raised because in such case iterable is evaluated to True
    """
    with pytest.raises(TimedOutError):
        wait_for(
            raise_(
                MyError, AnotherError, MyError(), AnotherError(), RuntimeError, RuntimeError('Foo')
            ),
            handle_exception=handle_exception,
            num_sec=1,
            delay=0.1
        )


@pytest.mark.parametrize('handle_exception, _', [  # _ - is workaround for minor pytest bug
    (cycle([]), 1),
    ('', 2),
    (set(), 3),
    ([], 4),
])
def test_handle_exceptions_in_empty_iterable_are_interpreted_as_False(handle_exception, _):
    """Set ``handle_exception`` to empty iterable

    An exception raised by the waited-upon function should bubble up.
    """
    with pytest.raises(MyError):
        wait_for(raise_(MyError), handle_exception=handle_exception, num_sec=1, delay=0.1)


def test_not_handle_unexpected_exception():
    """Set ``handle_exception`` to ``MyError``.

    An exception raised by the waited-upon function should bubble up, and a
    ``AnotherError`` should be raised.
    """
    with pytest.raises(AnotherError):
        wait_for(raise_(AnotherError), handle_exception=MyError, num_sec=0.1)


def test_not_handle_unexpected_exceptions():
    """Set ``handle_exception`` to ``(ValueError, RuntimeError,)``.

    An exception raised by the waited-upon function should bubble up, and a
    ``AnotherError`` should be raised.
    """
    with pytest.raises(AnotherError):
        wait_for(raise_(AnotherError), handle_exception=(ValueError, RuntimeError,), num_sec=0.1)


def test_handle_exception_silent_failure():
    """Set both ``handle_exception`` and ``silent_failure`` to true.

    The time spent calling the waited-upon function should be returned.
    """
    _, num_sec = wait_for(raise_(MyError), handle_exception=True, num_sec=0.1, silent_failure=True,)
    assert isinstance(num_sec, float)


def test_reraise_exception():
    """Original exception is re-raised"""
    with pytest.raises(MyError):
        wait_for(raise_(MyError), handle_exception=True, num_sec=0.1, raise_original=True)
