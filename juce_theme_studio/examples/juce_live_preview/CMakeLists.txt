cmake_minimum_required(VERSION 3.22)
project(JuceLivePreview VERSION 1.0.0 LANGUAGES CXX)

# Point JUCE_DIR to your JUCE install, e.g.:
# cmake -B build -DJUCE_DIR=~/JUCE

if(NOT DEFINED JUCE_DIR)
    message(WARNING "Set -DJUCE_DIR=/path/to/JUCE for a full build. Generating stub target only.")
    add_executable(JuceLivePreview Source/Main.cpp)
    return()
endif()

add_subdirectory(${JUCE_DIR} JUCE)

juce_add_gui_app(JuceLivePreview
    PRODUCT_NAME "JUCE Live Preview"
    COMPANY_NAME "JUCE Theme Studio")

target_sources(JuceLivePreview PRIVATE Source/Main.cpp)
target_compile_features(JuceLivePreview PRIVATE cxx_std_17)
target_link_libraries(JuceLivePreview PRIVATE juce::juce_gui_extra)
