# A small project rendered with the built-in reStructuredText template.
#
# Render it with:
#   cmake2doc --template reference.rst.jinja \
#            --output examples/rest/reference.rst \
#            examples/rest/CMakeLists.txt

cmake_minimum_required(VERSION 3.20)
project(example_rest)

# @defgroup build Build targets
#
# What gets built, and what is left out.

# @ingroup build
option(EXAMPLE_BUILD_TESTS "Build the test suite" ON)

# Ungrouped, so it lands in a table of its own below the grouped ones.
set(EXAMPLE_LOG_LEVEL "info" CACHE STRING "How much the build prints")
set_property(CACHE EXAMPLE_LOG_LEVEL PROPERTY STRINGS quiet info verbose)

# @brief Adds a library target.
#
# The description, the parameters and the sections below all survive the
# journey into reStructuredText.
#
# @since 0.2
#
# @note Call this after project(), so that the compiler is known.
#
# @example
# example_add_library(
#     NAME example_core
#     SOURCES src/a.cpp
# )
#
# @arg NAME the name of the resulting target
# @option EXCLUDE_FROM_ALL do not build this target by default
# @param OUTPUT_NAME @required file name of the produced artifact
# @multiparam SOURCES the source files to compile
function(example_add_library)
    cmake_parse_arguments(
        ARG "EXCLUDE_FROM_ALL" "OUTPUT_NAME" "SOURCES" ${ARGN}
    )
endfunction()

# Registers a test executable.
#
# @deprecated use example_add_library() instead.
#
# @arg NAME the name of the test
# @param TIMEOUT seconds before the test is considered hung
function(example_add_test)
    cmake_parse_arguments(ARG "" "TIMEOUT" "" ${ARGN})
endfunction()

# Looks up the version of a toolchain.
#
# @arg NAME the toolchain to look up
# @set_parent_scope EXAMPLE_TOOLCHAIN_VERSION the version that was found
function(example_toolchain_version NAME)
    set(EXAMPLE_TOOLCHAIN_VERSION "1.0" PARENT_SCOPE)
endfunction()

# Aborts the configuration with a message.
#
# @arg REASON why the build cannot continue
macro(example_fail)
    message(FATAL_ERROR "${ARGV0}")
endmacro()
