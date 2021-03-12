import inspect
import logging
import time
from collections import namedtuple
from datetime import datetime, timedelta
from functools import partial
from threading import Timer
from types import LambdaType
from typing import Iterable, Union, Type

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


def _get_timeout_secs(kwargs):
    if "timeout" in kwargs and kwargs["timeout"] is not None:
        timeout = kwargs["timeout"]
        if isinstance(timeout, (int, float)):
            num_sec = float(timeout)
        elif isinstance(timeout, str):
            num_sec = _parse_time(timeout)
        elif isinstance(timeout, timedelta):
            num_sec = timeout.total_seconds()
        else:
            raise ValueError("Timeout got an unknown value {}".format(timeout))
    else:
        num_sec = float(kwargs.get('num_sec', 120))
    return num_sec


def is_lambda_function(obj):
    return isinstance(obj, LambdaType) and obj.__name__ == "<lambda>"


def _get_context(func, message=None):
    if not message:
        if isinstance(func, partial):
            params = ", ".join([str(arg) for arg in func.args])
            message = "partial function {}({})".format(func.func.__name__, params)
        elif is_lambda_function(func):
            try:
                message = "lambda defined as `{}`".format(inspect.getsource(func).strip())
            except IOError:
                # Probably in interactive python shell or debugger and cannot get lambda source
                message = "lambda (source code unknown, perhaps defined in interactive shell)"
        else:
            message = "function {}()".format(func.__name__)

    func_obj = func.func if isinstance(func, partial) else func
    if hasattr(func_obj, '__code__'):
        line_no = func_obj.__code__.co_firstlineno
        filename = func_obj.__code__.co_filename
    else:
        line_no = None
        filename = None
    return line_no, filename, message


def check_result_in_fail_condition(fail_condition, result):
    return result in fail_condition


def check_result_is_fail_condition(fail_condition, result):
    return result == fail_condition


def _get_failcondition_check(fail_condition):
    if callable(fail_condition):
        return fail_condition
    elif isinstance(fail_condition, set):
        return partial(check_result_in_fail_condition, fail_condition)
    else:
        return partial(check_result_is_fail_condition, fail_condition)


def _is_exception_type(obj):
    return isinstance(obj, type) and issubclass(obj, Exception)


def _get_handled_exceptions(
        handle: Union[Type[Exception], Iterable[Type[Exception]]]
) -> Iterable[Type[Exception]]:
    if _is_exception_type(handle):
        return iter((handle,))
    else:
        if isinstance(handle, Iterable):
            return iter(item if _is_exception_type(item) else Exception for item in handle)
        else:
            return iter((Exception,))


def _check_must_be_handled(
        exception: Exception, handle: Union[Type[Exception], Iterable[Type[Exception]]]
) -> bool:
    return handle and any(
        exc_type for exc_type
        in _get_handled_exceptions(handle)
        if isinstance(exception, exc_type)
    )


