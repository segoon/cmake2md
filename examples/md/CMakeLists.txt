# An example project showing what cmake2doc reads.
#
# Render it with:
#   cmake2doc --template examples/md/reference.md.jinja \
#            --output examples/md/reference.md \
#            examples/md/CMakeLists.txt

cmake_minimum_required(VERSION 3.20)
project(example_project)

# A comment block of its own defines a group, which is what keeps the group
# names out of the template.

# @defgroup build Build targets
#
# What gets built, and what is left out.

# @defgroup compilation Compilation modes
#
# How the sources are compiled.

# @defgroup paths Paths
#
# Where the build looks for things it does not carry itself.

# @ingroup build
option(EXAMPLE_BUILD_TESTS "Build the test suite" ON)

# @ingroup build
option(EXAMPLE_BUILD_DOCS "Build the HTML documentation" OFF)

# Enable the sanitizers listed in EXAMPLE_SANITIZERS.
# @ingroup compilation
option(EXAMPLE_USE_SANITIZERS "Build with sanitizers enabled" OFF)

# @ingroup compilation
set(EXAMPLE_SANITIZERS "address" CACHE STRING "Sanitizers to enable")
set_property(CACHE EXAMPLE_SANITIZERS PROPERTY STRINGS address thread undefined)

# Not tagged with @@ingroup, so it lands in the ungrouped table.
option(EXAMPLE_STATIC "Link everything statically" OFF)

# @ingroup paths
set(EXAMPLE_TOOLCHAIN_DIR "/usr/local/toolchain" CACHE PATH "Toolchain location")

# @brief Adds a library target together with its tests and install rules.
#
# The description may safely contain an e-mail address such as
# maintainer@example.com or a literal @@ sign.
#
# @note Call this after project(), so that the compiler is known.
#
# @example
# example_add_library(
#     NAME example_core
#     OUTPUT_NAME core
#     SOURCES src/a.cpp src/b.cpp
# )
#
# @arg NAME the name of the resulting target
# @option EXCLUDE_FROM_ALL do not build this target by default
# @param OUTPUT_NAME @required file name of the produced artifact
# @multiparam SOURCES the source files to compile
# @multiparam DEPENDS targets this library links against
function(example_add_library)
    cmake_parse_arguments(
        ARG "EXCLUDE_FROM_ALL" "OUTPUT_NAME" "SOURCES;DEPENDS" ${ARGN}
    )
endfunction()

# Registers a test executable.
#
# @deprecated use example_add_library(... SOURCES ...) with EXCLUDE_FROM_ALL
# instead.
#
# @arg NAME the name of the test
# @multiparam SOURCES the source files to compile
# @param TIMEOUT seconds before the test is considered hung
function(example_add_test)
    cmake_parse_arguments(ARG "" "TIMEOUT" "SOURCES" ${ARGN})
endfunction()

# Looks up the version of a toolchain.
#
# The argument is named in the function() line and the result is set in the
# caller's scope, so cmake2doc checks both against this comment.
#
# @arg NAME the toolchain to look up
# @set_parent_scope EXAMPLE_TOOLCHAIN_VERSION the version that was found
function(example_toolchain_version NAME)
    set(EXAMPLE_TOOLCHAIN_VERSION "1.0" PARENT_SCOPE)
endfunction()

# Aborts the configuration with a message.
#
# A macro rather than a function, so that the arguments are substituted in the
# caller's scope.
#
# @arg REASON why the build cannot continue
macro(example_fail)
    message(FATAL_ERROR "${ARGV0}")
endmacro()

# A blank line ends a comment block, so the helper below counts as
# undocumented and the `documented` filter leaves it out of the reference.

function(_example_internal_helper)
endfunction()
