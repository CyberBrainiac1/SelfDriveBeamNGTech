"""
desktop_app/ui/styles.py — Dark engineering theme. Minimal stylesheet.
"""

COLORS = {
    "bg_dark":       "#1a1a1a",
    "bg_panel":      "#222222",
    "bg_widget":     "#2a2a2a",
    "bg_hover":      "#303030",
    "bg_selected":   "#1b3350",
    "border":        "#353535",
    "border_focus":  "#4a90d9",
    "text_primary":  "#e6e6e6",
    "text_secondary":"#909090",
    "text_dim":      "#555555",
    "accent_blue":   "#4a90d9",
    "accent_green":  "#4caf50",
    "accent_yellow": "#ffb300",
    "accent_red":    "#ef5350",
    "accent_orange": "#ff6f00",
}

DARK_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
    font-family: "Segoe UI", "Consolas", sans-serif;
    font-size: 13px;
}}

/* Sidebar nav */
QListWidget#nav_list {{
    background: {COLORS['bg_panel']};
    border: none;
    outline: none;
}}
QListWidget#nav_list::item {{
    color: {COLORS['text_secondary']};
    padding: 0 0 0 4px;
    border-left: 3px solid transparent;
}}
QListWidget#nav_list::item:hover {{
    color: {COLORS['text_primary']};
    background: {COLORS['bg_hover']};
    border-left-color: {COLORS['accent_blue']};
}}
QListWidget#nav_list::item:selected {{
    color: {COLORS['text_primary']};
    background: {COLORS['bg_selected']};
    border-left-color: {COLORS['accent_blue']};
}}

/* Buttons */
QPushButton {{
    background: {COLORS['bg_widget']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    padding: 5px 12px;
    min-height: 24px;
}}
QPushButton:hover {{ background: {COLORS['bg_hover']}; border-color: {COLORS['accent_blue']}; }}
QPushButton:pressed {{ background: {COLORS['bg_selected']}; }}
QPushButton:disabled {{ color: {COLORS['text_dim']}; }}

QPushButton#btn_primary {{
    background: {COLORS['accent_blue']}; border-color: {COLORS['accent_blue']};
    color: #fff; font-weight: 600;
}}
QPushButton#btn_primary:hover {{ background: #5aa0e8; }}

QPushButton#btn_danger {{
    background: {COLORS['accent_red']}; border-color: {COLORS['accent_red']};
    color: #fff; font-weight: 700;
}}
QPushButton#btn_danger:hover {{ background: #f46b69; }}

QPushButton#btn_success {{
    background: {COLORS['accent_green']}; border-color: {COLORS['accent_green']};
    color: #fff; font-weight: 600;
}}
QPushButton#btn_warning {{
    background: {COLORS['accent_yellow']}; border-color: {COLORS['accent_yellow']};
    color: #111; font-weight: 600;
}}

/* Sliders */
QSlider::groove:horizontal {{ height: 4px; background: {COLORS['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {COLORS['accent_blue']}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {COLORS['accent_blue']}; border: none;
    width: 13px; height: 13px; margin: -5px 0; border-radius: 7px;
}}

/* Inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {COLORS['bg_widget']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    padding: 3px 7px;
    min-height: 22px;
    selection-background-color: {COLORS['accent_blue']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {COLORS['border_focus']};
}}
QComboBox::drop-down {{ border: none; padding-right: 6px; }}
QComboBox QAbstractItemView {{
    background: {COLORS['bg_panel']}; color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['bg_selected']};
    outline: none;
}}

/* Checkbox */
QCheckBox {{ color: {COLORS['text_primary']}; spacing: 6px; }}
QCheckBox::indicator {{
    width: 13px; height: 13px;
    border: 1px solid {COLORS['border']}; background: {COLORS['bg_widget']}; border-radius: 2px;
}}
QCheckBox::indicator:checked {{ background: {COLORS['accent_blue']}; border-color: {COLORS['accent_blue']}; }}

/* Scrollbars */
QScrollBar:vertical {{
    background: {COLORS['bg_panel']}; width: 9px; border: none;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']}; min-height: 20px; border-radius: 4px; margin: 2px;
}}
QScrollBar::handle:vertical:hover {{ background: {COLORS['text_dim']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* Text / log */
QTextEdit, QPlainTextEdit {{
    background: {COLORS['bg_panel']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    font-family: Consolas, monospace;
    font-size: 12px;
    selection-background-color: {COLORS['bg_selected']};
}}

/* Tab widget */
QTabWidget::pane {{ border: 1px solid {COLORS['border']}; background: {COLORS['bg_panel']}; }}
QTabBar::tab {{
    background: {COLORS['bg_widget']}; color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']}; border-bottom: none;
    padding: 5px 12px; margin-right: 2px; border-radius: 3px 3px 0 0;
}}
QTabBar::tab:selected {{
    background: {COLORS['bg_panel']}; color: {COLORS['text_primary']};
}}
QTabBar::tab:hover {{ color: {COLORS['text_primary']}; background: {COLORS['bg_hover']}; }}

/* Progress bar */
QProgressBar {{
    background: {COLORS['bg_widget']}; border: 1px solid {COLORS['border']};
    border-radius: 3px; text-align: center; color: {COLORS['text_primary']};
}}
QProgressBar::chunk {{ background: {COLORS['accent_blue']}; border-radius: 2px; }}

/* Tooltip */
QToolTip {{
    background: {COLORS['bg_panel']}; color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']}; padding: 4px 8px;
    border-radius: 3px; font-size: 12px;
}}

/* FormLayout labels (right-align in forms) */
QLabel {{ background: transparent; }}
"""
