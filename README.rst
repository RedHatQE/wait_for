wait_for
========

A waiting-based utility with decorator and logger support for Python.

Designed to wait for a certain length of time for an action to complete,
either linearly in 1-second steps, or exponentially, up to a maximum.
Returns the output from the function once it completes successfully,
along with the time taken to complete the command.

Installation
------------

.. code-block:: bash

   pip install wait_for

Quick Start
-----------

.. code-block:: python

   import time
   from wait_for import wait_for

   class Incrementor:
       value = 0

       def i_sleep_a_lot(self):
           time.sleep(.1)
           self.value += 1
           return self.value

   incman = Incrementor()
   result, elapsed = wait_for(incman.i_sleep_a_lot,
                              fail_condition=0,
                              delay=0.05)
   print(f"Function returned {result} in {elapsed:.2f}s")


API Reference
-------------

``wait_for``
~~~~~~~~~~~~

.. code-block:: python

   wait_for(func, func_args=[], func_kwargs={}, logger=None, **kwargs)

Waits for ``func`` to return a value that does not match the ``fail_condition``,
retrying on a configurable interval. Uses ``time.monotonic`` for accurate elapsed
time measurement.

**Positional / keyword arguments:**

``func`` *(callable)* -- **Required.** The function to call on each attempt.

``func_args`` *(list)* -- Positional arguments forwarded to ``func``. Default: ``[]``.

``func_kwargs`` *(dict)* -- Keyword arguments forwarded to ``func``. Default: ``{}``.

``logger`` *(logging.Logger)* -- Logger instance for wait_for's own messages. Default:
a hidden logger (``wait_for.default``) that discards output.

**Keyword-only arguments (passed via** ``**kwargs`` **):**

``num_sec`` *(int | float)* -- Maximum number of seconds to wait before timing out.
Default: ``120``. Ignored when ``timeout`` is provided.

``timeout`` *(int | float | timedelta | str)* -- Maximum time to wait before timing out.
Accepts an ``int``/``float`` (seconds), a ``datetime.timedelta`` object, or a
human-readable string parsed by `parsedatetime <https://pypi.org/project/parsedatetime/>`_
(e.g. ``"1h 10m 5s"``, ``"2 minutes"``). When provided, this takes precedence
over ``num_sec``.

``delay`` *(int | float)* -- Seconds to sleep between attempts. Default: ``1``.

``expo`` *(bool)* -- When truthy, the ``delay`` is doubled after each failed attempt
(exponential backoff). Default: ``False``.

.. note::
   When using ``expo``, the reported elapsed time may be slightly inaccurate because
   ``wait_for`` only knows when the last *check* succeeded, not the exact moment the
   function started returning a passing value.

``message`` *(str | None)* -- A human-readable description of what is being waited on,
used in log messages and timeout error text. Default: auto-generated from
``func``'s name, partial arguments, or lambda source code.

``fail_condition`` *(callable | Any | set)* -- Defines what counts as a failed attempt.

- **Value** -- If ``func()`` returns this value, the attempt is considered failed and
  ``wait_for`` retries. Default: ``False``.
- **Callable** -- A function that receives the result and returns ``True`` if the
  attempt should be considered failed.
- **Set** -- The attempt fails if the result is a member of the set.

``handle_exception`` *(Type[Exception] | Iterable[Type[Exception]] | bool)* -- Controls
exception handling during ``func()`` invocation.

- ``False`` (default) -- Exceptions propagate immediately.
- ``True`` -- Any exception is caught and treated as a failed attempt.
- **Exception type or iterable of types** -- Only the listed exception types are caught;
  all others propagate. If the wait times out while handling exceptions, ``TimedOutError``
  is raised *from* the last caught exception (chained via ``__cause__``).

``raise_original`` *(bool)* -- When ``True`` and the wait times out while
``handle_exception`` is active, re-raises the last original exception instead of
``TimedOutError``. Default: ``False``.

``fail_func`` *(callable | None)* -- A callback invoked after every failed attempt
(after sleeping). Useful for cleanup or logging side-effects. Default: ``None``.

``quiet`` *(bool)* -- Suppress the ``"Took X to do Y"`` debug log emitted on a successful
return. Default: ``False``. Note: the secondary ``"Finished ..."`` debug message emitted
on success is only suppressed by ``very_quiet``, not by ``quiet`` alone.

``very_quiet`` *(bool)* -- Suppress the ``"Started ..."`` debug log at entry and both
``"Finished ..."`` debug logs (on success and on timeout expiry). Implies ``quiet``.
Default: ``False``. Note: ``logger.info`` messages produced by ``log_on_loop`` and by
exception handling are **not** suppressed by ``very_quiet``.

``silent_failure`` *(bool)* -- When ``True``, a timeout does **not** raise
``TimedOutError``. Instead, a ``WaitForResult`` is returned with the last
``func()`` output and the elapsed time at timeout. Default: ``False``.

``log_on_loop`` *(bool)* -- Emit a ``logger.info`` message at each iteration of the
wait loop, indicating the attempt number. Default: ``False``. This message is emitted
regardless of the ``quiet`` or ``very_quiet`` flags.

**Returns:**

A ``WaitForResult`` named tuple (see below).

**Raises:**

``TimedOutError`` -- If the timeout is exceeded without a successful result and
``silent_failure`` is not set.


``WaitForResult``
~~~~~~~~~~~~~~~~~

A ``typing.NamedTuple`` subclass returned by ``wait_for`` and ``wait_for_decorator``.

.. code-block:: python

   from typing import Any, NamedTuple

   class WaitForResult(NamedTuple):
       out: Any
       duration: float

