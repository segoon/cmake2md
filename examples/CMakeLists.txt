# An example project showing what cmake2md reads.
#
# Render it with:
#   cmake2md --template examples/reference.md.jinja \
#            --output examples/reference.md \
#            examples/CMakeLists.txt

cmake_minimum_required(VERSION 3.20)
project(example_project)

# @ingroup build
option(EXAMPLE_BUILD_TESTS "Build the test suite" ON)

# @ingroup build
option(EXAMPLE_BUILD_DOCS "Build the HTML documentation" OFF)

# Enable the sanitizers listed in EXAMPLE_SANITIZERS.
# @ingroup compilation
option(EXAMPLE_USE_SANITIZERS "Build with sanitizers enabled" OFF)

# Not tagged with @ingroup, so it lands in the ungrouped table.
option(EXAMPLE_STATIC "Link everything statically" OFF)

# @ingroup paths
set(EXAMPLE_TOOLCHAIN_DIR "/usr/local/toolchain" CACHE PATH "Toolchain location")

# Adds a library target together with its tests and install rules.
#
# The description may safely contain an e-mail address such as
# maintainer@example.com or a literal @@ sign.
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
# @arg NAME the name of the test
# @multiparam SOURCES the source files to compile
# @param TIMEOUT seconds before the test is considered hung
function(example_add_test)
    cmake_parse_arguments(ARG "" "TIMEOUT" "SOURCES" ${ARGN})
endfunction()
