API reference
=============

.. cmake:command:: example_add_library(<NAME> OUTPUT_NAME <value> [SOURCES <value>...])

   Adds a library target.

   A cross-reference to :cmake:command:`example_fail` is written by hand: the
   domain directives below are what make it resolve.

   .. versionadded:: 0.2

   :param NAME: the name of the resulting target
   :param OUTPUT_NAME: file name of the produced artifact
   :param SOURCES: the source files to compile

   .. note::

      Call this after project(), so that the compiler is known.

.. cmake:command:: example_add_test(<NAME> [TIMEOUT <value>])

   Registers a test executable.

   use example_add_library() instead.

   .. deprecated:: unreleased

   :param NAME: the name of the test
   :param TIMEOUT: seconds before the test is considered hung

.. cmake:command:: example_fail(<REASON>)

   Aborts the configuration with a message.

   :param REASON: why the build cannot continue

Build options
=============

.. cmake:variable:: EXAMPLE_BUILD_TESTS

   Build the test suite

   Defaults to ``ON``.
