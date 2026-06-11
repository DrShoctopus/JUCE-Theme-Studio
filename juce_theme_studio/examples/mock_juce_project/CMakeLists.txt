cmake_minimum_required(VERSION 3.22)
project(MockJucePlugin VERSION 1.0.0)

add_subdirectory(JUCE)  # placeholder — not required for Theme Studio tests

add_executable(MockPlugin
    Source/MainComponent.cpp
)

target_link_libraries(MockPlugin PRIVATE juce::juce_gui_basics)
