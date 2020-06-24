# -*- coding: utf-8 -*-
# pylint: disable=W0621
from unittest.mock import patch
import pytest
import time
from functools import partial
from wait_for import wait_for, wait_for_decorator, TimedOutError


class Incrementor():
    value = 0

    def i_sleep_a_lot(self):
        time.sleep(.1)
        self.value += 1
        return self.value


def test_simple_wait():
    incman = Incrementor()
    ec, tc = wait_for(incman.i_sleep_a_lot,
                      fail_condition=0,
                      delay=.05)
    print("Function output {} in time {}".format(ec, tc))
    assert tc < 1, "Should take less than 1 seconds"


def test_lambda_wait():
    incman = Incrementor()
    ec, tc = wait_for(lambda self: self.i_sleep_a_lot() > 10,
                      [incman],
                      delay=.05)
    print("Function output {} in time {}".format(ec, tc))
    assert tc < 2, "Should take less than 2 seconds"


def test_builtin_wait():
    incman = Incrementor()
    ec, tc = wait_for(bool, [incman], delay=0.5)
    print("Function output {} in time {}".format(ec, tc))
    assert tc < 2, "Should take less than 2 seconds"


def test_lambda_wait_silent_fail():
    incman = Incrementor()
    ec, tc = wait_for(lambda self: self.i_sleep_a_lot() > 100,
                      [incman],
                      delay=.05,
                      num_sec=1,
                      silent_failure=True)
    print("Function output {} in time {}".format(ec, tc))
    assert tc == 1, "Should be num_sec"


def test_lambda_long_wait():
    incman = Incrementor()
    with pytest.raises(TimedOutError):
        wait_for(lambda self: self.i_sleep_a_lot() > 10, [incman],
                 num_sec=1, message="lambda_long_wait")


@patch('wait_for.default_hidden_logger.error')
def test_lambda_default_message_from_src(error_logger):
    incman = Incrementor()
    with pytest.raises(TimedOutError) as excinfo:
        wait_for(lambda self: self.i_sleep_a_lot() > 10, [incman],
                 num_sec=1)

    # Check we got the lamda code in the TimedOutError
    expected_message_content = "lambda self: self.i_sleep_a_lot() > 10"
    assert expected_message_content in str(excinfo.value)

    # Check we got the lamda code in the error log
    error_log_messages = [call[0][0] % call[0][1] for call in error_logger.call_args_list]
    for message in error_log_messages:
        if expected_message_content in message:
            break
    else:
        pytest.fail("The error log doesn't contain a message with code of the lambda function")


def test_partial():
    incman = Incrementor()
    func = partial(lambda: incman.i_sleep_a_lot() > 10)
    with pytest.raises(TimedOutError):
        wait_for(func,
                 num_sec=2, delay=1)


def test_callable_fail_condition():
    incman = Incrementor()
    with pytest.raises(TimedOutError):
        wait_for(
            incman.i_sleep_a_lot,
            fail_condition=lambda value: value <= 10, num_sec=2, delay=1)


def test_wait_decorator():
    incman = Incrementor()

    @wait_for_decorator(fail_condition=0, delay=.05)
    def a_test():
        incman.i_sleep_a_lot()
    print("Function output {} in time {}".format(a_test.out, a_test.duration))
    assert a_test.duration < 1, "Should take less than 1 seconds"


def test_wait_decorator_noparams():
    incman = Incrementor()

    @wait_for_decorator()
    def a_test():
        return incman.i_sleep_a_lot() != 0
    print("Function output {} in time {}".format(a_test.out, a_test.duration))
    assert a_test.duration < 1, "Should take less than 1 seconds"


def test_nonnumeric_numsec_timedelta_via_string():
    incman = Incrementor()
    func = partial(lambda: incman.i_sleep_a_lot() > 10)
    with pytest.raises(TimedOutError):
        wait_for(func,
                 timeout="2s", delay=1)


def test_str_numsec():
    incman = Incrementor()
    func = partial(lambda: incman.i_sleep_a_lot() > 10)
    for value in "2", "1.5":
        with pytest.raises(TimedOutError):
            wait_for(func, num_sec=value)
