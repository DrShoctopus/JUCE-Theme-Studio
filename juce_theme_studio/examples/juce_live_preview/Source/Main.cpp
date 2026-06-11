/**
 * JUCE Live Preview — renders a ThemeLayout.json exported by JUCE Theme Studio.
 *
 * Self-contained: it parses the layout, loads images from the sibling assets/
 * folder, and paints the background, sprite frames, and labels. It polls the
 * layout file's modification time so re-exports from the editor show up live.
 *
 * Build with JUCE_DIR set (see CMakeLists.txt). Without JUCE it builds a stub.
 */

#include <iostream>
#include <string>

#if __has_include(<JuceHeader.h>)
 #include <JuceHeader.h>

namespace
{
juce::Rectangle<int> boundsOf (const juce::var& control)
{
    auto* b = control.getProperty ("bounds", {}).getDynamicObject();
    if (b == nullptr)
        return {};
    return { (int) b->getProperty ("x"), (int) b->getProperty ("y"),
             (int) b->getProperty ("width"), (int) b->getProperty ("height") };
}

juce::Image sliceFrame (const juce::Image& sheet, int frameIndex, const juce::var& cfg)
{
    if (! sheet.isValid() || ! cfg.isObject())
        return {};

    const int count  = juce::jmax (1, (int) cfg.getProperty ("frame_count", 1));
    int fw           = (int) cfg.getProperty ("frame_width", 0);
    int fh           = (int) cfg.getProperty ("frame_height", 0);
    const int cols   = juce::jmax (1, (int) cfg.getProperty ("columns", 1));
    const juce::String layout = cfg.getProperty ("layout", "horizontal_strip").toString();

    if (fw <= 0) fw = sheet.getWidth() / count;
    if (fh <= 0) fh = sheet.getHeight();
    if (fw <= 0 || fh <= 0)
        return {};

    const int idx = juce::jlimit (0, count - 1, frameIndex);
    int x = 0, y = 0;
    if (layout == "vertical_strip")      { x = 0;                 y = idx * fh; }
    else if (layout == "grid")           { x = (idx % cols) * fw; y = (idx / cols) * fh; }
    else                                 { x = idx * fw;          y = 0; }

    const juce::Rectangle<int> area = juce::Rectangle<int> (x, y, fw, fh)
                                          .getIntersection (sheet.getBounds());
    return area.isEmpty() ? juce::Image() : sheet.getClippedImage (area);
}

int frameIndexFor (const juce::var& control, const juce::var& cfg)
{
    const juce::String type = control.getProperty ("type", {}).toString();
    const int count = juce::jmax (1, (int) cfg.getProperty ("frame_count", 1));

    if (type == "button" || type == "toggle_button" || type == "switch" || type == "led")
    {
        const juce::var active = cfg.getProperty ("active_frame", {});
        if ((bool) control.getProperty ("on", false) && ! active.isVoid())
            return (int) active;
        return (int) cfg.getProperty ("default_frame", 0);
    }

    const double v = juce::jlimit (0.0, 1.0, (double) control.getProperty ("value", 0.0));
    return juce::roundToInt (v * (count - 1));
}

juce::Colour colourFromHex (const juce::var& v, juce::Colour fallback)
{
    const juce::String hex = v.toString();
    return hex.isEmpty() ? fallback : juce::Colour ((juce::uint32) hex.getHexValue64());
}
} // namespace

class PreviewComponent : public juce::Component,
                         private juce::Timer
{
public:
    explicit PreviewComponent (juce::File layoutFile) : layout (layoutFile)
    {
        loadLayout();
        startTimerHz (4); // poll for re-exports from the editor
    }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (background);

        if (! screen.isObject())
        {
            g.setColour (juce::Colours::white);
            g.setFont (15.0f);
            g.drawText ("JUCE Live Preview\n" + status, getLocalBounds(),
                        juce::Justification::centred, true);
            return;
        }

        const juce::String bgFile = screen.getProperty ("background_file", {}).toString();
        if (auto bg = getImage (bgFile); bg.isValid())
            g.drawImage (bg, getLocalBounds().toFloat(), juce::RectanglePlacement::stretchToFit);

        if (auto* controls = screen.getProperty ("controls", {}).getArray())
            for (auto& control : *controls)
                drawControl (g, control);
    }

