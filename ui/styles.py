"""
ui/styles.py
Net Max — Apple macOS Sonoma dark theme.

Design principles
─────────────────
• Colours match macOS Sonoma dark mode exactly (sampled from Activity Monitor,
  System Settings, and Apple Music)
• All font sizes use pt (point), never px — correct at every DPI scale
• Border radii: 20px cards, 12px list rows, 8px controls
• Backgrounds use three strict elevation levels with very low contrast delta
  so surfaces feel layered, not banded
• No fixed heights anywhere — all sizing is content-driven
• QSS handles *global* style rules only; individual widget chrome is painted
  in Python paintEvent() for anti-aliasing correctness
"""

# ─────────────────────────────────────────────────────────────────────────────
#  Palette — sampled from macOS Sonoma dark mode
# ─────────────────────────────────────────────────────────────────────────────
COLORS = {
    # Window & surface hierarchy
    "window":         "#1C1C1E",   # NSColor.windowBackgroundColor dark
    "surface_1":      "#2C2C2E",   # Cards, sidebar — 1-stop above window
    "surface_2":      "#3A3A3C",   # Inputs, nested panels, hover states
    "surface_3":      "#48484A",   # Active / pressed states

    # Borders — extremely subtle, Apple-style
    "border_card":    "#FFFFFF0F", # 6% white — used as card stroke
    "border_control": "#FFFFFF1A", # 10% white — inputs
    "border_focus":   "#0A84FF",   # macOS blue focus ring

    # Text — exact macOS label colours
    "label":          "#FFFFFF",   # Primary label
    "label_2":        "#EBEBF599", # Secondary label (60% white)
    "label_3":        "#EBEBF54D", # Tertiary label (30% white)
    "label_4":        "#EBEBF526", # Quaternary label (15% white)

    # System accent colours (macOS Sonoma defaults)
    "blue":           "#0A84FF",
    "indigo":         "#5E5CE6",
    "purple":         "#BF5AF2",
    "pink":           "#FF375F",
    "red":            "#FF453A",
    "orange":         "#FF9F0A",
    "yellow":         "#FFD60A",
    "green":          "#30D158",
    "teal":           "#40CBE0",
    "mint":           "#63E6E2",
    "cyan":           "#32ADE6",

    # Semantic
    "success":        "#30D158",
    "warning":        "#FF9F0A",
    "error":          "#FF453A",
    "info":           "#0A84FF",

    # Sidebar
    "sidebar_bg":     "#1C1C1E",
    "sidebar_hover":  "#FFFFFF0A",   # 4% white
    "sidebar_active": "#0A84FF1A",   # 10% blue
    "sidebar_active_text": "#0A84FF",

    # Chart colours (distinct, Apple vibrancy)
    "chart_dl":       "#0A84FF",
    "chart_ul":       "#BF5AF2",
    "chart_dl_fill":  (10,  132, 255, 45),
    "chart_ul_fill":  (191,  90, 242, 45),

}

