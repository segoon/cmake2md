#[==[.rst:
@file
@brief Runs cmake2md from a CMake build.

Include this module to document a project's own CMake code as part of its
build, rather than from a separate script that has to be remembered:

```cmake
include(cmake2md)

cmake2md_generate(
    TARGET docs
    TEMPLATE reference.md.jinja
    OUTPUT ${CMAKE_CURRENT_SOURCE_DIR}/docs/reference.md
    SOURCES cmake/helpers.cmake
)
```

The module is itself documented with cmake2md's own tags, so it doubles as a
worked example.
#]==]

# @defgroup cmake Using cmake2md from CMake
#
# What a CMakeLists.txt needs in order to generate its own documentation.

#[==[.rst:
@brief Adds a target that generates documentation from CMake sources.

The target is not built by default: documentation that regenerates on every
build is documentation that shows up in every diff. Ask for it by name, or
pass ALL when that is what you want.

@ingroup cmake

@param TARGET @required the name of the target to add
@param TEMPLATE @required the template to render, a path or a built-in name
@param OUTPUT @required the file to write
@multiparam SOURCES the CMake files to read; the current source directory
    when none are given
@multiparam EXTRA_ARGS further arguments for cmake2md, such as --strict
@option ALL build the target as part of the default build
@option CHECK verify that OUTPUT is up to date instead of writing it, which
    is what a CI job wants

@example
cmake2md_generate(
    TARGET docs-check
    TEMPLATE reference.md.jinja
    OUTPUT ${CMAKE_CURRENT_SOURCE_DIR}/docs/reference.md
    CHECK
)
#]==]
function(cmake2md_generate)
    cmake_parse_arguments(
        ARG "ALL;CHECK" "TARGET;TEMPLATE;OUTPUT" "SOURCES;EXTRA_ARGS" ${ARGN}
    )

    foreach(required TARGET TEMPLATE OUTPUT)
        if(NOT ARG_${required})
            message(FATAL_ERROR "cmake2md_generate: ${required} is required")
        endif()
    endforeach()

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

    if(NOT ARG_SOURCES)
        set(ARG_SOURCES ${CMAKE_CURRENT_SOURCE_DIR})
    endif()

    set(command
        ${CMAKE2MD_EXECUTABLE}
        --template ${ARG_TEMPLATE}
        --output ${ARG_OUTPUT}
        ${ARG_EXTRA_ARGS}
        ${ARG_SOURCES}
    )
    if(ARG_CHECK)
        list(INSERT command 1 --check)
    endif()

    set(all "")
    if(ARG_ALL)
        set(all ALL)
    endif()

    add_custom_target(
        ${ARG_TARGET} ${all}
        COMMAND ${command}
        # The output is a source file, not a build artifact: it is committed,
        # and generating it in the build tree would hide it from review.
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        DEPENDS ${ARG_SOURCES}
        COMMENT "cmake2md: ${ARG_OUTPUT}"
        VERBATIM
    )
endfunction()
