# A small project rendered into Sphinx CMake-domain directives.
#
# Render it with:
#   cmake2doc --template examples/sphinx/reference.rst.jinja \
#            --output examples/sphinx/reference.rst \
#            examples/sphinx/CMakeLists.txt

cmake_minimum_required(VERSION 3.20)
project(example_sphinx)

# @ingroup build
option(EXAMPLE_BUILD_TESTS "Build the test suite" ON)

# @defgroup build Build targets
#
# What gets built, and what is left out.

# @brief Adds a library target.
#
# A cross-reference to :cmake:command:`example_fail` is written by hand: the
# domain directives below are what make it resolve.
#
# @since 0.2
#
# @note Call this after project(), so that the compiler is known.
#
# @arg NAME the name of the resulting target
# @param OUTPUT_NAME @required file name of the produced artifact
# @multiparam SOURCES the source files to compile
function(example_add_library)
    cmake_parse_arguments(ARG "" "OUTPUT_NAME" "SOURCES" ${ARGN})
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

# Aborts the configuration with a message.
#
# @arg REASON why the build cannot continue
macro(example_fail)
    message(FATAL_ERROR "${ARGV0}")
endmacro()
