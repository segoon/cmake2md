import pytest

CMAKE_SOURCE = """\
# This comment is separated by a blank line and must not be picked up.

# @ingroup build
option(EXAMPLE_BUILD_TESTS "Build tests" ON)

option(EXAMPLE_STATIC "Link statically" OFF)

# @ingroup paths
set(EXAMPLE_DIR "/opt/example" CACHE PATH "Where example lives")

# Adds a library.
#
# @arg NAME the target name
# @option EXCLUDE_FROM_ALL do not build by default
# @param OUTPUT_NAME @required the artifact name
# @multiparam SOURCES the sources
function(example_add_library)
endfunction()

function(undocumented_function)
endfunction()
"""


@pytest.fixture
def cmake_file(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(CMAKE_SOURCE, encoding='utf-8')
    return path
