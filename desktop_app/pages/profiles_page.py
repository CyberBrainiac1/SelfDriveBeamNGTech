"""
desktop_app/pages/profiles_page.py — User profile management page.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QListWidget, QListWidgetItem, QLineEdit, QTextEdit,
    QFileDialog, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS


class ProfilesPage(BasePage):
    def __init__(self, **kwargs):
        self._profiles = kwargs.pop("profiles", None)
        super().__init__(
            title="Profiles",
            subtitle="Manage named setting profiles for different operating modes",
            **kwargs
        )
        self._build_content()

    def _build_content(self):
        main_h = QHBoxLayout()
        main_h.setSpacing(16)
        self.content_layout.addLayout(main_h)
        self.content_layout.addStretch()

        # ---- Profile list ----
        left = QVBoxLayout()
        list_group = QGroupBox("PROFILES")
        list_layout = QVBoxLayout(list_group)

        self._profile_list = QListWidget()
        self._profile_list.setMinimumWidth(200)
        self._profile_list.currentRowChanged.connect(self._on_profile_selected)
        list_layout.addWidget(self._profile_list)

        btn_refresh = QPushButton("Refresh List")
        btn_refresh.clicked.connect(self._load_list)
        list_layout.addWidget(btn_refresh)
        left.addWidget(list_group)
        left.addStretch()
        main_h.addLayout(left, 1)

        # ---- Profile details & actions ----
        right = QVBoxLayout()

        info_group = QGroupBox("PROFILE DETAILS")
        info_layout = QVBoxLayout(info_group)

        self._name_lbl = QLabel("—")
        self._name_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px; font-weight: 600;")
        info_layout.addWidget(self._name_lbl)

        self._desc_edit = QTextEdit()
        self._desc_edit.setReadOnly(True)
        self._desc_edit.setMaximumHeight(80)
        self._desc_edit.setStyleSheet(
            f"background: {COLORS['bg_dark']}; font-size: 11px; border: none;"
        )
        info_layout.addWidget(self._desc_edit)
        right.addWidget(info_group)

        # Actions
        act_group = QGroupBox("ACTIONS")
        act_layout = QHBoxLayout(act_group)

        btn_load = QPushButton("Load Profile")
        btn_load.setObjectName("btn_primary")
        btn_load.clicked.connect(self._load_selected)

        btn_save = QPushButton("Save Current")
        btn_save.setObjectName("btn_success")
        btn_save.clicked.connect(self._save_current)

        btn_dupe = QPushButton("Duplicate")
        btn_dupe.clicked.connect(self._duplicate_selected)

        btn_delete = QPushButton("Delete")
        btn_delete.setObjectName("btn_danger")
        btn_delete.clicked.connect(self._delete_selected)

        act_layout.addWidget(btn_load)
        act_layout.addWidget(btn_save)
        act_layout.addWidget(btn_dupe)
        act_layout.addWidget(btn_delete)
        right.addWidget(act_group)

        # Export / Import
        io_group = QGroupBox("EXPORT / IMPORT")
        io_layout = QHBoxLayout(io_group)

        btn_export = QPushButton("Export Profile...")
        btn_export.clicked.connect(self._export_profile)
        btn_import = QPushButton("Import Profile...")
        btn_import.clicked.connect(self._import_profile)
        io_layout.addWidget(btn_export)
        io_layout.addWidget(btn_import)
        right.addWidget(io_group)

        # Create new
        new_group = QGroupBox("CREATE NEW PROFILE")
        new_layout = QHBoxLayout(new_group)
        self._new_name_edit = QLineEdit()
        self._new_name_edit.setPlaceholderText("Profile name...")
        btn_create = QPushButton("Create")
        btn_create.setObjectName("btn_primary")
        btn_create.clicked.connect(self._create_profile)
        new_layout.addWidget(self._new_name_edit)
        new_layout.addWidget(btn_create)
        right.addWidget(new_group)
        right.addStretch()

        main_h.addLayout(right, 2)

        # Load initial list
        self._load_list()

        if self._profiles:
            self._profiles.profiles_changed.connect(self._load_list)

    def _load_list(self):
        self._profile_list.clear()
        if not self._profiles:
            return
        for name in self._profiles.list_profiles():
            item = QListWidgetItem(name)
            self._profile_list.addItem(item)
            # Highlight current profile
            if name == (self._profiles.current_name or ""):
                item.setForeground(Qt.GlobalColor.cyan)

    def _on_profile_selected(self, row: int):
        if row < 0:
            return
        name = self._profile_list.item(row).text()
        self._name_lbl.setText(name)

    def _load_selected(self):
        item = self._profile_list.currentItem()
        if item and self._profiles:
            self._profiles.load(item.text())
            self._load_list()

    def _save_current(self):
        item = self._profile_list.currentItem()
        if not item or not self._profiles:
            return
        name = item.text()
        self._profiles.save(name)

    def _duplicate_selected(self):
        item = self._profile_list.currentItem()
        if not item or not self._profiles:
            return
        name = item.text()
        new_name, ok = QInputDialog.getText(self, "Duplicate Profile", "New profile name:")
        if ok and new_name.strip():
            self._profiles.duplicate(name, new_name.strip())

    def _delete_selected(self):
        item = self._profile_list.currentItem()
        if not item or not self._profiles:
            return
        name = item.text()
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Delete profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._profiles.delete(name)

    def _export_profile(self):
        item = self._profile_list.currentItem()
        if not item or not self._profiles:
            return
        name = item.text()
        path, _ = QFileDialog.getSaveFileName(self, "Export Profile", f"{name}.json", "JSON (*.json)")
        if path:
            self._profiles.export_profile(name, path)

    def _import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Profile", "", "JSON (*.json)")
        if path and self._profiles:
            self._profiles.import_profile(path)

    def _create_profile(self):
        name = self._new_name_edit.text().strip()
        if name and self._profiles:
            self._profiles.save(name, description="New profile")
            self._new_name_edit.clear()
