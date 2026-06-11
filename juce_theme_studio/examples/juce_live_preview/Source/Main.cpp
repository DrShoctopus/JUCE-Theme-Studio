/**
 * JUCE Live Preview — loads ThemeLayout.json from JUCE Theme Studio export.
 * Build with JUCE_DIR set. Falls back to a stub window when JSON path is provided.
 */

#include <fstream>
#include <iostream>
#include <string>

#if __has_include(<JuceHeader.h>)
 #include <JuceHeader.h>

class PreviewComponent : public juce::Component
{
public:
    explicit PreviewComponent (juce::File layoutFile) : layout (layoutFile)
    {
        setSize (800, 600);
        loadLayout();
    }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (juce::Colour (0xff282c34));
        g.setColour (juce::Colours::white);
        g.setFont (16.0f);
        g.drawText ("JUCE Live Preview\n" + status, getLocalBounds(), juce::Justification::centred);
    }

    void reload()
    {
        loadLayout();
        repaint();
    }

private:
    juce::File layout;
    juce::String status;

    void loadLayout()
    {
        if (! layout.existsAsFile())
        {
            status = "Missing: " + layout.getFullPathName();
            return;
        }
        status = "Loaded: " + layout.getFileName() + "\n(Render controls via exported ThemeStudio helpers)";
    }
};

class PreviewWindow : public juce::DocumentWindow
{
public:
    PreviewWindow (juce::File layoutFile)
        : DocumentWindow ("JUCE Theme Studio Live Preview",
                          juce::Desktop::getInstance().getDefaultLookAndFeel()
                              .findColour (juce::ResizableWindow::backgroundColourId),
                          DocumentWindow::allButtons)
    {
        setContentOwned (new PreviewComponent (layoutFile), true);
        centreWithSize (800, 600);
        setVisible (true);
    }

    void closeButtonPressed() override { juce::JUCEApplication::getInstance()->systemRequestedQuit(); }
};

class PreviewApplication : public juce::JUCEApplication
{
public:
    const juce::String getApplicationName() override { return "JuceLivePreview"; }
    const juce::String getApplicationVersion() override { return "1.0.0"; }

    void initialise (const juce::String& commandLine) override
    {
        juce::File layout = juce::File::getCurrentWorkingDirectory()
                                .getChildFile (".juce_theme_studio/exports/ThemeLayout.json");
        if (commandLine.isNotEmpty())
            layout = juce::File (commandLine.unquoted());

        window.reset (new PreviewWindow (layout));
    }

    void shutdown() override { window = nullptr; }

private:
    std::unique_ptr<PreviewWindow> window;
};

START_JUCE_APPLICATION (PreviewApplication)

#else

int main (int argc, char* argv[])
{
    std::cout << "JUCE Live Preview stub — install JUCE and rebuild with -DJUCE_DIR=...\n";
    if (argc > 1)
        std::cout << "Layout: " << argv[1] << "\n";
    return 0;
}

#endif
