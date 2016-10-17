# -*- coding: utf-8 -*-
import six
import time
import logging
from collections import namedtuple
from datetime import datetime, timedelta
from functools import partial
from threading import Timer

import parsedatetime

WaitForResult = namedtuple("WaitForResult", ["out", "duration"])

calendar = parsedatetime.Calendar()

default_hidden_logger = logging.getLogger('wait_for.default')
default_hidden_logger.propagate = False
default_hidden_logger.addHandler(logging.NullHandler())


def _parse_time(t):
    global calendar

    parsed, code = calendar.parse(t)
    if code != 2:
        raise ValueError("Could not parse {}!".format(t))
    parsed = datetime.fromtimestamp(time.mktime(parsed))
    return (parsed - datetime.now()).total_seconds()


def wait_for(func, func_args=[], func_kwargs={}, logger=None, **kwargs):
    """Waits for a certain amount of time for an action to complete
    Designed to wait for a certain length of time,
    either linearly in 1 second steps, or exponentially, up to a maximum.
    Returns the output from the function once it completes successfully,
    along with the time taken to complete the command.
    Note: If using the expo keyword, the returned elapsed time will be inaccurate
        as wait_for does not know the exact time that the function returned
        correctly, only that it returned correctly at last check.
    Args:
        func: A function to be run
        func_args: A list of function arguments to be passed to func
        func_kwargs: A dict of function keyword arguments to be passed to func
        num_sec: An int describing the number of seconds to wait before timing out.
        timeout: Either an int describing the number of seconds to wait before timing out. Or a
            :py:class:`timedelta` object. Or a string formatted like ``1h 10m 5s``. This then sets
            the ``num_sec`` variable.
        expo: A boolean flag toggling exponential delay growth.
        message: A string containing a description of func's operation. If None,
            defaults to the function's name.
        fail_condition: An object describing the failure condition that should be tested
            against the output of func. If func() == fail_condition, wait_for continues
            to wait. Can be a callable which takes the result and returns boolean whether to fail.
            You can also specify it as a  set, that way it checks whether it is present in the
            iterable.
        handle_exception: A boolean controlling the handling of excepetions during func()
            invocation. If set to True, in cases where func() results in an exception,
            clobber the exception and treat it as a fail_condition.
        delay: An integer describing the number of seconds to delay before trying func()
            again.
        fail_func: A function to be run after every unsuccessful attempt to run func()
        quiet: Do not write time report to the log (default False)
        very_quiet: Do not log unless there was an error (default False). Implies quiet.
        silent_failure: Even if the entire attempt times out, don't throw a exception.
    Returns:
        A tuple containing the output from func() and a float detailing the total wait time.
    Raises:
        TimedOutError: If num_sec is exceeded after an unsuccessful func() invocation.
    """
    logger = logger or default_hidden_logger
    st_time = time.time()
    total_time = 0
    if "timeout" in kwargs and kwargs["timeout"] is not None:
        timeout = kwargs["timeout"]
        if isinstance(timeout, (int, float)):
            num_sec = float(timeout)
        elif isinstance(timeout, six.string_types):
            num_sec = _parse_time(timeout)
        elif isinstance(timeout, timedelta):
            num_sec = timeout.total_seconds()
        else:
            raise ValueError("Timeout got an unknown value {}".format(timeout))
    else:
        num_sec = kwargs.get('num_sec', 120)

    expo = kwargs.get('expo', False)
    message = kwargs.get('message', None)

    if isinstance(func, partial):
        f_code = six.get_function_code(func.func)
        line_no = f_code.co_firstlineno
        filename = f_code.co_filename
        if not message:
            params = ", ".join([str(arg) for arg in func.args])
            message = "partial function %s(%s)" % (func.func.__name__, params)
    else:
        f_code = six.get_function_code(func)
        line_no = f_code.co_firstlineno
        filename = f_code.co_filename
        if not message:
            message = "function %s()" % func.__name__

    fail_condition = kwargs.get('fail_condition', False)

    def check_result_in_fail_condition(fail_condition, result):
        return result in fail_condition

    def check_result_is_fail_condition(fail_condition, result):
        return result == fail_condition

    if callable(fail_condition):
        fail_condition_check = fail_condition
    elif isinstance(fail_condition, set):
        fail_condition_check = partial(check_result_in_fail_condition, fail_condition)
    else:
        fail_condition_check = partial(check_result_is_fail_condition, fail_condition)
    handle_exception = kwargs.get('handle_exception', False)
    delay = kwargs.get('delay', 1)
    fail_func = kwargs.get('fail_func', None)
    quiet = kwargs.get("quiet", False)
    very_quiet = kwargs.get("very_quiet", False)
    if very_quiet:
        quiet = True
    silent_fail = kwargs.get("silent_failure", False)

    t_delta = 0
    tries = 0
    if not very_quiet:
        logger.debug('Started {} at {}'.format(message, st_time))
    while t_delta <= num_sec:
        try:
            tries += 1
            out = func(*func_args, **func_kwargs)
        except Exception as e:
            logger.info("wait_for hit an exception: {}: {}".format(type(e).__name__, e))
            if handle_exception:
                out = fail_condition
                logger.info("Call failed with following exception, but continuing "
                            "as handle_exception is set to True")
            else:
                logger.info(
                    "Wait for {} took {} tries and {} seconds "
                    "before failure from an exception.".format(
                        message, tries, time.time() - st_time))
                raise
        if out is fail_condition or fail_condition_check(out):
            time.sleep(delay)
            total_time += delay
            if expo:
                delay *= 2
            if fail_func:
                fail_func()
        else:
            duration = time.time() - st_time
            if not quiet:
                logger.debug('Took {:0.2f} to do {}'.format(duration, message))
            if not very_quiet:
                logger.debug(
                    'Finished {} at {}, {} tries'.format(message, st_time + t_delta, tries))
            return WaitForResult(out, duration)
        t_delta = time.time() - st_time
    if not very_quiet:
        logger.debug('Finished at {}'.format(st_time + t_delta))
    if not silent_fail:
        logger.error("Couldn't complete {} at {}:{} in time, took {:0.2f}, {} tries".format(message,
            filename, line_no, t_delta, tries))
        logger.error('The last result of the call was: {}'.format(out))
        raise TimedOutError("Could not do {} at {}:{} in time".format(message, filename, line_no))
    else:
        logger.warning("Could not do {} at {}:{} in time ({} tries) but ignoring".format(message,
            filename, line_no, tries))
        logger.warning('The last result of the call was: {}'.format(out))


