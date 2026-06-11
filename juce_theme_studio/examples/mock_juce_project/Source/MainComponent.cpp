#include "MainComponent.h"

MainComponent::MainComponent()
{
    setSize(800, 600);
    addAndMakeVisible(gainSlider);
    addAndMakeVisible(bypassButton);
    addAndMakeVisible(titleLabel);
}

MainComponent::~MainComponent() = default;

void MainComponent::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colours::darkgrey);
}

void MainComponent::resized()
{
    gainSlider.setBounds(100, 200, 64, 64);
    bypassButton.setBounds(200, 200, 80, 32);
    titleLabel.setBounds(50, 50, 200, 24);
}
