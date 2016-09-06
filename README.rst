wait-for
========

Introduction
------------

Waits for a certain amount of time for an action to complete
Designed to wait for a certain length of time,
either linearly in 1 second steps, or exponentially, up to a maximum.
Returns the output from the function once it completes successfully,
along with the time taken to complete the command.

.. note::
   If using the expo keyword, the returned elapsed time will be inaccurate
   as wait_for does not know the exact time that the function returned
   correctly, only that it returned correctly at last check.

Usage
-----

.. code-block:: python

  from wait_for import wait_for

  class Incrementor():
      value = 0

      def i_sleep_a_lot(self):
          time.sleep(.1)
          self.value += 1
          return self.value


  incman = Incrementor()
  ec, tc = wait_for(incman.i_sleep_a_lot,
                    fail_condition=0,
                    delay=.05)
  print("Function output {} in time {} ".format(ec, tc))
