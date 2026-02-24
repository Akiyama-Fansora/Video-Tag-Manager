# folder_video_manager.py - Final V22: 修复精准视频切换 + 新增右键删除标签功能（完整版）
import sys
import os
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QListWidget, QLabel,
    QFileDialog, QMessageBox, QListWidgetItem, QScrollArea, QCheckBox, QInputDialog,
    QApplication, QMenu, QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QFont
from video_player import VideoPlayer
from data_manager import DataManager

# --- 尝试从 ui_components 导入，若失败则内联定义 ---
try:
    from ui_components import VIDEO_PATH_ROLE, VIDEO_EXTENSIONS
except ImportError:
    from PyQt5.QtCore import Qt
    VIDEO_PATH_ROLE = Qt.UserRole + 1
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm', '.m4v'}

SAVE_DIR = "Save"
PLAYBACK_STATE_FILE = os.path.join(SAVE_DIR, "video_playback_state.json")
os.makedirs(SAVE_DIR, exist_ok=True)


class TagSelectionDialog(QDialog):
    def __init__(self, available_tags, parent=None, title="选择标签"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(300, 400)
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for tag in sorted(available_tags):
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_tags(self):
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected


class FolderVideoManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("文件夹视频管理器 (Final V22)")
        self.resize(1400, 750)
        self.data_manager = DataManager()
        self.selected_filter_tags = set()
        self.current_folder = None
        self.video_player = None
        self.current_selected_video_path = None
        self.is_fullscreen_mode = False
        self.playback_states = self.load_playback_states()

        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QHBoxLayout(central)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # 左侧面板
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(280)
        self.list_widget.setMaximumWidth(280)
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.on_right_click)
        self.list_widget.setFont(QFont("SimHei", 12))
        left_layout.addWidget(self.list_widget)
        self.main_layout.addWidget(self.left_panel)

        # 视频占位
        self.placeholder = QWidget()
        self.placeholder.setStyleSheet("background-color: #000;")
        self.main_layout.addWidget(self.placeholder, stretch=3)

        # 右侧面板
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self.current_video_name_label = QLabel("当前未选择任何视频文件")
        self.current_video_name_label.setFont(QFont("SimHei", 12))
        self.current_video_name_label.setStyleSheet("color: #333;")
        self.current_video_name_label.setWordWrap(True)
        right_layout.addWidget(self.current_video_name_label)

        self.current_video_tags_label = QLabel("当前视频标签")
        self.current_video_tags_label.setFont(QFont("SimHei", 12, QFont.Bold))
        right_layout.addWidget(self.current_video_tags_label)
        self.current_tags_scroll = QScrollArea()
        self.current_tags_scroll.setWidgetResizable(True)
        self.current_tags_widget = QWidget()
        self.current_tags_layout = QVBoxLayout(self.current_tags_widget)
        self.current_tags_layout.setContentsMargins(5, 5, 5, 5)
        self.current_tags_layout.setSpacing(5)
        self.current_tags_layout.setAlignment(Qt.AlignTop)
        self.current_tags_scroll.setWidget(self.current_tags_widget)
        right_layout.addWidget(self.current_tags_scroll, stretch=1)

        tag_header_layout = QHBoxLayout()
        self.global_tags_label = QLabel("全局已知标签列表")
        self.global_tags_label.setFont(QFont("SimHei", 12, QFont.Bold))
        tag_header_layout.addWidget(self.global_tags_label)
        add_global_tag_btn = QPushButton("+")
        add_global_tag_btn.setFixedSize(24, 24)
        add_global_tag_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        add_global_tag_btn.clicked.connect(self.add_new_global_tag)
        tag_header_layout.addWidget(add_global_tag_btn)
        tag_header_layout.addStretch()
        right_layout.addLayout(tag_header_layout)

        self.global_tags_scroll = QScrollArea()
        self.global_tags_scroll.setWidgetResizable(True)
        self.global_tags_widget = QWidget()
        self.global_tags_layout = QVBoxLayout(self.global_tags_widget)
        self.global_tags_layout.setContentsMargins(5, 5, 5, 5)
        self.global_tags_layout.setSpacing(5)
        self.global_tags_layout.setAlignment(Qt.AlignTop)
        self.global_tags_scroll.setWidget(self.global_tags_widget)
        right_layout.addWidget(self.global_tags_scroll, stretch=2)

        self.main_layout.addWidget(self.right_panel, stretch=1)

        toolbar = self.addToolBar("工具栏")
        toolbar.setIconSize(QSize(24, 24))
        self.back_action = toolbar.addAction("← 返回上级目录", self.go_back)
        self.back_action.setEnabled(False)
        toolbar.addSeparator()
        toolbar.addAction("添加视频文件夹", self.add_folder)
        toolbar.addAction("删除视频文件夹", self.delete_folder)

        self.show_folder_list()
        self.update_global_tags_list()

    def load_playback_states(self):
        if os.path.exists(PLAYBACK_STATE_FILE):
            try:
                with open(PLAYBACK_STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] 读取播放状态失败: {e}")
                return {}
        return {}

    def save_playback_states(self):
        try:
            with open(PLAYBACK_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.playback_states, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] 保存播放状态失败: {e}")

    def update_current_context_ui(self):
        selected_items = self.list_widget.selectedItems()
        if selected_items and self.current_folder is not None:
            from ui_components import VIDEO_PATH_ROLE
            path = selected_items[0].data(VIDEO_PATH_ROLE)
            if path and os.path.isfile(path):
                self.current_selected_video_path = path
                filename = os.path.basename(path)
                self.current_video_name_label.setText(f"当前选中视频文件: {filename}")
                tags = self.data_manager.all_videos_info.get(path, {}).get('tags', [])
                self.update_current_tags_ui(tags)
                return
        self.current_selected_video_path = None
        self.current_video_name_label.setText("当前未选择任何视频文件")
        self.update_current_tags_ui([])

    def update_current_tags_ui(self, tags):
        while self.current_tags_layout.count():
            child = self.current_tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for tag in sorted(tags):
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(tag)
            label.setFont(QFont("SimHei", 12))
            label.setStyleSheet("""
                background-color: #e0e0e0;
                border: 1px solid #aaa;
                border-radius: 6px;
                padding: 4px 8px;
                color: #333;
            """)
            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(16, 16)
            remove_btn.setStyleSheet("""
                QPushButton {
                    background: #ff6666;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background: #cc3333;
                }
            """)
            remove_btn.clicked.connect(lambda _, t=tag: self.remove_tag_from_current_video(t))
            container_layout.addWidget(label)
            container_layout.addWidget(remove_btn)
            self.current_tags_layout.addWidget(container)
        self.current_tags_layout.addStretch()

    def update_global_tags_list(self):
        while self.global_tags_layout.count():
            child = self.global_tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for tag in sorted(self.data_manager.all_known_tags):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            cb = QCheckBox(tag)
            cb.setFont(QFont("SimHei", 12))
            cb.setChecked(tag in self.selected_filter_tags)
            cb.stateChanged.connect(lambda state, t=tag: self.toggle_filter_tag(t, state == Qt.Checked))
            row_layout.addWidget(cb)
            add_btn = QPushButton("+")
            add_btn.setFixedSize(24, 24)
            add_btn.setStyleSheet("""
                QPushButton {
                    background: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #45a049;
                }
            """)
            add_btn.clicked.connect(lambda _, t=tag: self.add_tag_to_current_video(t))
            row_layout.addWidget(add_btn)
            edit_btn = QPushButton("✏️")
            edit_btn.setFixedSize(24, 24)
            edit_btn.clicked.connect(lambda _, t=tag: self.rename_global_tag(t))
            row_layout.addWidget(edit_btn)
            delete_btn = QPushButton("🗑️")
            delete_btn.setFixedSize(24, 24)
            delete_btn.clicked.connect(lambda _, t=tag: self.delete_global_tag(t))
            row_layout.addWidget(delete_btn)
            self.global_tags_layout.addWidget(row)
        self.global_tags_layout.addStretch()

    def add_tag_to_current_video(self, tag):
        if not self.current_selected_video_path:
            QMessageBox.warning(self, "无选中视频", "请先选择一个视频文件。")
            return
        video_path = self.current_selected_video_path
        if video_path not in self.data_manager.all_videos_info:
            self.data_manager.all_videos_info[video_path] = {'tags': []}
        tags = set(self.data_manager.all_videos_info[video_path].get('tags', []))
        tags.add(tag)
        self.data_manager.all_videos_info[video_path]['tags'] = list(tags)
        self.data_manager.save_labels(self.data_manager.all_videos_info)
        self.update_current_context_ui()

    def remove_tag_from_current_video(self, tag):
        if not self.current_selected_video_path:
            return
        video_path = self.current_selected_video_path
        if video_path in self.data_manager.all_videos_info:
            tags = set(self.data_manager.all_videos_info[video_path].get('tags', []))
            tags.discard(tag)
            self.data_manager.all_videos_info[video_path]['tags'] = list(tags)
            self.data_manager.save_labels(self.data_manager.all_videos_info)
            self.update_current_context_ui()
            self.update_global_tags_list()

    def add_new_global_tag(self):
        tag, ok = QInputDialog.getText(self, "添加新标签", "请输入新标签名称：")
        if ok and tag.strip():
            tag = tag.strip()
            if tag in self.data_manager.all_known_tags:
                QMessageBox.warning(self, "标签已存在", f"标签 '{tag}' 已存在于全局标签列表中。")
                return
            self.data_manager.all_known_tags.add(tag)
            self.data_manager.save_all_known_tags(self.data_manager.all_known_tags)
            self.update_global_tags_list()

    def rename_global_tag(self, old_tag):
        new_tag, ok = QInputDialog.getText(self, "重命名标签", "请输入新标签名称：", text=old_tag)
        if ok and new_tag.strip():
            new_tag = new_tag.strip()
            if new_tag == old_tag:
                return
            if new_tag in self.data_manager.all_known_tags:
                QMessageBox.warning(self, "标签已存在", f"标签 '{new_tag}' 已存在。")
                return
            self.data_manager.all_known_tags.discard(old_tag)
            self.data_manager.all_known_tags.add(new_tag)
            for video_info in self.data_manager.all_videos_info.values():
                tags = set(video_info.get('tags', []))
                if old_tag in tags:
                    tags.discard(old_tag)
                    tags.add(new_tag)
                    video_info['tags'] = list(tags)
            self.data_manager.save_all_known_tags(self.data_manager.all_known_tags)
            self.data_manager.save_labels(self.data_manager.all_videos_info)
            self.update_global_tags_list()
            self.update_current_context_ui()

    def delete_global_tag(self, tag_to_delete):
        reply = QMessageBox.question(
            self, '确认删除', f"确定要永久删除全局标签 '{tag_to_delete}' 吗？\n该标签将从所有视频中移除。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.data_manager.all_known_tags.discard(tag_to_delete)
            for video_info in self.data_manager.all_videos_info.values():
                tags = set(video_info.get('tags', []))
                tags.discard(tag_to_delete)
                video_info['tags'] = list(tags)
            self.data_manager.save_all_known_tags(self.data_manager.all_known_tags)
            self.data_manager.save_labels(self.data_manager.all_videos_info)
            self.update_global_tags_list()
            self.update_current_context_ui()

    def toggle_filter_tag(self, tag, checked):
        if checked:
            self.selected_filter_tags.add(tag)
        else:
            self.selected_filter_tags.discard(tag)
        if self.current_folder:
            self.show_video_list(self.current_folder)

    def show_folder_list(self):
        self.current_folder = None
        self.back_action.setEnabled(False)
        self.list_widget.clear()
        for folder in self.data_manager.folders:
            item = QListWidgetItem(folder)
            item.setData(VIDEO_PATH_ROLE, folder)
            self.list_widget.addItem(item)

    def show_video_list(self, folder_path):
        self.current_folder = folder_path
        self.back_action.setEnabled(True)
        self.list_widget.clear()
        videos = []
        if os.path.isdir(folder_path):
            for p in Path(folder_path).rglob('*'):
                if p.suffix.lower() in VIDEO_EXTENSIONS:
                    full_path = str(p.resolve())
                    videos.append(full_path)
        if self.selected_filter_tags:
            filtered = []
            for v in videos:
                tags = self.data_manager.all_videos_info.get(v, {}).get('tags', [])
                if self.selected_filter_tags.issubset(set(tags)):
                    filtered.append(v)
            videos = filtered
        for video_path in sorted(videos):
            item = QListWidgetItem(os.path.basename(video_path))
            item.setData(VIDEO_PATH_ROLE, video_path)
            self.list_widget.addItem(item)

    def go_back(self):
        self.selected_filter_tags.clear()
        self.show_folder_list()

    def release_video_player(self):
        if self.video_player:
            state = self.video_player.get_current_state()
            if state and state['path']:
                self.playback_states[state['path']] = state
                self.save_playback_states()
            try:
                self.video_player.player.stop()
            except:
                pass
            self.video_player.update_timer.stop()
            self.main_layout.removeWidget(self.video_player)
            self.video_player.setParent(None)
            self.video_player.deleteLater()
            self.video_player = None
            self.main_layout.insertWidget(1, self.placeholder, stretch=3)
            self.update_current_context_ui()

    def on_item_double_clicked(self, item):
        path = item.data(VIDEO_PATH_ROLE)
        if not path:
            return
        if self.current_folder is None:
            if os.path.isdir(path):
                self.show_video_list(path)
                return
        if os.path.isfile(path):
            self.open_video(path)

    # === 【核心修复】精准查找相邻视频 ===
    def _find_adjacent_video(self, direction):
        if self.current_folder is None or not self.video_player or not self.video_player.video_path:
            return None

        current_path = self.video_player.video_path
        items = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item_path = item.data(VIDEO_PATH_ROLE)
            if os.path.isfile(item_path):  # 只考虑视频文件
                items.append(item_path)

        try:
            idx = items.index(current_path)
        except ValueError:
            return None

        new_idx = idx + direction
        if 0 <= new_idx < len(items):
            return items[new_idx]
        return None

    def play_prev_video(self):
        prev_path = self._find_adjacent_video(-1)
        if prev_path:
            self.open_video(prev_path)

    def play_next_video(self):
        next_path = self._find_adjacent_video(1)
        if next_path:
            self.open_video(next_path)

    def open_video(self, video_path):
        if self.video_player:
            state = self.video_player.get_current_state()
            if state and state['path']:
                self.playback_states[state['path']] = state
                self.save_playback_states()

        if self.video_player is None:
            self.main_layout.removeWidget(self.placeholder)
            self.placeholder.setParent(None)
            self.video_player = VideoPlayer()
            self.video_player.play_pause_requested.connect(self.video_player.toggle_play_pause)
            self.video_player.volume_changed.connect(self.video_player.set_volume)
            self.video_player.seek_requested.connect(self.video_player.seek_to)
            self.video_player.fullscreen_requested.connect(self.toggle_fullscreen)
            self.video_player.close_requested.connect(self.release_video_player)
            self.video_player.prev_video_requested.connect(self.play_prev_video)
            self.video_player.next_video_requested.connect(self.play_next_video)
            self.main_layout.insertWidget(1, self.video_player, stretch=3)

        state = self.playback_states.get(video_path, {})
        resume_time = state.get('time_ms', 0)
        volume = state.get('volume', 100)
        speed = state.get('speed', 1.0)
        was_playing = state.get('playing', True)

        self.video_player.load_video(video_path, resume_time, volume, speed)
        self.video_player.setFocus()
        self.update_current_context_ui()

        if not was_playing:
            QTimer.singleShot(300, lambda: self.video_player.toggle_play_pause())

        # 高亮当前播放项（单选）
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(VIDEO_PATH_ROLE) == video_path:
                self.list_widget.setCurrentItem(item)
                break

    def closeEvent(self, event):
        if self.video_player:
            state = self.video_player.get_current_state()
            if state and state['path']:
                self.playback_states[state['path']] = state
                self.save_playback_states()
        event.accept()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择要添加的视频文件夹")
        if folder:
            folder = os.path.normpath(folder)
            if folder not in self.data_manager.folders and os.path.exists(folder):
                self.data_manager.folders.append(folder)
                self.show_folder_list()
                self.data_manager.save_folders(self.data_manager.folders)

    def delete_folder(self):
        if self.current_folder is not None:
            return
        current = self.list_widget.currentItem()
        if not current:
            return
        index = self.list_widget.row(current)
        if 0 <= index < len(self.data_manager.folders):
            folder_to_remove = self.data_manager.folders[index]
            reply = QMessageBox.question(self, '确认删除', f"确定要从列表中移除文件夹 '{folder_to_remove}' 吗？\n此操作不会删除硬盘上的实际文件。",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                del self.data_manager.folders[index]
                self.show_folder_list()
                self.data_manager.save_folders(self.data_manager.folders)

    def toggle_fullscreen(self):
        if self.is_fullscreen_mode:
            self.showNormal()
            self.is_fullscreen_mode = False
            self.left_panel.show()
            self.right_panel.show()
            self.placeholder.hide()
            self.main_layout.setContentsMargins(10, 10, 10, 10)
        else:
            self.is_fullscreen_mode = True
            self.left_panel.hide()
            self.right_panel.hide()
            self.placeholder.hide()
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.showFullScreen()
            if self.video_player:
                self.video_player.setFocus()

    # === 【新增】右键菜单：添加/删除标签 ===
    def on_right_click(self, position):
        if self.current_folder is None:
            return

        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        menu = QMenu(self)
        add_tag_action = menu.addAction("添加标签")
        remove_tag_action = menu.addAction("删除标签")
        action = menu.exec_(self.list_widget.mapToGlobal(position))

        if action == add_tag_action:
            self.show_add_tag_dialog_for_selection(selected_items)
        elif action == remove_tag_action:
            self.show_remove_tag_dialog_for_selection(selected_items)

    def show_add_tag_dialog_for_selection(self, selected_items):
        if not self.data_manager.all_known_tags:
            QMessageBox.information(self, "无可用标签", "当前没有可用的全局标签，请先添加标签。")
            return

        dialog = TagSelectionDialog(self.data_manager.all_known_tags, self, "选择要添加的标签")
        if dialog.exec_() == QDialog.Accepted:
            selected_tags = dialog.get_selected_tags()
            if not selected_tags:
                return

            video_paths = []
            for item in selected_items:
                path = item.data(VIDEO_PATH_ROLE)
                if path and os.path.isfile(path):
                    video_paths.append(path)

            for video_path in video_paths:
                if video_path not in self.data_manager.all_videos_info:
                    self.data_manager.all_videos_info[video_path] = {'tags': []}
                existing_tags = set(self.data_manager.all_videos_info[video_path].get('tags', []))
                existing_tags.update(selected_tags)
                self.data_manager.all_videos_info[video_path]['tags'] = list(existing_tags)

            self.data_manager.save_labels(self.data_manager.all_videos_info)
            self.update_current_context_ui()
            self.update_global_tags_list()

    def show_remove_tag_dialog_for_selection(self, selected_items):
        all_tags_in_selection = set()
        video_paths = []
        for item in selected_items:
            path = item.data(VIDEO_PATH_ROLE)
            if path and os.path.isfile(path):
                video_paths.append(path)
                tags = self.data_manager.all_videos_info.get(path, {}).get('tags', [])
                all_tags_in_selection.update(tags)

        if not all_tags_in_selection:
            QMessageBox.information(self, "无可删除标签", "选中的视频没有标签。")
            return

        dialog = TagSelectionDialog(all_tags_in_selection, self, "选择要删除的标签")
        if dialog.exec_() == QDialog.Accepted:
            tags_to_remove = dialog.get_selected_tags()
            if not tags_to_remove:
                return

            for video_path in video_paths:
                if video_path in self.data_manager.all_videos_info:
                    existing_tags = set(self.data_manager.all_videos_info[video_path].get('tags', []))
                    existing_tags.difference_update(tags_to_remove)
                    self.data_manager.all_videos_info[video_path]['tags'] = list(existing_tags)

            self.data_manager.save_labels(self.data_manager.all_videos_info)
            self.update_current_context_ui()
            self.update_global_tags_list()