def wait_for(func, func_args=[], func_kwargs={}, logger=None, **kwargs):
    """Waits for a certain amount of time for an action to complete
    Designed to wait for a certain length of time,
    either linearly in 1 second steps, or exponentially, up to a maximum.
    Returns the output from the function once it completes successfully,
    along with the time taken to complete the command.

    It tries to use :py:func:`time.monotonic`, if it is not present, falls back to
    :py:func:`time.time`, but it then is not resistant against system time changes.

    Note: If using the expo keyword, the returned elapsed time will be inaccurate
        as wait_for does not know the exact time that the function returned
        correctly, only that it returned correctly at last check.

    Args:
        func (callable): A function to be run
        func_args (Iterable[Any]): A list of function arguments to be passed to func
        func_kwargs (dict[str, Any]): A dict of function keyword arguments to be passed to func
        num_sec (int): An int describing the number of seconds to wait before timing out.
        timeout (Union[int, timedelta, str]): Describes time to wait before timing out.
            Either an int describing the number of seconds.
            Or a :py:class:`timedelta` object.
            Or a string formatted like ``1h 10m 5s``.
            This then sets the ``num_sec`` variable.
        expo (Any): A flag toggling exponential delay growth.
        message (Optional[str]): A description of func's operation. If None, defaults to the
            function's name.
        fail_condition (Union[callable, Any, set[Any]]): An object describing the failure
            condition that should be tested against the output of func.
            If func() == fail_condition, wait_for continues to wait.
            Can be a callable which takes the result and returns boolean whether to fail.
            You can also specify it as a  set, that way it checks whether it is present in the
            iterable.
        handle_exception(Union[Type[Exception], Iterable[Type[Exception]], Any]):
            A parameter for the handling of exceptions during func() invocation.
            If set to ``Union[Type[Exception], Iterable[Type[Exception]]`` clobber exception
            just from listed exceptions and treat it as a fail_condition.
            If could be casted to True, in cases where func() results in an exception,
            clobber the exception and treat it as a fail_condition.
            If timed out during handling exception TimedOutError would be raised from last handled
            exception.
        raise_original (bool): Controls if last original exception would be raised on timeout
        delay (int): An integer describing the number of seconds to delay before trying func()
            again.
        fail_func (callable): A function to be run after every unsuccessful attempt to run func()
        quiet (Any): Do not write time report to the log (default False)
        very_quiet (Any): Do not log unless there was an error (default False). Implies quiet.
        silent_failure (Any): Even if the entire attempt times out, don't throw a exception.
        log_on_loop (Any): Fire off a log.info message indicating we're still waiting at each
            iteration of the wait loop
    Returns:
        Tuple[Any, float]: Output from func() and total wait time.
    Raises:
        TimedOutError: If num_sec is exceeded after an unsuccessful func() invocation and silent
            failure is not set
    """
    # Hide this call in the detailed traceback
    # https://docs.pytest.org/en/latest/example/simple.html#writing-well-integrated-assertion-helpers
    __tracebackhide__ = True
    logger = logger or default_hidden_logger
    st_time = time.monotonic()
    total_time = 0

    num_sec = _get_timeout_secs(kwargs)
    expo = kwargs.get('expo', False)

    line_no, filename, message = _get_context(func, kwargs.get('message', None))

    fail_condition = kwargs.get('fail_condition', False)
    fail_condition_check = _get_failcondition_check(fail_condition)
    handle_exception = kwargs.get('handle_exception', False)
    delay = kwargs.get('delay', 1)
    fail_func = kwargs.get('fail_func', None)
    very_quiet = kwargs.get("very_quiet", False)
    quiet = kwargs.get("quiet", False) or very_quiet
    silent_fail = kwargs.get("silent_failure", False)
    log_on_loop = kwargs.get("log_on_loop", False)
    raise_original = kwargs.get("raise_original", False)

    t_delta = 0
    tries = 0
    out = None
    exc = None

    if not very_quiet:
        logger.debug("Started %(message)r at %(time).2f", {'message': message, 'time': st_time})
    while t_delta <= num_sec:
        tries += 1
        if log_on_loop:
            logger.info("%(message)r -- try %(tries)d", {'message': message, 'tries': tries})
        try:
            out = func(*func_args, **func_kwargs)
        except Exception as e:
            logger.info(
                "wait_for hit an exception: %(exc_name)s: %(exc)s",
                {'exc_name': type(e).__name__, 'exc': e})
            if _check_must_be_handled(e, handle_exception):
                out = fail_condition
                exc = e
                logger.info("Call failed with following exception, but continuing "
                            "as handle_exception is set to True")
            else:
                logger.info(
                    "%(message)r took %(tries)d tries and %(time).2f seconds "
                    "before failure from an exception.",
                    {'message': message, 'tries': tries, 'time': time.monotonic() - st_time})
                raise
        if out is fail_condition or fail_condition_check(out):
            time.sleep(delay)
            total_time += delay
            if expo:
                delay *= 2
            if fail_func:
                fail_func()
        else:
            duration = time.monotonic() - st_time
            if not quiet:
                logger.debug(
                    "Took %(time).2f to do %(message)r",
                    {'time': duration, 'message': message})
            if not very_quiet:
                logger.debug(
                    "Finished %(message)r at %(duration).2f, %(tries)d tries",
                    {'message': message, 'duration': st_time + t_delta, 'tries': tries})
            return WaitForResult(out, duration)
        t_delta = time.monotonic() - st_time
    if not very_quiet:
        logger.debug(
            "Finished %(message)r at %(duration).2f",
            {'message': message, 'duration': st_time + t_delta})

    if filename and line_no:
        logger_fmt = ("Couldn't complete %(message)r at %(filename)s:%(line_no)d in time,"
            " took %(duration).2f, %(tries)d tries")
        logger_dict = {
            'message': message,
            'filename': filename,
            'line_no': line_no,
            'duration': t_delta,
            'tries': tries
        }
        timeout_msg = "Could not do '{}' at {}:{} in time".format(message, filename, line_no)
    else:
        logger_fmt = ("Couldn't complete %(message)r in time,"
            " took %(duration).2f, %(tries)d tries")
        logger_dict = {
            'message': message,
            'duration': t_delta,
            'tries': tries
        }
        timeout_msg = "Could not do '{}' in time".format(message)

    if not silent_fail:
        logger.error(logger_fmt, logger_dict)
        logger.error('The last result of the call was: %(result)r', {'result': out})

        if raise_original and exc:
            raise exc
        else:
            raise TimedOutError(timeout_msg) from exc
    else:
        logger.warning("{} but ignoring".format(logger_fmt), logger_dict)
        logger.warning('The last result of the call was: %(result)r', {'result': out})
        return WaitForResult(out, num_sec)


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
