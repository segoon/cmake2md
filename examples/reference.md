# API reference

## Functions


## example_add_library

Adds a library target together with its tests and install rules.

The description may safely contain an e-mail address such as
maintainer@example.com or a literal @ sign.

```
example_add_library(
    <NAME>
    [EXCLUDE_FROM_ALL]
    OUTPUT_NAME <value>
    [SOURCES <value>...]
    [DEPENDS <value>...]
)
```

* <**NAME**> the name of the resulting target
* **EXCLUDE_FROM_ALL** do not build this target by default
* **OUTPUT_NAME <value>** file name of the produced artifact
* **SOURCES <value>...** the source files to compile
* **DEPENDS <value>...** targets this library links against


```cmake
example_add_library(
    NAME example_core
    OUTPUT_NAME core
    SOURCES src/a.cpp src/b.cpp
)
```


> **Note:** Call this after project(), so that the compiler is known.

## example_add_test

**Deprecated.**

Registers a test executable.

use example_add_library(... SOURCES ...) with EXCLUDE_FROM_ALL
instead.

```
example_add_test(
    <NAME>
    [TIMEOUT <value>]
    [SOURCES <value>...]
)
```

* <**NAME**> the name of the test
* **TIMEOUT <value>** seconds before the test is considered hung
* **SOURCES <value>...** the source files to compile

## example_toolchain_version

Looks up the version of a toolchain.

The argument is named in the function() line and the result is set in the
caller's scope, so cmake2md checks both against this comment.

```
example_toolchain_version(
    <NAME>
)
```

* <**NAME**> the toolchain to look up

Sets in the caller's scope:

* **EXAMPLE_TOOLCHAIN_VERSION** the version that was found


## Macros


## example_fail

Aborts the configuration with a message.

A macro rather than a function, so that the arguments are substituted in the
caller's scope.

```
example_fail(
    <REASON>
)
```

* <**REASON**> why the build cannot continue


# Build options

## General

| Option | Description | Default |
|--------|-------------|---------|
| `EXAMPLE_STATIC` | Link everything statically | `OFF` |


## Build targets

| Option | Description | Default |
|--------|-------------|---------|
| `EXAMPLE_BUILD_TESTS` | Build the test suite | `ON` |
| `EXAMPLE_BUILD_DOCS` | Build the HTML documentation | `OFF` |


## Compilation modes

| Option | Description | Default |
|--------|-------------|---------|
| `EXAMPLE_USE_SANITIZERS` | Build with sanitizers enabled | `OFF` |
| `EXAMPLE_SANITIZERS` | Sanitizers to enable (one of: address, thread, undefined) | `address` |


## Paths

| Variable | Description | Default |
|--------|-------------|---------|
| `EXAMPLE_TOOLCHAIN_DIR` | Toolchain location | `/usr/local/toolchain` |