def wait_for_decorator(*args, **kwargs):
    """Wrapper for :py:func:`utils.wait.wait_for` that makes it nicer to write testing waits.
    It passes the function decorated to to ``wait_for``
    Example:
    .. code-block:: python
        @wait_for_decorator(num_sec=120)
        def my_waiting_func():
            return do_something()
    You can also pass it without parameters, then it uses ``wait_for``'s defaults:
    .. code-block:: python
        @wait_for_decorator
        def my_waiting_func():
            return do_something()
    Then the result of the waiting is stored in the variable named after the function.
    """
    if not kwargs and len(args) == 1 and callable(args[0]):
        # No params passed, only a callable, so just call it
        return wait_for(args[0])
    else:
        def g(f):
            return wait_for(f, *args, **kwargs)
        return g


class TimedOutError(Exception):
    pass


class RefreshTimer(object):
    """
    Simple Timer class using threads.
    Initialized with a refresh period, a callback and args. Very similar to the
    actual threading.Timer class, when no callback function is passed, reverts to
    even simpler usage of just telling if a certain amount of time has passed.
    Can be resued.
    """

    def __init__(self, time_for_refresh=300, callback=None, *args, **kwargs):
        self.callback = callback or self.it_is_time
        self.time_for_refresh = time_for_refresh
        self.args = args
        self.kwargs = kwargs
        self._is_it_time = False
        self.start()

    def start(self):
        t = Timer(self.time_for_refresh, self.callback, self.args, self.kwargs)
        t.start()

    def it_is_time(self):
        self._is_it_time = True

    def reset(self):
        self._is_it_time = False
        self.start()

    def is_it_time(self):
        if self._is_it_time:
            return True
        else:
            return False


def pytest_namespace():
    # Expose the waiting function in pytest
    return {'wait_for': wait_for_decorator}
