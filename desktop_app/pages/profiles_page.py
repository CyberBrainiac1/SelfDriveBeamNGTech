"""
desktop_app/pages/profiles_page.py — Profiles: load, save, create, export.
Simple list + action buttons.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit,
    QFileDialog, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS


class ProfilesPage(BasePage):
    def __init__(self, **kwargs):
        self._profiles = kwargs.pop("profiles", None)
        super().__init__(title="Profiles", **kwargs)
        self._build()

    def _build(self):
        # ── Profile list ─────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setMaximumHeight(220)
        self.content_layout.addWidget(self._list)

        # ── Action row ───────────────────────────────────────────────
        row1 = QHBoxLayout()
        for label, fn in [("Load", self._load), ("Save Current", self._save),
                          ("Duplicate", self._duplicate), ("Delete", self._delete)]:
            b = QPushButton(label)
            if label == "Load":
                b.setObjectName("btn_primary")
            elif label == "Delete":
                b.setObjectName("btn_danger")
            b.clicked.connect(fn)
            row1.addWidget(b)
        row1.addStretch()
        self.content_layout.addLayout(row1)
        self.content_layout.addWidget(self._sep())

        # ── Create new ───────────────────────────────────────────────
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("New name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Profile name...")
        self._name_edit.setFixedWidth(200)
        btn_create = QPushButton("Create")
        btn_create.setObjectName("btn_success")
        btn_create.clicked.connect(self._create)
        row2.addWidget(self._name_edit)
        row2.addWidget(btn_create)
        row2.addStretch()
        self.content_layout.addLayout(row2)
        self.content_layout.addWidget(self._sep())

        # ── Export / Import ───────────────────────────────────────────
        row3 = QHBoxLayout()
        btn_exp = QPushButton("Export...")
        btn_exp.clicked.connect(self._export)
        btn_imp = QPushButton("Import...")
        btn_imp.clicked.connect(self._import)
        row3.addWidget(btn_exp)
        row3.addWidget(btn_imp)
        row3.addStretch()
        self.content_layout.addLayout(row3)
        self.content_layout.addStretch()

        self._reload_list()
        if self._profiles:
            self._profiles.profiles_changed.connect(self._reload_list)

    def _reload_list(self):
        self._list.clear()
        if not self._profiles:
            return
        for name in self._profiles.list_profiles():
            item = QListWidgetItem(name)
            if name == (self._profiles.current_name or ""):
                item.setForeground(Qt.GlobalColor.cyan)
            self._list.addItem(item)

    def _selected(self):
        item = self._list.currentItem()
        return item.text() if item else None

    def _load(self):
        name = self._selected()
        if name and self._profiles:
            self._profiles.load(name)
            self._reload_list()

    def _save(self):
        name = self._selected()
        if name and self._profiles:
            self._profiles.save(name)

    def _duplicate(self):
        name = self._selected()
        if not name or not self._profiles:
            return
        new_name, ok = QInputDialog.getText(self, "Duplicate", "New name:")
        if ok and new_name.strip():
            self._profiles.duplicate(name, new_name.strip())

    def _delete(self):
        name = self._selected()
        if not name or not self._profiles:
            return
        if QMessageBox.question(self, "Delete", f"Delete '{name}'?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) == QMessageBox.StandardButton.Yes:
            self._profiles.delete(name)

    def _create(self):
        name = self._name_edit.text().strip()
        if name and self._profiles:
            self._profiles.save(name, description="New profile")
            self._name_edit.clear()

    def _export(self):
        name = self._selected()
        if not name or not self._profiles:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export", f"{name}.json", "JSON (*.json)")
        if path:
            self._profiles.export_profile(name, path)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import", "", "JSON (*.json)")
        if path and self._profiles:
            self._profiles.import_profile(path)
