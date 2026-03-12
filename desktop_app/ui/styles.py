"""
desktop_app/ui/styles.py — Application-wide dark theme stylesheet.
Engineering/sim-racing tool aesthetic. Clean, dark, minimal.
"""

# Dark engineering tool color palette
COLORS = {
    "bg_dark":       "#1a1a1a",
    "bg_panel":      "#222222",
    "bg_widget":     "#2a2a2a",
    "bg_hover":      "#333333",
    "bg_selected":   "#1e3a5f",
    "border":        "#3a3a3a",
    "border_focus":  "#4a90d9",
    "text_primary":  "#e8e8e8",
    "text_secondary":"#999999",
    "text_dim":      "#666666",
    "accent_blue":   "#4a90d9",
    "accent_green":  "#4caf50",
    "accent_yellow": "#ffb300",
    "accent_red":    "#ef5350",
    "accent_orange": "#ff6f00",
    "accent_purple": "#9c4dcc",
    "sidebar_width": "200px",
}

DARK_STYLESHEET = f"""
/* ============================================================
   Global
   ============================================================ */
QMainWindow, QWidget {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
    font-family: "Segoe UI", "Consolas", sans-serif;
    font-size: 13px;
}}

QFrame {{
    background-color: transparent;
    border: none;
}}

/* ============================================================
   Sidebar / Navigation
   ============================================================ */
QListWidget#nav_list {{
    background-color: {COLORS['bg_panel']};
    border: none;
    border-right: 1px solid {COLORS['border']};
    outline: none;
    font-size: 13px;
    padding: 4px 0;
}}

QListWidget#nav_list::item {{
    color: {COLORS['text_secondary']};
    padding: 10px 16px;
    border-left: 3px solid transparent;
}}

QListWidget#nav_list::item:hover {{
    color: {COLORS['text_primary']};
    background-color: {COLORS['bg_hover']};
    border-left: 3px solid {COLORS['accent_blue']};
}}

QListWidget#nav_list::item:selected {{
    color: {COLORS['text_primary']};
    background-color: {COLORS['bg_selected']};
    border-left: 3px solid {COLORS['accent_blue']};
}}

/* ============================================================
   Section headers
   ============================================================ */
QLabel#section_header {{
    color: {COLORS['text_dim']};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    padding: 12px 16px 4px 16px;
    text-transform: uppercase;
}}

/* ============================================================
   Page titles
   ============================================================ */
QLabel#page_title {{
    color: {COLORS['text_primary']};
    font-size: 18px;
    font-weight: 600;
    padding: 0;
    margin: 0;
}}

QLabel#page_subtitle {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
}}

/* ============================================================
   Group boxes (panels)
   ============================================================ */
QGroupBox {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    margin-top: 14px;
    padding: 8px 10px;
    font-size: 12px;
    font-weight: 600;
    color: {COLORS['text_secondary']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    color: {COLORS['text_secondary']};
    letter-spacing: 0.5px;
}}

/* ============================================================
   Buttons
   ============================================================ */
QPushButton {{
    background-color: {COLORS['bg_widget']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    padding: 6px 14px;
    min-height: 26px;
    font-size: 13px;
}}

QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['accent_blue']};
    color: {COLORS['text_primary']};
}}

QPushButton:pressed {{
    background-color: {COLORS['bg_selected']};
}}

QPushButton:disabled {{
    color: {COLORS['text_dim']};
    border-color: {COLORS['bg_widget']};
}}

QPushButton#btn_primary {{
    background-color: {COLORS['accent_blue']};
    border-color: {COLORS['accent_blue']};
    color: white;
    font-weight: 600;
}}

QPushButton#btn_primary:hover {{
    background-color: #5aa0e8;
}}

QPushButton#btn_danger {{
    background-color: {COLORS['accent_red']};
    border-color: {COLORS['accent_red']};
    color: white;
    font-weight: 700;
    font-size: 14px;
}}

QPushButton#btn_danger:hover {{
    background-color: #ff6b6b;
}}

QPushButton#btn_success {{
    background-color: {COLORS['accent_green']};
    border-color: {COLORS['accent_green']};
    color: white;
    font-weight: 600;
}}

QPushButton#btn_warning {{
    background-color: {COLORS['accent_yellow']};
    border-color: {COLORS['accent_yellow']};
    color: #111;
    font-weight: 600;
}}

/* ============================================================
   Sliders
   ============================================================ */
QSlider::groove:horizontal {{
    height: 4px;
    background-color: {COLORS['border']};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {COLORS['accent_blue']};
    border: none;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::sub-page:horizontal {{
    background-color: {COLORS['accent_blue']};
    border-radius: 2px;
}}

QSlider::groove:horizontal:disabled {{
    background-color: {COLORS['bg_widget']};
}}

/* ============================================================
   Inputs
   ============================================================ */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_widget']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 24px;
    selection-background-color: {COLORS['accent_blue']};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLORS['border_focus']};
}}

QComboBox {{
    background-color: {COLORS['bg_widget']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 24px;
}}

QComboBox:hover {{
    border-color: {COLORS['accent_blue']};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_panel']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['bg_selected']};
    outline: none;
}}

/* ============================================================
   Checkboxes
   ============================================================ */
QCheckBox {{
    color: {COLORS['text_primary']};
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {COLORS['border']};
    background-color: {COLORS['bg_widget']};
    border-radius: 2px;
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS['accent_blue']};
    border-color: {COLORS['accent_blue']};
}}

/* ============================================================
   Scroll bars
   ============================================================ */
QScrollBar:vertical {{
    background-color: {COLORS['bg_panel']};
    width: 10px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border']};
    min-height: 20px;
    border-radius: 4px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['text_dim']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {COLORS['bg_panel']};
    height: 10px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS['border']};
    min-width: 20px;
    border-radius: 4px;
    margin: 2px;
}}

/* ============================================================
   Tables
   ============================================================ */
QTableWidget {{
    background-color: {COLORS['bg_panel']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    gridline-color: {COLORS['border']};
    selection-background-color: {COLORS['bg_selected']};
    outline: none;
}}

QTableWidget::item {{
    padding: 4px 8px;
}}

QHeaderView::section {{
    background-color: {COLORS['bg_widget']};
    color: {COLORS['text_secondary']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 6px 8px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

/* ============================================================
   Text edit / log viewer
   ============================================================ */
QTextEdit, QPlainTextEdit {{
    background-color: {COLORS['bg_panel']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    selection-background-color: {COLORS['bg_selected']};
}}

/* ============================================================
   Tab widget
   ============================================================ */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    background-color: {COLORS['bg_panel']};
}}

QTabBar::tab {{
    background-color: {COLORS['bg_widget']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    border-radius: 3px 3px 0 0;
}}

QTabBar::tab:selected {{
    background-color: {COLORS['bg_panel']};
    color: {COLORS['text_primary']};
    border-bottom: 1px solid {COLORS['bg_panel']};
}}

QTabBar::tab:hover {{
    color: {COLORS['text_primary']};
    background-color: {COLORS['bg_hover']};
}}

/* ============================================================
   Status indicators (custom labels)
   ============================================================ */
QLabel#status_ok {{
    color: {COLORS['accent_green']};
    font-weight: 600;
}}

QLabel#status_warn {{
    color: {COLORS['accent_yellow']};
    font-weight: 600;
}}

QLabel#status_error {{
    color: {COLORS['accent_red']};
    font-weight: 700;
}}

QLabel#status_inactive {{
    color: {COLORS['text_dim']};
}}

QLabel#value_display {{
    color: {COLORS['accent_blue']};
    font-family: "Consolas", monospace;
    font-size: 16px;
    font-weight: 600;
}}

QLabel#value_large {{
    color: {COLORS['text_primary']};
    font-family: "Consolas", monospace;
    font-size: 24px;
    font-weight: 700;
}}

/* ============================================================
   Separator
   ============================================================ */
QFrame[frameShape="4"],  /* HLine */
QFrame[frameShape="5"] {{  /* VLine */
    color: {COLORS['border']};
    background-color: {COLORS['border']};
}}

/* ============================================================
   Tooltip
   ============================================================ */
QToolTip {{
    background-color: {COLORS['bg_panel']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    padding: 4px 8px;
    border-radius: 3px;
    font-size: 12px;
}}

/* ============================================================
   Splitter
   ============================================================ */
QSplitter::handle {{
    background-color: {COLORS['border']};
    width: 1px;
    height: 1px;
}}
"""
