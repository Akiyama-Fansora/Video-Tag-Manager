# video_player.py - 统一快捷键下降沿处理（所有快捷键仅响应首次按下）
import sys
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt5.QtGui import QFont, QKeyEvent

try:
    from ui_components import ClickableSlider
except ImportError:
    from PyQt5.QtWidgets import QSlider

    class ClickableSlider(QSlider):
        clicked = pyqtSignal(int)

        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton:
                opt = self.style().sliderPositionFromValue(
                    self.minimum(), self.maximum(), event.x(), self.width()
                )
                self.setValue(opt)
                self.clicked.emit(opt)
            super().mousePressEvent(event)


class VLCWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #000;")


class VideoPlayer(QWidget):
    play_pause_requested = pyqtSignal()
    volume_changed = pyqtSignal(int)
    seek_requested = pyqtSignal(int)
    fullscreen_requested = pyqtSignal()
    close_requested = pyqtSignal()
    prev_video_requested = pyqtSignal()
    next_video_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.instance = None
        self.player = None
        self.media = None
        self.is_playing = False
        self.current_speed = 1.0
        self.current_volume = 100
        self.total_duration = 0
        self.is_seeking = False
        self.playback_ended = False
        self.video_path = None
        self.last_volume_before_mute = 100

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.vlc_widget = VLCWidget()
        layout.addWidget(self.vlc_widget)

        self.top_overlay = self.create_top_overlay()
        self.bottom_overlay = self.create_bottom_overlay()
        self.left_arrow = self.create_side_arrow("◀", is_prev=True)
        self.right_arrow = self.create_side_arrow("▶", is_prev=False)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_overlays)

        self.init_vlc()
        self.setup_connections()
        self.hide_overlays()
        self.setFocusPolicy(Qt.StrongFocus)
        self.vlc_widget.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.ArrowCursor)
        self.setMouseTracking(True)

    def init_vlc(self):
        try:
            import vlc
            self.instance = vlc.Instance(
                "--quiet",
                "--no-xlib",
                "--no-video-title-show",
                "--disable-screensaver",
                "--no-embedded-video",
                "--no-keyboard-events"
            )
            self.player = self.instance.media_player_new()
            if sys.platform.startswith('win'):
                self.player.set_hwnd(int(self.vlc_widget.winId()))
            elif sys.platform.startswith('darwin'):
                self.player.set_nsobject(int(self.vlc_widget.winId()))
            else:
                self.player.set_xwindow(int(self.vlc_widget.winId()))
            self.player.video_set_key_input(False)
            self.player.video_set_mouse_input(False)
            self.player.audio_set_volume(self.current_volume)
            self.player.set_rate(self.current_speed)
            self.update_timer = QTimer(self)
            self.update_timer.timeout.connect(self.update_playback_state)
            self.update_timer.start(200)
        except Exception as e:
            print(f"[VLC Init Error] VLC 初始化失败（回退到空播放器）: {e}")
            self.player = None
            self.instance = None

    def create_top_overlay(self):
        overlay = QWidget(self)
        overlay.setStyleSheet("background-color: #222; color: white;")
        overlay.setFixedHeight(30)
        overlay.hide()
        layout = QHBoxLayout(overlay)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)
        self.top_label = QLabel("")
        self.top_label.setFont(QFont("SimHei", 14))
        self.top_label.setStyleSheet("color: white;")
        layout.addWidget(self.top_label)
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setFont(QFont("SimHei", 12))
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: white;
                padding: 0;
            }
            QPushButton:hover {
                color: #ff6666;
            }
        """)
        self.close_btn.clicked.connect(self.on_close_clicked)
        layout.addStretch(1)
        layout.addWidget(self.close_btn)
        return overlay

    def on_close_clicked(self):
        self.close_requested.emit()

    def create_bottom_overlay(self):
        overlay = QWidget(self)
        overlay.setStyleSheet("background-color: rgba(0, 0, 0, 160); color: white;")
        overlay.setFixedHeight(36)
        overlay.hide()
        layout = QHBoxLayout(overlay)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(24, 24)
        self.play_btn.setFont(QFont("SimHei", 12))
        self.play_btn.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: white;
            }
            QPushButton:hover {
                color: #ccc;
            }
        """)
        layout.addWidget(self.play_btn)
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setFont(QFont("SimHei", 14))
        self.time_label.setStyleSheet("color: white;")
        layout.addWidget(self.time_label)
        self.progress_slider = ClickableSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setValue(0)
        self.progress_slider.setFixedHeight(8)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: rgba(255, 255, 255, 20%);
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
                background: white;
                border: 1px solid #999;
            }
            QSlider::handle:horizontal:hover {
                background: #ddd;
            }
        """)
        layout.addWidget(self.progress_slider, stretch=1)
        self.speed_label = QLabel("1.0x")
        self.speed_label.setFont(QFont("SimHei", 14))
        self.speed_label.setStyleSheet("color: white;")
        layout.addWidget(self.speed_label)
        self.vol_icon = QLabel("🔊")
        self.vol_icon.setFont(QFont("SimHei", 14))
        self.vol_icon.setStyleSheet("color: white;")
        layout.addWidget(self.vol_icon)
        self.vol_slider = ClickableSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setFixedHeight(8)
        self.vol_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: rgba(255, 255, 255, 20%);
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
                background: white;
                border: 1px solid #999;
            }
            QSlider::handle:horizontal:hover {
                background: #ddd;
            }
        """)
        layout.addWidget(self.vol_slider)
        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setFixedSize(24, 24)
        self.fullscreen_btn.setFont(QFont("SimHei", 12))
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: white;
            }
            QPushButton:hover {
                color: #ccc;
            }
        """)
        layout.addWidget(self.fullscreen_btn)
        return overlay

    def create_side_arrow(self, text, is_prev):
        btn = QPushButton(text, self)
        btn.setFixedSize(40, 60)
        btn.setFont(QFont("SimHei", 18, QFont.Bold))
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: rgba(50, 50, 50, 220);
            }
        """)
        btn.setCursor(Qt.PointingHandCursor)
        btn.hide()
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        if is_prev:
            def on_prev():
                print("[DEBUG] 左箭头被点击！触发 prev_video_requested")
                self._on_prev_clicked()
            btn.clicked.connect(on_prev)
        else:
            def on_next():
                print("[DEBUG] 右箭头被点击！触发 next_video_requested")
                self._on_next_clicked()
            btn.clicked.connect(on_next)
        print(f"[DEBUG] 创建 {'左' if is_prev else '右'}箭头按钮，初始几何: {btn.geometry()}")
        return btn

    def _on_prev_clicked(self):
        print("[SIGNAL] 发出 prev_video_requested")
        self.prev_video_requested.emit()

    def _on_next_clicked(self):
        print("[SIGNAL] 发出 next_video_requested")
        self.next_video_requested.emit()

    def setup_connections(self):
        self.play_btn.clicked.connect(self.on_play_pause_clicked)
        self.vol_slider.valueChanged.connect(self.on_volume_changed)
        self.vol_slider.clicked.connect(self.on_volume_changed)
        self.speed_label.mousePressEvent = self.speed_label_clicked
        self.progress_slider.sliderPressed.connect(self.on_slider_pressed)
        self.progress_slider.sliderMoved.connect(self.on_slider_moved)
        self.progress_slider.sliderReleased.connect(self.on_slider_released)
        self.progress_slider.clicked.connect(self.on_slider_clicked)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

    def on_play_pause_clicked(self):
        print("[DEBUG] 播放/暂停按钮被点击")
        if self.playback_ended:
            self.restart_video()
        else:
            self.toggle_play_pause()

    def on_volume_changed(self, value):
        self.current_volume = value
        if self.player:
            self.player.audio_set_volume(value)
        self.set_volume_ui(value)
        self.volume_changed.emit(value)

    def speed_label_clicked(self, event):
        if event.button() == Qt.LeftButton:
            self.show_speed_menu()

    def show_speed_menu(self):
        speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
        menu = QMenu()
        menu.setFont(QFont("SimHei", 12))
        for speed in speeds:
            action = menu.addAction(f"{speed}x")
            action.triggered.connect(lambda checked, s=speed: self.change_speed(s))
        menu.exec_(self.speed_label.mapToGlobal(QPoint(0, 20)))

    def change_speed(self, speed):
        self.current_speed = speed
        if self.player:
            self.player.set_rate(speed)
        self.speed_label.setText(f"{speed:.1f}x")

    def on_slider_pressed(self):
        self.is_seeking = True

    def on_slider_moved(self, value):
        if not self.media or self.media.get_duration() <= 0:
            return
        ms = int(value * self.media.get_duration() / 1000)
        self.time_label.setText(
            f"{self.format_time(ms)} / {self.format_time(self.media.get_duration())}"
        )

    def on_slider_released(self):
        value = self.progress_slider.value()
        if self.media and self.media.get_duration() > 0:
            ms = int(value * self.media.get_duration() / 1000)
            self.seek_to(ms)
        self.is_seeking = False

    def on_slider_clicked(self, value):
        if self.media and self.media.get_duration() > 0:
            ms = int(value * self.media.get_duration() / 1000)
            self.seek_to(ms)
        self.is_seeking = False

    def seek_to(self, target_ms):
        if not self.player or not self.media:
            return
        self.player.set_time(target_ms)

    def format_time(self, ms):
        if ms < 0:
            ms = 0
        s = ms // 1000
        return f"{int(s // 3600):02d}:{int((s % 3600) // 60):02d}:{int(s % 60):02d}"

    def set_video_title(self, title):
        self.top_label.setText(title)

    def set_time_display(self, current_ms, total_ms):
        self.total_duration = total_ms
        self.time_label.setText(
            f"{self.format_time(current_ms)} / {self.format_time(total_ms)}"
        )
        if total_ms > 0:
            value = int((current_ms / total_ms) * 1000)
            if not self.is_seeking:
                self.progress_slider.setValue(value)

    def set_volume_ui(self, vol):
        self.vol_slider.setValue(vol)
        if vol == 0:
            self.vol_icon.setText("🔇")
        elif vol < 30:
            self.vol_icon.setText("🔉")
        else:
            self.vol_icon.setText("🔊")

    def toggle_fullscreen(self):
        self.fullscreen_requested.emit()

    def restart_video(self):
        if not self.media or not self.player:
            return
        self.player.stop()
        self.player.set_media(self.media)
        self.player.play()
        self.is_playing = True
        self.playback_ended = False
        self.play_btn.setText("⏸")

    def toggle_play_pause(self):
        if not self.player:
            return
        if self.is_playing:
            self.player.pause()
            self.is_playing = False
            self.play_btn.setText("▶")
        else:
            self.player.play()
            self.is_playing = True
            self.play_btn.setText("⏸")

    def load_video(self, video_path, resume_time_ms=0, volume=100, speed=1.0):
        self.video_path = video_path
        self.current_volume = volume
        self.current_speed = speed
        try:
            if self.player:
                self.player.stop()
            import vlc
            self.media = self.instance.media_new(video_path)
            self.player.set_media(self.media)
            self.is_playing = False
            self.playback_ended = False
            self.player.set_rate(speed)
            self.player.audio_set_volume(volume)
            self.set_video_title(os.path.basename(video_path))
            self.set_time_display(0, 0)
            self.set_speed_ui(speed)
            self.set_volume_ui(volume)
            self.play_btn.setText("▶")
            self.player.play()
            self.is_playing = True
            self.play_btn.setText("⏸")
            if resume_time_ms > 0:
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(300, lambda: self.seek_to(resume_time_ms))
        except Exception as e:
            print(f"[Load Video Error] 加载视频失败: {e}")

    def get_current_state(self):
        if not self.player or not self.media:
            return None
        current_time = self.player.get_time()
        total = self.media.get_duration()
        if total <= 0:
            return None
        return {
            'path': self.video_path,
            'time_ms': current_time,
            'volume': self.current_volume,
            'speed': self.current_speed,
            'playing': self.is_playing and not self.playback_ended
        }

    def mousePressEvent(self, event):
        pos = event.pos()
        print(f"[DEBUG] 鼠标点击位置: ({pos.x()}, {pos.y()})")
        if event.button() == Qt.LeftButton and not self.is_seeking:
            clicked_on_top = self.top_overlay.isVisible() and self.top_overlay.geometry().contains(pos)
            clicked_on_bottom = self.bottom_overlay.isVisible() and self.bottom_overlay.geometry().contains(pos)
            clicked_on_left = self.left_arrow.isVisible() and self.left_arrow.geometry().contains(pos)
            clicked_on_right = self.right_arrow.isVisible() and self.right_arrow.geometry().contains(pos)
            print(f"[DEBUG] 点击检测 -> top:{clicked_on_top}, bottom:{clicked_on_bottom}, left:{clicked_on_left}, right:{clicked_on_right}")
            if not (clicked_on_top or clicked_on_bottom or clicked_on_left or clicked_on_right):
                self.on_play_pause_clicked()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.show_overlays()
        self.hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hide_timer.start(1000)
        super().leaveEvent(event)

    def show_overlays(self):
        self.top_overlay.show()
        self.bottom_overlay.show()
        self.left_arrow.show()
        self.right_arrow.show()
        self.top_overlay.raise_()
        self.bottom_overlay.raise_()
        self.left_arrow.raise_()
        self.right_arrow.raise_()
        print("[DEBUG] 浮窗已显示并提升层级")

    def hide_overlays(self):
        self.top_overlay.hide()
        self.bottom_overlay.hide()
        self.left_arrow.hide()
        self.right_arrow.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        self.top_overlay.setFixedWidth(w)
        self.bottom_overlay.setFixedWidth(w)
        self.top_overlay.move(0, 0)
        self.bottom_overlay.move(0, h - self.bottom_overlay.height())
        self.left_arrow.move(10, h // 2 - self.left_arrow.height() // 2)
        self.right_arrow.move(w - self.right_arrow.width() - 10, h // 2 - self.right_arrow.height() // 2)
        print(f"[DEBUG] 窗口大小: {w}x{h}, 左箭头位置: {self.left_arrow.pos()}, 右箭头位置: {self.right_arrow.pos()}")

    def mouseMoveEvent(self, event):
        self.show_overlays()
        self.hide_timer.stop()
        self.hide_timer.start(1000)
        super().mouseMoveEvent(event)

    def update_playback_state(self):
        if not self.player or not self.media:
            return
        state = self.player.get_state()
        current = self.player.get_time()
        total = self.media.get_duration()
        if total > 0:
            self.set_time_display(current, total)
        if hasattr(self.player, 'get_state'):
            from vlc import State
            if state == State.Ended:
                self.is_playing = False
                self.playback_ended = True
                self.play_btn.setText("▶")
            elif state == State.Playing:
                self.is_playing = True
                self.playback_ended = False
                self.play_btn.setText("⏸")
            elif state == State.Paused:
                self.is_playing = False
                self.playback_ended = False
                self.play_btn.setText("▶")

    def set_volume(self, vol):
        self.current_volume = max(0, min(100, vol))
        if self.player:
            self.player.audio_set_volume(self.current_volume)
        self.set_volume_ui(self.current_volume)

    def set_speed_ui(self, speed):
        self.current_speed = speed
        self.speed_label.setText(f"{speed:.1f}x")

    # === 新增：统一快捷键入口（仅响应下降沿）===
    def keyPressEvent(self, event: QKeyEvent):
        # 所有快捷键只响应首次按下（下降沿），忽略自动重复
        if event.isAutoRepeat():
            return

        key = event.key()
        if key == Qt.Key_Space:
            self.on_space()
        elif key == Qt.Key_Escape and self.window().isFullScreen():
            self.on_escape_fullscreen()
        elif key == Qt.Key_F:
            self.on_f_toggle_fullscreen()
        elif key == Qt.Key_Up:
            self.on_volume_up()
        elif key == Qt.Key_Down:
            self.on_volume_down()
        elif key == Qt.Key_Left:
            self.on_seek_left()
        elif key == Qt.Key_Right:
            self.on_seek_right()
        elif key == Qt.Key_M:
            self.on_mute_toggle()
        else:
            super().keyPressEvent(event)

    # --- 具体功能实现 ---
    def on_space(self):
        self.toggle_play_pause()

    def on_escape_fullscreen(self):
        self.toggle_fullscreen()

    def on_f_toggle_fullscreen(self):
        self.toggle_fullscreen()

    def on_volume_up(self):
        new_vol = min(100, self.current_volume + 10)
        self.set_volume(new_vol)
        self.volume_changed.emit(new_vol)

    def on_volume_down(self):
        new_vol = max(0, self.current_volume - 10)
        self.set_volume(new_vol)
        self.volume_changed.emit(new_vol)

    def on_seek_left(self):
        if self.player and self.media:
            current = self.player.get_time()
            new_time = max(0, current - 5000)
            self.seek_to(new_time)
            self.seek_requested.emit(new_time)

    def on_seek_right(self):
        if self.player and self.media:
            total = self.media.get_duration()
            current = self.player.get_time()
            new_time = min(total, current + 5000)
            self.seek_to(new_time)
            self.seek_requested.emit(new_time)

    def on_mute_toggle(self):
        if self.current_volume == 0:
            self.set_volume(self.last_volume_before_mute)
            self.volume_changed.emit(self.last_volume_before_mute)
        else:
            self.last_volume_before_mute = self.current_volume
            self.set_volume(0)
            self.volume_changed.emit(0)