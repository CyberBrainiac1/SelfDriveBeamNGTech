"""
desktop_app/ui/styles.py
Engineering / sim-racing dashboard aesthetic.
Dense, readable, panelled. No bubbles, no mobile styling.
"""

COLORS = {
    "bg_dark":       "#181818",
    "bg_panel":      "#202020",
    "bg_card":       "#242424",
    "bg_widget":     "#2c2c2c",
    "bg_hover":      "#303030",
    "bg_selected":   "#0f2a42",
    "border":        "#333333",
    "border_bright": "#444444",
    "border_focus":  "#4a90d9",
    "text_primary":  "#dcdcdc",
    "text_secondary":"#888888",
    "text_dim":      "#4a4a4a",
    "accent_blue":   "#4a90d9",
    "accent_green":  "#3cb870",
    "accent_yellow": "#e8a020",
    "accent_red":    "#d94040",
    "accent_orange": "#d97020",
    "accent_cyan":   "#38b8c8",
}

DARK_STYLESHEET = f"""
/* ── Base ─────────────────────────────────────────────────────── */
QMainWindow, QWidget {{
    background: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 12px;
}}
QFrame {{ background: transparent; border: none; }}

/* ── Sidebar nav ──────────────────────────────────────────────── */
QListWidget#nav_list {{
    background: {COLORS['bg_panel']};
    border: none; outline: none;
    padding: 2px 0;
}}
QListWidget#nav_list::item {{
    color: {COLORS['text_secondary']};
    padding: 0 4px 0 0;
    border-left: 2px solid transparent;
    min-height: 30px;
}}
QListWidget#nav_list::item:hover {{
    color: {COLORS['text_primary']};
    background: {COLORS['bg_hover']};
    border-left: 2px solid {COLORS['border_bright']};
}}
QListWidget#nav_list::item:selected {{
    color: {COLORS['text_primary']};
    background: {COLORS['bg_selected']};
    border-left: 2px solid {COLORS['accent_blue']};
}}

/* ── Group boxes — engineering panel style ────────────────────── */
QGroupBox {{
    background: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-left: 3px solid {COLORS['accent_blue']};
    border-radius: 0px;
    margin-top: 16px;
    padding: 4px 6px 6px 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    color: {COLORS['text_dim']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 1px 6px;
    color: {COLORS['text_secondary']};
    background: {COLORS['bg_card']};
    letter-spacing: 1.2px;
}}

/* Accent variants for group boxes */
QGroupBox[accent="green"] {{ border-left-color: {COLORS['accent_green']}; }}
QGroupBox[accent="red"]   {{ border-left-color: {COLORS['accent_red']};   }}
QGroupBox[accent="yellow"]{{ border-left-color: {COLORS['accent_yellow']};}}
QGroupBox[accent="cyan"]  {{ border-left-color: {COLORS['accent_cyan']};  }}

/* ── Buttons ──────────────────────────────────────────────────── */
QPushButton {{
    background: {COLORS['bg_widget']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 2px;
    padding: 3px 10px;
    min-height: 22px;
    font-size: 12px;
}}
QPushButton:hover  {{ background: {COLORS['bg_hover']}; border-color: {COLORS['border_bright']}; }}
QPushButton:pressed {{ background: {COLORS['bg_selected']}; }}
QPushButton:disabled {{ color: {COLORS['text_dim']}; border-color: {COLORS['bg_widget']}; }}

QPushButton#btn_primary {{
    background: {COLORS['accent_blue']}; border-color: {COLORS['accent_blue']};
    color: #fff; font-weight: 600;
}}
QPushButton#btn_primary:hover {{ background: #5ba4e8; }}

QPushButton#btn_danger {{
    background: {COLORS['accent_red']}; border-color: {COLORS['accent_red']};
    color: #fff; font-weight: 700; font-size: 13px;
}}
QPushButton#btn_danger:hover {{ background: #e85555; }}

QPushButton#btn_success {{
    background: {COLORS['accent_green']}; border-color: {COLORS['accent_green']};
    color: #fff; font-weight: 600;
}}
QPushButton#btn_success:hover {{ background: #4dd080; }}

QPushButton#btn_warning {{
    background: {COLORS['accent_yellow']}; border-color: {COLORS['accent_yellow']};
    color: #111; font-weight: 600;
}}
QPushButton#btn_tool {{
    background: {COLORS['bg_panel']}; border-color: {COLORS['border']};
    color: {COLORS['text_secondary']}; padding: 2px 8px; font-size: 11px;
}}
QPushButton#btn_tool:hover {{ color: {COLORS['text_primary']}; border-color: {COLORS['accent_blue']}; }}

/* ── Sliders ──────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 3px; background: {COLORS['border']}; border-radius: 1px;
}}
QSlider::sub-page:horizontal {{
    background: {COLORS['accent_blue']}; border-radius: 1px;
}}
QSlider::handle:horizontal {{
    background: {COLORS['accent_blue']}; border: none;
    width: 11px; height: 11px; margin: -4px 0; border-radius: 6px;
}}
QSlider::groove:horizontal:disabled {{ background: {COLORS['bg_widget']}; }}
QSlider::handle:horizontal:disabled {{ background: {COLORS['border']}; }}

/* ── Inputs ───────────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {COLORS['bg_widget']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 2px;
    padding: 2px 6px;
    min-height: 20px;
    selection-background-color: {COLORS['bg_selected']};
    font-family: "Consolas", monospace;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLORS['border_focus']};
}}
QLineEdit[readOnly="true"] {{
    color: {COLORS['text_secondary']}; background: {COLORS['bg_panel']};
}}

/* ── Combo box ────────────────────────────────────────────────── */
QComboBox {{
    background: {COLORS['bg_widget']}; color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']}; border-radius: 2px;
    padding: 2px 6px; min-height: 20px;
}}
QComboBox:hover  {{ border-color: {COLORS['border_bright']}; }}
QComboBox:focus  {{ border-color: {COLORS['border_focus']};  }}
QComboBox::drop-down {{ border: none; padding-right: 6px; }}
QComboBox QAbstractItemView {{
    background: {COLORS['bg_panel']}; color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['bg_selected']};
    outline: none;
}}

/* ── Checkbox ─────────────────────────────────────────────────── */
QCheckBox {{ color: {COLORS['text_primary']}; spacing: 5px; }}
QCheckBox::indicator {{
    width: 12px; height: 12px;
    border: 1px solid {COLORS['border_bright']};
    background: {COLORS['bg_widget']}; border-radius: 1px;
}}
QCheckBox::indicator:checked {{
    background: {COLORS['accent_blue']}; border-color: {COLORS['accent_blue']};
}}

/* ── Scrollbars ───────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {COLORS['bg_panel']}; width: 8px; border: none;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']}; min-height: 20px; border-radius: 3px; margin: 1px;
}}
QScrollBar::handle:vertical:hover {{ background: {COLORS['border_bright']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {COLORS['bg_panel']}; height: 8px; border: none;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS['border']}; min-width: 20px; border-radius: 3px; margin: 1px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Tab widget ───────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']}; background: {COLORS['bg_card']};
    border-top: none;
}}
QTabBar::tab {{
    background: {COLORS['bg_panel']}; color: {COLORS['text_dim']};
    border: 1px solid {COLORS['border']}; border-bottom: none;
    padding: 3px 12px; margin-right: 1px; border-radius: 0;
    font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
}}
QTabBar::tab:selected {{
    background: {COLORS['bg_card']}; color: {COLORS['text_primary']};
    border-top: 2px solid {COLORS['accent_blue']};
}}
QTabBar::tab:hover:!selected {{ color: {COLORS['text_secondary']}; background: {COLORS['bg_hover']}; }}

/* ── Text/log views ───────────────────────────────────────────── */
QTextEdit, QPlainTextEdit {{
    background: {COLORS['bg_panel']}; color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']}; border-radius: 0px;
    font-family: "Consolas", monospace; font-size: 11px;
    selection-background-color: {COLORS['bg_selected']};
}}

/* ── Tables ───────────────────────────────────────────────────── */
QTableWidget {{
    background: {COLORS['bg_card']}; color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']}; gridline-color: {COLORS['border']};
    selection-background-color: {COLORS['bg_selected']};
    outline: none;
}}
QTableWidget::item {{ padding: 3px 6px; }}
QHeaderView::section {{
    background: {COLORS['bg_panel']}; color: {COLORS['text_secondary']};
    border: none; border-bottom: 1px solid {COLORS['border']};
    border-right: 1px solid {COLORS['border']};
    padding: 4px 6px; font-size: 10px; font-weight: 700;
    letter-spacing: 0.8px;
}}

/* ── Progress bar ─────────────────────────────────────────────── */
QProgressBar {{
    background: {COLORS['bg_widget']}; border: 1px solid {COLORS['border']};
    border-radius: 0px; text-align: center; color: {COLORS['text_secondary']};
    font-size: 10px; font-family: Consolas; max-height: 14px;
}}
QProgressBar::chunk {{ background: {COLORS['accent_blue']}; }}

/* ── Splitter ─────────────────────────────────────────────────── */
QSplitter::handle {{ background: {COLORS['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* ── Tooltip ──────────────────────────────────────────────────── */
QToolTip {{
    background: {COLORS['bg_panel']}; color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border_bright']}; padding: 3px 7px;
    font-size: 11px;
}}

/* ── List widget (non-nav) ────────────────────────────────────── */
QListWidget {{
    background: {COLORS['bg_card']}; color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']}; outline: none;
}}
QListWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {COLORS['border']}; }}
QListWidget::item:selected {{ background: {COLORS['bg_selected']}; color: {COLORS['text_primary']}; }}
QListWidget::item:hover {{ background: {COLORS['bg_hover']}; }}

/* ── Scroll area ──────────────────────────────────────────────── */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
"""