private:
    juce::File layout;
    juce::String status;
    juce::var document, screen;
    juce::Colour background { 0xff282c34 };
    std::map<juce::String, juce::Image> images;
    juce::int64 lastModified = 0;

    void timerCallback() override
    {
        const juce::int64 mod = layout.getLastModificationTime().toMilliseconds();
        if (mod != lastModified)
            loadLayout();
    }

    juce::Image getImage (const juce::String& fileName)
    {
        if (fileName.isEmpty())
            return {};
        auto it = images.find (fileName);
        return it != images.end() ? it->second : juce::Image();
    }

    void loadLayout()
    {
        lastModified = layout.getLastModificationTime().toMilliseconds();
        images.clear();
        document = juce::var();
        screen = juce::var();

        if (! layout.existsAsFile())
        {
            status = "Missing: " + layout.getFullPathName();
            repaint();
            return;
        }

        document = juce::JSON::parse (layout);
        if (! document.isObject())
        {
            status = "Could not parse " + layout.getFileName();
            repaint();
            return;
        }

        background = colourFromHex (document.getProperty ("colors", {})
                                            .getProperty ("background", {}),
                                    juce::Colour (0xff282c34));

        const juce::File assetsDir = layout.getParentDirectory().getChildFile ("assets");
        auto loadImage = [&] (const juce::String& name)
        {
            if (name.isEmpty() || images.count (name) > 0)
                return;
            const juce::File f = assetsDir.getChildFile (name);
            if (f.existsAsFile())
                if (auto img = juce::ImageFileFormat::loadFrom (f); img.isValid())
                    images[name] = img;
        };

        if (auto* screens = document.getProperty ("screens", {}).getArray())
        {
            if (! screens->isEmpty())
                screen = screens->getFirst();
            for (auto& s : *screens)
            {
                loadImage (s.getProperty ("background_file", "").toString());
                if (auto* controls = s.getProperty ("controls", {}).getArray())
                    for (auto& c : *controls)
                        loadImage (c.getProperty ("asset_file", "").toString());
            }
        }

        const int w = (int) screen.getProperty ("width", 800);
        const int h = (int) screen.getProperty ("height", 600);
        setSize (juce::jmax (1, w), juce::jmax (1, h));
        status = "Loaded: " + layout.getFileName();
        repaint();
    }

    void drawControl (juce::Graphics& g, const juce::var& control)
    {
        const juce::Rectangle<int> bounds = boundsOf (control);
        if (bounds.isEmpty())
            return;

        const juce::String type = control.getProperty ("type", {}).toString();
        if (type == "label")
        {
            g.setColour (juce::Colours::white);
            const juce::String text = control.getProperty ("label_text", {}).toString();
            g.drawText (text.isNotEmpty() ? text : control.getProperty ("name", {}).toString(),
                        bounds, juce::Justification::centred, true);
            return;
        }

        const juce::Image sheet = getImage (control.getProperty ("asset_file", {}).toString());
        const juce::var cfg = control.getProperty ("sprite_config", {});

        if (auto frame = sliceFrame (sheet, frameIndexFor (control, cfg), cfg); frame.isValid())
        {
            g.drawImage (frame, bounds.toFloat(), juce::RectanglePlacement::centred);
            return;
        }
        if (sheet.isValid())
        {
            g.drawImage (sheet, bounds.toFloat(), juce::RectanglePlacement::centred);
            return;
        }

        g.setColour (juce::Colours::white.withAlpha (0.25f));
        g.fillRect (bounds);
        g.setColour (juce::Colours::black.withAlpha (0.4f));
        g.drawRect (bounds);
    }
};

class PreviewWindow : public juce::DocumentWindow
{
public:
    explicit PreviewWindow (juce::File layoutFile)
        : DocumentWindow ("JUCE Theme Studio Live Preview",
                          juce::Desktop::getInstance().getDefaultLookAndFeel()
                              .findColour (juce::ResizableWindow::backgroundColourId),
                          DocumentWindow::allButtons)
    {
        auto* content = new PreviewComponent (layoutFile);
        setContentOwned (content, true);
        setResizable (true, false);
        centreWithSize (juce::jmax (320, content->getWidth()),
                        juce::jmax (240, content->getHeight()));
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
