"""Help / User Guide dialog."""

# ruff: noqa: E501

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

_SECTIONS: list[tuple[str, str]] = [
    (
        "Getting Started",
        """
<h2>Getting Started</h2>

<h3>What is JUCE Theme Studio?</h3>
<p>JUCE Theme Studio is a standalone visual editor for designing, previewing, and exporting
themes for JUCE audio plugins and applications. Scanning and export work non-destructively
alongside your existing JUCE project; <b>Apply to Project</b> is the explicit managed write
path with preview, transaction backups, and revert support.</p>

<h3>Opening a Project</h3>
<ol>
  <li>Click <b>Open Project</b> in the toolbar (or <b>File → Open Project…</b>).</li>
  <li>Select your JUCE project root folder — the one containing
      <code>.jucer</code>, <code>CMakeLists.txt</code>, or a <code>Source/</code> directory.</li>
  <li>JUCE Theme Studio creates a hidden <code>.juce_theme_studio/</code> folder inside your project
      to store theme data, assets, and exports. Nothing else is changed.</li>
  <li>The scanner reads your C++ source and populates the <b>Screens</b> list with detected
      <code>juce::Component</code> subclasses.</li>
</ol>

<h3>The Studio Folder</h3>
<pre>
.juce_theme_studio/
  theme_project.json   — all layout, asset, and color data
  screens/             — per-screen metadata
  assets/              — imported image copies
  exports/             — generated C++ and JSON files
  backups/             — previous export snapshots
  logs/                — studio.log
</pre>

<h3>Typical Workflow</h3>
<ol>
  <li><b>Open</b> your JUCE project.</li>
  <li><b>Import assets</b> (images, sprite sheets) into the Asset Library.</li>
  <li><b>Select a screen</b> in the Screens list.</li>
  <li><b>Add controls</b> from the Control Palette and position them on the canvas.</li>
  <li><b>Link assets</b> to controls by dragging or clicking.</li>
  <li><b>Set JUCE mappings</b> in the Properties panel (class, variable, parameter ID).</li>
  <li><b>Export</b> — generates C++ and JSON ready to drop into your JUCE project.</li>
  <li><b>Commit</b> the <code>.juce_theme_studio/</code> folder to Git.</li>
</ol>
""",
    ),
    (
        "Screens & Canvas",
        """
<h2>Screens &amp; Canvas</h2>

<h3>Screen List (Left Panel)</h3>
<p>Each item represents one UI screen (a <code>juce::Component</code> subclass).
Screens detected automatically from your C++ source are listed with their class name in
brackets, e.g. <b>MainComponent [MainComponent]</b>. Manually created screens are tagged
<i>(manual)</i>.</p>

<ul>
  <li><b>New Screen</b> — opens a dialog to enter a name, width, and height for a
      blank manual screen.</li>
  <li><b>Fit</b> — zooms the canvas to fit the current screen in the viewport.</li>
  <li>Click any screen to switch to it; your layout is preserved.</li>
</ul>

<h3>Canvas Navigation</h3>
<ul>
  <li><b>Scroll wheel</b> — zoom in/out.</li>
  <li><b>Middle-click drag</b> or <b>space + drag</b> — pan.</li>
  <li><b>Fit Canvas</b> (toolbar or Fit button) — reset zoom to fit the canvas.</li>
</ul>

<h3>Screen Settings Panel (Right)</h3>
<p>Edit the canvas <b>Width</b> and <b>Height</b> for the selected screen. These values
correspond to <code>setSize(width, height)</code> in your JUCE component.</p>

<h3>Snap &amp; Grid</h3>
<p>Open <b>Settings</b> (toolbar or <b>File → Settings…</b>) to configure:</p>
<ul>
  <li><b>Grid size</b> — pixel interval for the background grid.</li>
  <li><b>Snap to grid</b> — snap control edges to grid lines while dragging.</li>
  <li><b>Smart snap guides</b> — blue alignment guides appear when a control's edge or
      center aligns with another control or the canvas edge.</li>
</ul>

<h3>Preview Mode</h3>
<p>Toggle <b>Preview Mode</b> in the toolbar to disable editing and simulate how the
theme will look at runtime. In preview mode:</p>
<ul>
  <li>Controls are not selectable or draggable.</li>
  <li>The <b>Preview Simulation</b> panel (right) lets you set button state
      (Normal / Hover / Active / Disabled) to preview sprite frames.</li>
  <li>Knob, meter, and slider controls respond to the <b>Value</b> field in Properties.</li>
</ul>
""",
    ),
    (
        "Controls",
        """
<h2>Controls</h2>

<h3>Control Palette</h3>
<p>Select a control type from the <b>Control Palette</b> dropdown (bottom-left), then click
<b>Add Control</b> to place it on the current screen. You can also pre-select an asset in
the Asset Library before adding — the asset will be linked automatically.</p>

<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse">
  <tr><th>Type</th><th>Description</th></tr>
  <tr><td><b>Knob</b></td><td>Rotary control. Sprite strip drives the rotation frame. Maps to <code>juce::Slider</code> (rotary).</td></tr>
  <tr><td><b>Button</b></td><td>Momentary push button. Sprite frames: normal, hover, active, disabled.</td></tr>
  <tr><td><b>Toggle</b></td><td>Latching on/off button. Two-state sprite.</td></tr>
  <tr><td><b>Switch</b></td><td>Horizontal or vertical flip switch.</td></tr>
  <tr><td><b>Meter</b></td><td>Generic level meter; sprite strip frames represent dB levels.</td></tr>
  <tr><td><b>VU Meter</b></td><td>VU-style meter with ballistics.</td></tr>
  <tr><td><b>GR Meter</b></td><td>Gain-reduction meter (inverted scale).</td></tr>
  <tr><td><b>Slider</b></td><td>Linear (horizontal or vertical) slider. Maps to <code>juce::Slider</code>.</td></tr>
  <tr><td><b>LED</b></td><td>Indicator light. Sprite frames: off / on.</td></tr>
  <tr><td><b>Image</b></td><td>Static decorative image. No interaction.</td></tr>
  <tr><td><b>Label</b></td><td>Text label. Font, size, and color set in Properties.</td></tr>
  <tr><td><b>Panel</b></td><td>Background region. Typically set via <b>Set Background</b>.</td></tr>
</table>

<h3>Moving &amp; Resizing</h3>
<ul>
  <li><b>Drag</b> a control to move it.</li>
  <li><b>Drag the resize handle</b> (bottom-right corner) to resize.</li>
  <li><b>Arrow keys</b> nudge selected controls 1 px; <b>Shift + Arrow</b> nudges 8 px.</li>
  <li>Hold <b>Shift</b> to add to the selection (multi-select).</li>
  <li><b>Ctrl/Cmd + A</b> selects all controls on the current screen.</li>
</ul>

<h3>Edit Operations</h3>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse">
  <tr><th>Action</th><th>Shortcut</th></tr>
  <tr><td>Copy</td><td>Ctrl/Cmd+C</td></tr>
  <tr><td>Cut</td><td>Ctrl/Cmd+X</td></tr>
  <tr><td>Paste (offset +20px)</td><td>Ctrl/Cmd+V</td></tr>
  <tr><td>Duplicate (offset +20px)</td><td>Ctrl/Cmd+D</td></tr>
  <tr><td>Delete</td><td>Delete</td></tr>
  <tr><td>Select All</td><td>Ctrl/Cmd+A</td></tr>
  <tr><td>Undo</td><td>Ctrl/Cmd+Z</td></tr>
  <tr><td>Redo</td><td>Ctrl/Cmd+Shift+Z</td></tr>
</table>

<h3>Layers Panel</h3>
<p>The <b>Layers</b> panel (right side) lists all controls on the current screen:</p>
<ul>
  <li><b>Visibility</b> — eye icon toggles canvas visibility.</li>
  <li><b>Lock</b> — padlock icon prevents dragging/resizing the control.</li>
  <li><b>Z-order</b> — drag rows to reorder; controls higher in the list render on top.</li>
  <li>Click a row to select the corresponding control on the canvas.</li>
</ul>
""",
    ),
    (
        "Asset Library",
        """
<h2>Asset Library</h2>

<h3>Importing Assets</h3>
<ul>
  <li><b>Import Asset</b> — choose any PNG, JPG, WEBP, TTF, or OTF file from disk. A copy
      is placed in <code>.juce_theme_studio/assets/</code>.</li>
  <li><b>From Project</b> — scan the JUCE project for images (<code>Resources/</code>,
      <code>BinaryData/</code>, etc.) and copy all unimported ones to the asset library.</li>
  <li><b>Import Sprite Sheet</b> — opens the Sprite Import dialog (see below).</li>
</ul>
<p>When opening a project that contains images not yet imported, a prompt appears offering
to copy them all automatically.</p>

<h3>Assigning Assets to Controls</h3>
<p>There are three ways to link an asset to a control:</p>
<ol>
  <li><b>Click-to-assign</b> — click an asset in the library, then click a control on
      the canvas. A confirmation dialog appears.</li>
  <li><b>Drag-and-drop to canvas empty area</b> — creates a new control of the selected
      palette type at the drop position, already linked to the asset.</li>
  <li><b>Drag-and-drop onto existing control</b> — shows a "Link Asset to Control"
      dialog for confirmation.</li>
</ol>
<p>Press <b>Esc</b> to cancel a pending click-to-assign.</p>

<h3>Import Sprite Sheet</h3>
<p>The Sprite Import dialog configures how a sprite strip or grid is sliced:</p>
<ul>
  <li><b>Layout</b> — Horizontal Strip, Vertical Strip, or Grid.</li>
  <li><b>Frame count</b> — number of animation frames.</li>
  <li><b>Frame width / height</b> — dimensions of a single frame.</li>
  <li><b>Slice all frames into library</b> — saves each frame as a separate asset
      (<code>name_frame_00.png</code>, <code>name_frame_01.png</code>, …). Useful for
      LED states and icon variations.</li>
  <li><b>Keep full sprite sheet</b> — retains the master strip/grid asset for
      strip-based controls (knobs, meters).</li>
</ul>

<h3>Set Background</h3>
<p>Select an asset in the library and click <b>Set Background</b> to use it as the
screen's background image.</p>

<h3>Delete Asset</h3>
<p>Select an asset and click <b>Delete Asset</b>. If the asset is in use, a list of
affected controls is shown before confirming deletion.</p>
""",
    ),
    (
        "Properties Panel",
        """
<h2>Properties Panel</h2>

<p>The <b>Properties</b> panel (right side) shows fields for the currently selected control.
Changes take effect immediately and are undoable.</p>

<h3>Geometry</h3>
<ul>
  <li><b>X</b>, <b>Y</b> — position from the top-left corner of the canvas, in pixels.
      Matches <code>juce::Component::setBounds(x, y, w, h)</code>.</li>
  <li><b>W</b>, <b>H</b> — width and height in pixels.</li>
</ul>
<p>Edit values numerically and press Enter or Tab to commit. All geometry edits are undoable.</p>

<h3>Sprite Sheet</h3>
<p>Visible when the control has a sprite sheet asset linked:</p>
<ul>
  <li><b>Frame count</b> — total number of animation frames in the strip/grid.</li>
  <li><b>Frame width / height</b> — size of one frame in pixels.</li>
  <li><b>Layout</b> — Horizontal Strip, Vertical Strip, or Grid.</li>
  <li><b>Columns</b> (Grid only) — number of columns in the grid.</li>
  <li><b>Preview state</b> — choose Normal / Hover / Active / Disabled to preview
      which frame is shown.</li>
  <li><b>Value</b> (0.0–1.0) — simulate the knob/slider/meter position for previewing
      the corresponding sprite frame.</li>
</ul>

<h3>JUCE Mapping</h3>
<p>Links the visual control to a C++ component in your JUCE project:</p>
<ul>
  <li><b>JUCE class</b> — the C++ type, e.g. <code>juce::Slider</code>,
      <code>juce::TextButton</code>.</li>
  <li><b>C++ variable</b> — the member variable name, e.g. <code>gainSlider</code>.</li>
  <li><b>Parameter ID</b> — the APVTS parameter string, e.g. <code>"gain"</code>.
      Autocomplete is populated from scanned <code>AudioProcessorValueTreeState</code>
      attachments.</li>
  <li><b>Screen name</b> — which screen this control belongs to (auto-set).</li>
</ul>
<p>These fields are used during export to generate correctly typed C++ accessors and to
position your existing components via <code>applyScreenLayout()</code>.</p>
""",
    ),
    (
        "Export",
        """
<h2>Export</h2>

<h3>Running an Export</h3>
<ol>
  <li>Click <b>Export</b> in the toolbar (or <b>File → Export…</b>).</li>
  <li>The <b>Export Preview</b> dialog shows what will be written and lists any validation
      warnings or errors.</li>
  <li>Click <b>Export</b> in the dialog to write files to
      <code>.juce_theme_studio/exports/</code>.</li>
  <li>Previous exports are automatically backed up to
      <code>.juce_theme_studio/backups/</code>.</li>
</ol>

<h3>Managed Apply</h3>
<p><b>Apply to Project</b> copies generated runtime files into
<code>Source/ThemeStudio/</code> and records a reversible transaction under
<code>.juce_theme_studio/applies/</code>.</p>
<p>The preview lists creates, replacements, unchanged files, and conflicts before
anything in the project is modified. Use <b>Revert Last Apply</b> to restore the
latest completed transaction.</p>

<h3>Generated Files</h3>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse">
  <tr><th>File</th><th>Description</th></tr>
  <tr><td><code>ThemeLayout.json</code></td>
      <td>Complete layout, sprite config, and palette data. Loaded at runtime by the
          generated components.</td></tr>
  <tr><td><code>ThemeAssets.h/cpp</code></td>
      <td>Loads exported images and slices sprite frames using JUCE's
          <code>ImageCache</code>.</td></tr>
  <tr><td><code>ThemeLookAndFeel.h/cpp</code></td>
      <td>Custom <code>LookAndFeel</code> that draws sprite-based knobs, buttons, and
          meters, and applies the exported palette colors.</td></tr>
  <tr><td><code>GeneratedThemeComponents.h/cpp</code></td>
      <td><code>ThemeScreenComponent</code> renders a complete screen from
          <code>ThemeLayout.json</code>; <code>applyScreenLayout()</code> positions your
          own components.</td></tr>
  <tr><td><code>README-INTEGRATION.md</code></td>
      <td>CMake snippet and usage example for integrating the generated files.</td></tr>
  <tr><td><code>assets/</code></td>
      <td>Copied image files referenced by the generated C++.</td></tr>
</table>

<h3>Export Settings Panel</h3>
<p>Configured in the <b>Export</b> panel (right side):</p>
<ul>
  <li><b>Export JSON</b> — include <code>ThemeLayout.json</code>.</li>
  <li><b>Export C++</b> — include the four generated C++ files.</li>
  <li><b>Copy assets</b> — copy image files to the export directory.</li>
  <li><b>Namespace</b> — C++ namespace wrapping the generated code
      (set globally in <b>Settings</b>).</li>
  <li><b>Output subdirectory</b> — subdirectory inside <code>exports/</code>.</li>
</ul>

<h3>Validation</h3>
<p>Before exporting, check the <b>Validation</b> tab in the Log Panel (bottom).
Errors must be resolved; warnings can be exported past with confirmation.</p>
""",
    ),
    (
        "Layout Tools",
        """
<h2>Layout Tools</h2>

<h3>Alignment (Layout Menu)</h3>
<p>Select two or more controls, then use <b>Layout → Align</b>:</p>
<ul>
  <li><b>Align Left</b> — align left edges to the leftmost selected control.</li>
  <li><b>Align H Center</b> — align horizontal centers.</li>
  <li><b>Align Right</b> — align right edges to the rightmost selected control.</li>
  <li><b>Align Top</b> — align top edges to the topmost selected control.</li>
  <li><b>Align V Center</b> — align vertical centers.</li>
  <li><b>Align Bottom</b> — align bottom edges to the bottommost selected control.</li>
  <li><b>Align to Canvas H Center</b> — center selected controls horizontally on the canvas.</li>
  <li><b>Align to Canvas V Center</b> — center selected controls vertically on the canvas.</li>
</ul>

<h3>Distribute (Layout Menu)</h3>
<p>Select three or more controls, then use:</p>
<ul>
  <li><b>Distribute Horizontally</b> — equal spacing between left edges.</li>
  <li><b>Distribute Vertically</b> — equal spacing between top edges.</li>
</ul>

<h3>Smart Snap Guides</h3>
<p>Blue guide lines appear while dragging when a control's edge or center aligns with:</p>
<ul>
  <li>The edge or center of another control on the same screen.</li>
  <li>The canvas edges or center.</li>
</ul>
<p>Snap strength and the grid can be configured in <b>File → Settings…</b></p>

<h3>Nudge</h3>
<p>Select controls and use arrow keys to nudge:</p>
<ul>
  <li><b>Arrow keys</b> — 1 px per press.</li>
  <li><b>Shift + Arrow keys</b> — 8 px per press.</li>
</ul>

<h3>Settings Dialog</h3>
<p>Accessed via <b>File → Settings…</b> or the <b>Settings</b> toolbar button:</p>
<ul>
  <li><b>Grid size</b> — spacing of the background dot grid in pixels.</li>
  <li><b>Snap to grid</b> — toggle grid-snapping during drag.</li>
  <li><b>C++ namespace</b> — wraps all generated code; default is <code>ThemeStudio</code>.</li>
</ul>
""",
    ),
    (
        "JUCE Integration",
        """
<h2>JUCE Integration</h2>

<h3>Code Scanner</h3>
<p>When a project is opened, JUCE Theme Studio scans <code>Source/</code> for:</p>
<ul>
  <li><code>juce::Component</code> subclasses → create one screen per class.</li>
  <li>Member variables of <code>juce::Slider</code>, <code>juce::TextButton</code>, etc.
      → add placeholder controls with JUCE class and variable pre-filled.</li>
  <li><code>AudioProcessorValueTreeState</code> <code>*Attachment</code> constructors →
      extract parameter IDs and link them to the corresponding controls.</li>
  <li>Image file references → offer them in the asset import prompt.</li>
</ul>
<p>The scanner uses three backends (in decreasing precision order):</p>
<ol>
  <li><b>libclang</b> (optional) — full AST parsing via Clang.</li>
  <li><b>tree-sitter-cpp</b> (optional) — fast incremental AST parsing.</li>
  <li><b>Regex fallback</b> — always available; less precise for complex macros.</li>
</ol>
<p>Install optional backends with <code>pip install -e ".[full]"</code>.</p>

<h3>Rescan &amp; Sync</h3>
<ul>
  <li><b>Project → Rescan Project</b> — re-scan all C++ source; add newly found screens
      and mappings.</li>
  <li><b>Project → Sync JUCE Mappings</b> — apply only new control mappings without
      adding new screens.</li>
</ul>

<h3>JUCE Mapping Fields (Properties)</h3>
<p>For each control, set the <b>JUCE class</b>, <b>C++ variable</b>, and optionally a
<b>Parameter ID</b>. The exporter uses these to generate accessor code in
<code>GeneratedThemeComponents.h</code> and to call <code>applyScreenLayout()</code>
with the correct component references.</p>

<h3>Live JUCE Preview</h3>
<p>A native companion app (<code>examples/juce_live_preview/</code>) renders
<code>ThemeLayout.json</code> and reloads automatically on each export.</p>
<ol>
  <li>Build the companion: open <code>examples/juce_live_preview/CMakeLists.txt</code>
      with JUCE installed.</li>
  <li>In the <b>Live Preview</b> panel (right), browse to the built binary.</li>
  <li>Enable <b>Auto-export on edit</b> to update the preview on every change.</li>
  <li>Click <b>Launch Preview</b> to start the companion.</li>
</ol>

<h3>Theme Colors</h3>
<p>Open <b>Project → Theme Colors…</b> to edit the palette:</p>
<ul>
  <li>Background, Surface, Primary, On-Primary, Text, Meter colors.</li>
  <li>Values are embedded in <code>ThemeLayout.json</code> and applied by
      <code>ThemeLookAndFeel</code> at runtime.</li>
  <li>Click <b>Restore Defaults</b> to reset to the built-in palette.</li>
</ul>

<h3>Theme Diff</h3>
<p><b>Project → Theme Diff…</b> compares two versions of the theme manifest. It shows
added, removed, and modified screens, controls, and assets between your current project
and the latest export backup (or any two JSON files you choose).</p>
""",
    ),
    (
        "Git Integration",
        """
<h2>Git Integration</h2>

<h3>Committing Theme Changes</h3>
<p>Click <b>Commit</b> in the toolbar (enabled only when the project is inside a Git
repository) to open the Git Commit dialog:</p>
<ol>
  <li>The dialog lists all changed files under <code>.juce_theme_studio/</code>.</li>
  <li>Click any file to preview its diff.</li>
  <li>Edit the commit message.</li>
  <li>Check the confirmation box and press <b>OK</b> to commit.</li>
</ol>
<p><b>JUCE Theme Studio never commits automatically.</b> A warning is shown if there are
unrelated changes staged in the repository.</p>

<h3>Git Status Tab</h3>
<p>The <b>Git Status</b> tab in the Log Panel (bottom) shows the current status of the
<code>.juce_theme_studio/</code> folder. It updates automatically after Save and Export.</p>

<h3>Theme Diff</h3>
<p>Use <b>Project → Theme Diff…</b> to compare theme manifests before committing, to
verify exactly what changed between two exports or project states.</p>
""",
    ),
    (
        "Keyboard Shortcuts",
        """
<h2>Keyboard Shortcuts</h2>

<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
  <tr><th>Action</th><th>macOS</th><th>Windows / Linux</th></tr>
  <tr><td>Save</td><td>Cmd+S</td><td>Ctrl+S</td></tr>
  <tr><td>Undo</td><td>Cmd+Z</td><td>Ctrl+Z</td></tr>
  <tr><td>Redo</td><td>Cmd+Shift+Z</td><td>Ctrl+Shift+Z</td></tr>
  <tr><td>Copy</td><td>Cmd+C</td><td>Ctrl+C</td></tr>
  <tr><td>Cut</td><td>Cmd+X</td><td>Ctrl+X</td></tr>
  <tr><td>Paste</td><td>Cmd+V</td><td>Ctrl+V</td></tr>
  <tr><td>Duplicate</td><td>Cmd+D</td><td>Ctrl+D</td></tr>
  <tr><td>Delete selected</td><td>Delete / Backspace</td><td>Delete</td></tr>
  <tr><td>Select All</td><td>Cmd+A</td><td>Ctrl+A</td></tr>
  <tr><td>Nudge 1px</td><td>Arrow keys</td><td>Arrow keys</td></tr>
  <tr><td>Nudge 8px</td><td>Shift + Arrow keys</td><td>Shift + Arrow keys</td></tr>
  <tr><td>Cancel asset assign</td><td>Esc</td><td>Esc</td></tr>
  <tr><td>Fit canvas</td><td>(toolbar button)</td><td>(toolbar button)</td></tr>
</table>

<h3>Log Panel Tabs</h3>
<ul>
  <li><b>Log</b> — operation messages and info.</li>
  <li><b>Warnings</b> — validation warnings from the last scan or export.</li>
  <li><b>Git Status</b> — current status of <code>.juce_theme_studio/</code>.</li>
  <li><b>Validation</b> — detailed validation results with error/warning counts.</li>
</ul>
""",
    ),
]


class HelpDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("JUCE Theme Studio — Help")
        self.resize(900, 650)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel("JUCE Theme Studio — User Guide")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        header.setFont(font)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._nav = QListWidget()
        self._nav.setMaximumWidth(200)
        self._nav.setMinimumWidth(160)
        for title, _ in _SECTIONS:
            item = QListWidgetItem(title)
            self._nav.addItem(item)
        self._nav.currentRowChanged.connect(self._on_nav_changed)
        splitter.addWidget(self._nav)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        content_layout.addWidget(self._browser)
        scroll.setWidget(content_widget)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._nav.setCurrentRow(0)

    def _on_nav_changed(self, row: int) -> None:
        if 0 <= row < len(_SECTIONS):
            _, html = _SECTIONS[row]
            self._browser.setHtml(_wrap_html(html))

    def show_section(self, title: str) -> None:
        for i, (t, _) in enumerate(_SECTIONS):
            if t == title:
                self._nav.setCurrentRow(i)
                return


def _wrap_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<style>
body {{ font-family: sans-serif; font-size: 13px; line-height: 1.6; color: #e0e0e0; background: transparent; }}
h2 {{ color: #7eb8f7; border-bottom: 1px solid #444; padding-bottom: 4px; margin-top: 8px; }}
h3 {{ color: #b0d0ff; margin-top: 16px; }}
code, pre {{ background: #2a2a2a; color: #aaffaa; padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 12px; }}
pre {{ display: block; padding: 10px; white-space: pre; }}
table {{ border-color: #555; width: 100%; }}
th {{ background: #2a3a4a; color: #c0d8f0; text-align: left; }}
td, th {{ padding: 6px 10px; }}
ul, ol {{ padding-left: 20px; }}
li {{ margin-bottom: 4px; }}
b {{ color: #ffffff; }}
</style>
</head>
<body>{body}</body>
</html>"""