# ─────────────────────────────────────────────────────────────────────────────
#  QSS — global rules only, pt-based fonts throughout
# ─────────────────────────────────────────────────────────────────────────────
DARK_THEME = """
/* ═══════════════════════════════════════════
   RESET & BASE
═══════════════════════════════════════════ */
QWidget {
    color: #FFFFFF;
    font-family: "Segoe UI Variable Display", "Segoe UI", ".AppleSystemUIFont",
                 "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
    border: none;
    outline: none;
}

QMainWindow, QDialog {
    background-color: #1C1C1E;
}

/* ═══════════════════════════════════════════
   SCROLL BARS  — thin macOS overlay style
═══════════════════════════════════════════ */
QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 2px 2px 2px 0;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.18);
    border-radius: 3px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255,255,255,0.28);
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal {
    background: transparent;
    height: 7px;
    margin: 0 2px 2px 2px;
}
QScrollBar::handle:horizontal {
    background: rgba(255,255,255,0.18);
    border-radius: 3px;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(255,255,255,0.28);
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal { width: 0; }

QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}

/* ═══════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════ */
#Sidebar {
    background-color: #1C1C1E;
    border-right: 1px solid rgba(255,255,255,0.06);
    min-width: 230px;
    max-width: 230px;
}

/* ═══════════════════════════════════════════
   SIDEBAR NAV BUTTONS
   NOTE: background/colour is painted in Python set_active()
   QSS only provides the hover rectangle
═══════════════════════════════════════════ */
QPushButton#SidebarBtn {
    background: transparent;
    border: none;
    border-radius: 10px;
    color: rgba(235,235,245,0.6);
    font-size: 10pt;
    font-weight: 400;
    text-align: left;
    padding: 0;
    margin: 2px 10px;
    min-height: 44px;
}
QPushButton#SidebarBtn:hover {
    background: rgba(255,255,255,0.06);
    color: #FFFFFF;
}
QPushButton#SidebarBtn[active="true"] {
    background: rgba(10,132,255,0.08);
    color: #FFFFFF;
    border-radius: 10px;
}

/* ═══════════════════════════════════════════
   CONTENT AREA
═══════════════════════════════════════════ */
#ContentArea {
    background-color: #1C1C1E;
}

/* ═══════════════════════════════════════════
   TABLE  (applications page)
═══════════════════════════════════════════ */
QTableWidget {
    background: #2C2C2E;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    gridline-color: rgba(255,255,255,0.05);
    selection-background-color: rgba(10,132,255,0.20);
    selection-color: #FFFFFF;
    alternate-background-color: rgba(255,255,255,0.02);
    font-size: 10pt;
}
QTableWidget::item {
    padding: 9px 14px;
    border: none;
    color: #FFFFFF;
}
QTableWidget::item:selected {
    background: rgba(10,132,255,0.20);
    color: #FFFFFF;
}
QHeaderView {
    background: transparent;
}
QHeaderView::section {
    background: #2C2C2E;
    color: rgba(235,235,245,0.5);
    padding: 11px 14px;
    border: none;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}
QHeaderView::section:hover {
    color: rgba(235,235,245,0.8);
    background: rgba(255,255,255,0.04);
}

/* ═══════════════════════════════════════════
   INPUTS
═══════════════════════════════════════════ */
QLineEdit {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    color: #FFFFFF;
    padding: 8px 14px;
    font-size: 10pt;
    selection-background-color: rgba(10,132,255,0.4);
}
QLineEdit:focus {
    border: 2px solid #0A84FF;
    padding: 7px 13px;
}
QLineEdit:hover {
    border-color: rgba(255,255,255,0.18);
}

/* ═══════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════ */
QPushButton {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    color: #FFFFFF;
    padding: 8px 18px;
    font-size: 10pt;
    font-weight: 500;
}
QPushButton:hover {
    background: rgba(255,255,255,0.13);
    border-color: rgba(255,255,255,0.18);
}
QPushButton:pressed {
    background: rgba(255,255,255,0.05);
}

QPushButton#PrimaryBtn {
    background: #0A84FF;
    border: none;
    color: #FFFFFF;
    font-weight: 600;
    border-radius: 10px;
}
QPushButton#PrimaryBtn:hover {
    background: #409CFF;
}
QPushButton#PrimaryBtn:pressed {
    background: #0071E3;
}

QPushButton#DangerBtn {
    background: rgba(255,69,58,0.12);
    border: 1px solid rgba(255,69,58,0.30);
    color: #FF453A;
    border-radius: 10px;
}
QPushButton#DangerBtn:hover {
    background: rgba(255,69,58,0.20);
}

QPushButton#SmallBtn {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    color: rgba(235,235,245,0.6);
    padding: 5px 14px;
    font-size: 9pt;
    font-weight: 500;
}
QPushButton#SmallBtn:hover {
    color: #FFFFFF;
    background: rgba(255,255,255,0.11);
}

/* ═══════════════════════════════════════════
   COMBO BOX
═══════════════════════════════════════════ */
QComboBox {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    color: #FFFFFF;
    padding: 7px 14px;
    font-size: 10pt;
    min-width: 110px;
}
QComboBox:hover { border-color: rgba(255,255,255,0.18); }
QComboBox:focus { border: 2px solid #0A84FF; padding: 6px 13px; }
QComboBox QAbstractItemView {
    background: #3A3A3C;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    selection-background-color: rgba(10,132,255,0.25);
    color: #FFFFFF;
    padding: 4px;
    font-size: 10pt;
}
QComboBox::drop-down { border: none; padding-right: 12px; }

/* ═══════════════════════════════════════════
   SPINBOX
═══════════════════════════════════════════ */
QSpinBox, QDoubleSpinBox {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    color: #FFFFFF;
    padding: 7px 10px;
    font-size: 10pt;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #0A84FF;
    padding: 6px 9px;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: rgba(255,255,255,0.08);
    border: none;
    width: 20px;
    border-radius: 4px;
    margin: 2px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: rgba(255,255,255,0.15);
}

/* ═══════════════════════════════════════════
   CHECKBOX
═══════════════════════════════════════════ */
QCheckBox {
    color: #FFFFFF;
    spacing: 10px;
    font-size: 10pt;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1.5px solid rgba(255,255,255,0.25);
    background: rgba(255,255,255,0.06);
}
QCheckBox::indicator:checked {
    background: #0A84FF;
    border-color: #0A84FF;
}
QCheckBox::indicator:hover {
    border-color: rgba(255,255,255,0.40);
}

/* ═══════════════════════════════════════════
   DIVIDERS
═══════════════════════════════════════════ */
QFrame[frameShape="4"] {
    border: none;
    background: rgba(255,255,255,0.06);
    max-height: 1px;
    min-height: 1px;
}
QFrame[frameShape="5"] {
    border: none;
    background: rgba(255,255,255,0.06);
    max-width: 1px;
    min-width: 1px;
}

/* ═══════════════════════════════════════════
   STATUS BAR
═══════════════════════════════════════════ */
QStatusBar {
    background: #1C1C1E;
    color: rgba(235,235,245,0.4);
    border-top: 1px solid rgba(255,255,255,0.06);
    font-size: 8pt;
}
QStatusBar::item { border: none; }

/* ═══════════════════════════════════════════
   TOOLTIP
═══════════════════════════════════════════ */
QToolTip {
    background: #3A3A3C;
    color: #FFFFFF;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 9pt;
}

/* ═══════════════════════════════════════════
   TABS
═══════════════════════════════════════════ */
QTabWidget::pane {
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    background: #2C2C2E;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: rgba(235,235,245,0.5);
    padding: 10px 24px;
    border: none;
    font-size: 10pt;
    font-weight: 500;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: #0A84FF;
    border-bottom: 2px solid #0A84FF;
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    color: rgba(235,235,245,0.8);
}
QTabWidget { background: transparent; }

/* ═══════════════════════════════════════════
   MESSAGE BOX
═══════════════════════════════════════════ */
QMessageBox {
    background: #2C2C2E;
}
QMessageBox QLabel {
    color: #FFFFFF;
    font-size: 10pt;
}
"""