``out`` *(Any)* -- The return value from the waited-on function.

``duration`` *(float)* -- Wall-clock seconds elapsed from the start of waiting until
``func()`` succeeded, or until the timeout was reached when ``silent_failure=True``.


``wait_for_decorator``
~~~~~~~~~~~~~~~~~~~~~~

A decorator wrapper around ``wait_for`` for cleaner syntax in tests and scripts.
All keyword arguments accepted by ``wait_for`` can be passed to the decorator.

**With parameters:**

.. code-block:: python

   from wait_for import wait_for_decorator

   @wait_for_decorator(num_sec=120, fail_condition=0, delay=0.05)
   def my_waiting_func():
       return do_something()

   # my_waiting_func is now a WaitForResult
   print(my_waiting_func.out, my_waiting_func.duration)

**Without parameters** (uses ``wait_for`` defaults):

.. code-block:: python

   @wait_for_decorator
   def my_waiting_func():
       return do_something()


``TimedOutError``
~~~~~~~~~~~~~~~~~

Exception raised when ``wait_for`` exceeds its timeout without a successful result.
Subclasses ``Exception``.

When ``handle_exception`` is active and exceptions were caught during waiting, the
``TimedOutError`` is chained from the last caught exception (accessible via
``__cause__``).


``RefreshTimer``
~~~~~~~~~~~~~~~~

A simple thread-based timer for periodic refresh checks.

.. code-block:: python

   from wait_for import RefreshTimer

   RefreshTimer(time_for_refresh=300, callback=None, *args, **kwargs)

``time_for_refresh`` *(int | float)* -- Seconds before the timer fires. Default: ``300``.

``callback`` *(callable | None)* -- Function to call when the timer fires. If ``None``,
defaults to an internal method that sets a boolean flag.

``*args, **kwargs`` -- Forwarded to the callback.

**Methods:**

- ``start()`` -- Cancel any previously scheduled timer and start a new background daemon
  thread. Safe to call multiple times; only one pending timer will be active at a time.
- ``reset()`` -- Reset the fired flag and call ``start()`` to schedule a fresh timer.
- ``is_it_time()`` -- Returns ``True`` if the timer has fired since the last reset.

**Example:**

.. code-block:: python

   timer = RefreshTimer(time_for_refresh=60)
   # ... later ...
   if timer.is_it_time():
       refresh_data()
       timer.reset()


Examples
--------

Basic wait with fail_condition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Wait until a function returns something other than ``0``:

.. code-block:: python

   import time
   from wait_for import wait_for

   class Incrementor:
       value = 0

       def i_sleep_a_lot(self):
           time.sleep(.1)
           self.value += 1
           return self.value

   incman = Incrementor()
   result, elapsed = wait_for(incman.i_sleep_a_lot,
                              fail_condition=0,
                              delay=0.05)

Using a lambda with func_args
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pass arguments to a lambda and wait until the condition is met:

.. code-block:: python

   incman = Incrementor()
   result, elapsed = wait_for(
       lambda self: self.i_sleep_a_lot() > 10,
       [incman],
       delay=0.05
   )

Human-readable timeout strings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use natural language for the timeout value:

.. code-block:: python

   from functools import partial

   func = partial(lambda: incman.i_sleep_a_lot() > 10)
   result, elapsed = wait_for(func, timeout="2s", delay=1)

The ``timeout`` parameter also accepts ``datetime.timedelta`` objects:

.. code-block:: python

   from datetime import timedelta

   result, elapsed = wait_for(func, timeout=timedelta(minutes=5), delay=1)

Exponential backoff
~~~~~~~~~~~~~~~~~~~

Double the delay after each failed attempt:

.. code-block:: python

   result, elapsed = wait_for(
       my_flaky_function,
       delay=1,
       expo=True,
       num_sec=120
   )

Exception handling
~~~~~~~~~~~~~~~~~~

Catch exceptions during waiting and convert them to retries:

.. code-block:: python

   from wait_for import wait_for, TimedOutError

   # Catch all exceptions
   result, elapsed = wait_for(
       might_raise,
       handle_exception=True,
       num_sec=30
   )

   # Catch only specific exception types
   result, elapsed = wait_for(
       might_raise,
       handle_exception=(ConnectionError, TimeoutError),
       num_sec=30
   )

   # Re-raise the original exception instead of TimedOutError
   try:
       wait_for(might_raise, handle_exception=True,
                num_sec=5, raise_original=True)
   except ConnectionError:
       print("Original exception re-raised")

Callable fail_condition
~~~~~~~~~~~~~~~~~~~~~~~

Use a function to define complex failure logic:

.. code-block:: python

   incman = Incrementor()
   result, elapsed = wait_for(
       incman.i_sleep_a_lot,
       fail_condition=lambda value: value <= 10,
       num_sec=30,
       delay=0.1
   )

Silent failure
~~~~~~~~~~~~~~

Return the last result instead of raising on timeout:

.. code-block:: python

   result, elapsed = wait_for(
       lambda: some_check(),
       num_sec=5,
       silent_failure=True
   )
   # result contains the last return value; elapsed == num_sec

Decorator usage
~~~~~~~~~~~~~~~

.. code-block:: python

   from wait_for import wait_for_decorator

   @wait_for_decorator(fail_condition=0, delay=0.05)
   def wait_until_incremented():
       return incman.i_sleep_a_lot()

   print(f"Got {wait_until_incremented.out} in "
         f"{wait_until_incremented.duration:.2f}s")


License
-------

Apache License 2.0. See `LICENSE <LICENSE>`_ for details.
