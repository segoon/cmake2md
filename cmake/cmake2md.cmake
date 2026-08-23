#[==[.rst:
@file
@brief Runs cmake2md from a CMake build.

Include this module to document a project's own CMake code as part of its
build, rather than from a separate script that has to be remembered:

```cmake
include(cmake2md)

cmake2md_generate(TARGET docs)
```

What to render, where to write it and which files to read are in the
project's `cmake2md.toml`, so they are written once rather than once here and
once there.

The module is itself documented with cmake2md's own tags, so it doubles as a
worked example.
#]==]

# @defgroup cmake Using cmake2md from CMake
#
# What a CMakeLists.txt needs in order to generate its own documentation.

#[==[.rst:
@brief Adds targets that generate documentation from CMake sources.

Two of them: TARGET writes the documentation, and `<TARGET>-check` verifies
that it is up to date and fails when it is not, which is what a CI job wants.

Neither is built by default: documentation that regenerates on every build is
documentation that shows up in every diff. Ask for one by name, or pass ALL.

cmake2md is run from the current source directory, and reads the nearest
`cmake2md.toml` at or above it. Everything it does is said there; a target
that repeated any of it would be a second place to keep in step.

@ingroup cmake

@param TARGET @required the name of the target to add; the verifying target
    is named after it, with `-check` on the end
@option ALL build TARGET as part of the default build

@example
cmake2md_generate(TARGET docs)
#]==]
function(cmake2md_generate)
    cmake_parse_arguments(ARG "ALL" "TARGET" "" ${ARGN})

    if(NOT ARG_TARGET)
        message(FATAL_ERROR "cmake2md_generate: TARGET is required")
    endif()

    if(NOT CMAKE2MD_EXECUTABLE)
        find_program(CMAKE2MD_EXECUTABLE cmake2md)
    endif()
    if(NOT CMAKE2MD_EXECUTABLE)
        message(
            FATAL_ERROR
            "cmake2md_generate: cmake2md was not found on PATH. Install it "
            "with 'pip install cmake2md', or set CMAKE2MD_EXECUTABLE to its "
            "location."
        )
    endif()

    set(all "")
    if(ARG_ALL)
        set(all ALL)
    endif()

    add_custom_target(
        ${ARG_TARGET} ${all}
        COMMAND ${CMAKE2MD_EXECUTABLE}
        # Where cmake2md.toml is looked for, and what the paths in it are
        # relative to. The output is a source file, not a build artifact: it
        # is committed, and writing it into the build tree would hide it from
        # review.
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        COMMENT "cmake2md: ${ARG_TARGET}"
        VERBATIM
    )

    add_custom_target(
        ${ARG_TARGET}-check
        COMMAND ${CMAKE2MD_EXECUTABLE} --check
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        COMMENT "cmake2md: checking ${ARG_TARGET}"
        VERBATIM
    )
endfunction()
