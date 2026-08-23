Reference
=========


.. contents::
   :local:


Functions and macros
--------------------

example_add_library
~~~~~~~~~~~~~~~~~~~

Adds a library target.

The description, the parameters and the sections below all survive the
journey into reStructuredText.

.. code:: cmake

   example_add_library(
       <NAME>
       [EXCLUDE_FROM_ALL]
       OUTPUT_NAME <value>
       [SOURCES <value>...]
   )

:param NAME: the name of the resulting target
:option EXCLUDE_FROM_ALL: do not build this target by default
:param OUTPUT_NAME <value>: file name of the produced artifact
:param SOURCES <value>...: the source files to compile
:since: 0.2

.. code:: cmake

   example_add_library(
       NAME example_core
       SOURCES src/a.cpp
   )

.. note::

   Call this after project(), so that the compiler is known.

example_add_test
~~~~~~~~~~~~~~~~

.. warning::

   Deprecated.

Registers a test executable.

use example_add_library() instead.

.. code:: cmake

   example_add_test(
       <NAME>
       [TIMEOUT <value>]
   )

:param NAME: the name of the test
:param TIMEOUT <value>: seconds before the test is considered hung

example_toolchain_version
~~~~~~~~~~~~~~~~~~~~~~~~~

Looks up the version of a toolchain.

.. code:: cmake

   example_toolchain_version(
       <NAME>
   )

:param NAME: the toolchain to look up
:sets EXAMPLE_TOOLCHAIN_VERSION: the version that was found

example_fail
~~~~~~~~~~~~

Aborts the configuration with a message.

.. code:: cmake

   example_fail(
       <REASON>
   )

:param REASON: why the build cannot continue

Build options
-------------

Build targets
~~~~~~~~~~~~~

What gets built, and what is left out.

.. list-table:: Build targets
   :header-rows: 1
   :widths: 25 55 20

   * - Option
     - Description
     - Default
   * - ``EXAMPLE_BUILD_TESTS``
     - Build the test suite
     - ``ON``

Other
~~~~~

.. list-table:: Options
   :header-rows: 1
   :widths: 25 55 20

   * - Option
     - Description
     - Default
   * - ``EXAMPLE_LOG_LEVEL``
     - How much the build prints (one of: quiet, info, verbose)
     - ``info``
