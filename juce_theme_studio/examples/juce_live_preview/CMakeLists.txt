cmake_minimum_required(VERSION 3.22)
# JUCE builds SheenBidi as C; both languages must be enabled.
project(JuceLivePreview VERSION 1.0.0 LANGUAGES C CXX)

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
    COMPANY_NAME "JUCEThemeStudio"
    BUNDLE_ID com.jucethemestudio.JuceLivePreview)

target_sources(JuceLivePreview PRIVATE Source/Main.cpp)
target_compile_features(JuceLivePreview PRIVATE cxx_std_17)
target_link_libraries(JuceLivePreview PRIVATE juce::juce_gui_extra)
