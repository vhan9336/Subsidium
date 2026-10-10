cmake_minimum_required(VERSION 3.20)
project(SecondOpinion CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")
option(SO_NATIVE "Optimise for this CPU" ON)
if(SO_NATIVE)
  add_compile_options(-march=native)
endif()

option(SO_BUILD_APP "Build the SDL3 + Dear ImGui visualizer" ON)

# Core estimator: no dependencies, runs on a laptop or a Raspberry Pi.
add_library(so_core
  src/core/image.cpp
  src/core/ttc.cpp
  src/core/fusion.cpp
  src/core/hazard.cpp)
target_include_directories(so_core PUBLIC src)
target_compile_options(so_core PRIVATE -Wall -Wextra)

# Simulated moonscape, camera, rangefinder and landers.
add_library(so_sim
  src/sim/terrain.cpp
  src/sim/sensors.cpp
  src/sim/simulation.cpp)
find_package(Threads REQUIRED)
target_link_libraries(so_sim PUBLIC so_core Threads::Threads)
target_compile_options(so_sim PRIVATE -Wall -Wextra)

# Live hardware: V4L2 webcam + Arduino over serial (Linux).
add_library(so_live
  src/live/serial.cpp
  src/live/webcam.cpp
  src/live/rig.cpp)
target_link_libraries(so_live PUBLIC so_core)
target_compile_options(so_live PRIVATE -Wall -Wextra)

add_executable(so_sim_cli src/cli/run_scenarios.cpp)
target_link_libraries(so_sim_cli PRIVATE so_sim)

enable_testing()
add_executable(so_tests tests/tests.cpp)
target_link_libraries(so_tests PRIVATE so_sim)
add_test(NAME so_tests COMMAND so_tests)

if(SO_BUILD_APP)
  find_package(SDL3 REQUIRED CONFIG)
  include(FetchContent)
  FetchContent_Declare(imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui.git
    GIT_TAG v1.91.9b
    GIT_SHALLOW TRUE)
  FetchContent_Declare(implot
    GIT_REPOSITORY https://github.com/epezent/implot.git
    GIT_TAG v0.16
    GIT_SHALLOW TRUE)
  FetchContent_MakeAvailable(imgui implot)

  add_library(imgui_lib STATIC
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_sdl3.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_sdlrenderer3.cpp
    ${implot_SOURCE_DIR}/implot.cpp
    ${implot_SOURCE_DIR}/implot_items.cpp)
  target_include_directories(imgui_lib PUBLIC ${imgui_SOURCE_DIR} ${imgui_SOURCE_DIR}/backends ${implot_SOURCE_DIR})
  target_link_libraries(imgui_lib PUBLIC SDL3::SDL3)

  add_executable(second_opinion src/app/main.cpp src/app/views.cpp)
  target_link_libraries(second_opinion PRIVATE so_sim so_live imgui_lib)
  target_compile_options(second_opinion PRIVATE -Wall -Wextra)
endif()
