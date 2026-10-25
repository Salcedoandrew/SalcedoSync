from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.album_choice import ALBUM_MODES
from gui.widgets import Card, DroppableLineEdit, FormSection


def build_upload_folder_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["upload-folder"] = {}

    card = Card("Source Configuration", required=True)
    form = FormSection()

    host.source_path_edit = DroppableLineEdit()
    host.source_path_edit.setPlaceholderText("/path/to/files or /path/to/archive.zip")
    host.inputs["upload-folder"]["path"] = host.source_path_edit

    btn_folder = QPushButton("Select Folder…")
    btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_folder.clicked.connect(host.browse_folder_upload)

    btn_zip = QPushButton("Select ZIP Archive…")
    btn_zip.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_zip.clicked.connect(host.browse_zip_upload)

    btn_box = QHBoxLayout()
    btn_box.setContentsMargins(0, 4, 0, 0)
    btn_box.setSpacing(10)
    btn_box.addWidget(btn_folder)
    btn_box.addWidget(btn_zip)
    btn_box.addStretch()

    path_container = QWidget()
    path_layout = QVBoxLayout(path_container)
    path_layout.setContentsMargins(0, 0, 0, 0)
    path_layout.setSpacing(6)
    path_layout.addWidget(host.source_path_edit)
    path_layout.addLayout(btn_box)
    path_err = host._make_field_error_label()
    path_layout.addWidget(path_err)
    host._register_field_error_label("upload-folder", "path", path_err)
    host._bind_field_error_clear("upload-folder", "path", host.source_path_edit)

    form.add_row(
        "Folder / ZIP to upload",
        path_container,
        "Every file inside this folder will be considered. ZIP archives are also supported.",
    )

    card.layout.addLayout(form)
    lay.addWidget(card)

    # "Where should these go in Immich?" (same 4 choices as Immich Upload)
    card = Card("Where should these go in Immich?")
    form = FormSection()

    c_mode = QComboBox()
    c_mode.addItems(list(ALBUM_MODES))
    host.inputs["upload-folder"]["album-mode"] = c_mode
    form.add_row("Destination", c_mode)

    c_existing = QComboBox()
    c_existing.setEditable(True)
    c_existing.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    c_existing.lineEdit().setPlaceholderText("Type to search your albums")
    completer = c_existing.completer()
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    host.inputs["upload-folder"]["album-existing"] = c_existing
    host.album_existing_combo = c_existing
    btn_refresh = QPushButton("Refresh")
    btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_refresh.clicked.connect(host.refresh_album_list)
    existing_box = QWidget()
    existing_row = QHBoxLayout(existing_box)
    existing_row.setContentsMargins(0, 0, 0, 0)
    existing_row.addWidget(c_existing, 1)
    existing_row.addWidget(btn_refresh)
    form.add_row("Album", existing_box)

    t_new = QLineEdit()
    t_new.setPlaceholderText("e.g. Family Trip 2026")
    host.inputs["upload-folder"]["album-new"] = t_new
    form.add_row("New album name", t_new)

    def on_mode_changed(text: str):
        mode = ALBUM_MODES.get(text, "none")
        form.setRowVisible(existing_box, mode == "existing")
        form.setRowVisible(t_new, mode == "new")
        if mode == "existing" and c_existing.count() == 0:
            host.refresh_album_list()
        host._schedule_status_update()

    c_mode.currentTextChanged.connect(on_mode_changed)
    c_existing.currentTextChanged.connect(lambda _t: host._schedule_status_update())
    t_new.textChanged.connect(lambda _t: host._schedule_status_update())
    host._on_album_mode_changed = on_mode_changed
    on_mode_changed(c_mode.currentText())

    cb_compress = QCheckBox("Compress images (same as Immich Upload)")
    cb_compress.setToolTip(
        "JPEG/PNG/WebP/GIF are compressed with caesiumclt at quality 80, keeping "
        "EXIF/GPS and file dates, into a temp copy. Originals are never changed. "
        "Videos and RAW files upload as they are."
    )
    host.inputs["upload-folder"]["compress"] = cb_compress
    form.add_row("Compression", cb_compress)

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("upload-folder")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
