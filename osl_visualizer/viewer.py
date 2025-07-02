import os
import json
import logging

from PyQt6 import uic
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QListWidgetItem, QMessageBox
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QShortcut, QKeySequence

from utils import ms_to_time
from utils import ms_to_hms  # at the top if not already imported
from utils import ms_to_hms_ms
from utils import hms_ms_to_ms

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[logging.StreamHandler()]
)
from PyQt6 import uic
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import QSettings

class ConfigDialog(QDialog):
    def __init__(self, parent=None, current_jump_before=5000):
        super().__init__(parent)
        # uic.loadUi("ui/configdialog.ui", self)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "ui/configdialog.ui"), self)

        self.jumpBeforeSpinBox.setValue(current_jump_before)
        self.okButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

    def get_jump_before(self):
        return self.jumpBeforeSpinBox.value()

class DatasetViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(os.path.join(os.path.dirname(__file__), "ui/mainwindow.ui"), self)

        # Patch: Replace placeholder with QVideoWidget
        placeholder = self.videoWidgetPlaceholder
        layout = placeholder.parent().layout()
        self.videoWidget = QVideoWidget(self)
        layout.replaceWidget(placeholder, self.videoWidget)
        placeholder.deleteLater()
        self.videoWidget.setMinimumSize(300, 200)
        self.videoWidget.show()

        self.osl_data = None
        self.current_annotations = []
        self.current_video_path = ""
        self.video_dir = os.getcwd()
        self.current_annotation_index = None
        self.available_labels = []
        self.current_video_info = None
        self._updating_selection = False
        self.jump_before_ms = 5000

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.videoWidget)
        

        # Connect signals
        self.loadButton.clicked.connect(self.load_osl_json)
        self.saveButton.clicked.connect(self.save_osl_json)
        self.videoListWidget.itemClicked.connect(self.load_video)
        self.annotationListWidget.itemClicked.connect(self.select_annotation)
        self.playButton.clicked.connect(self.toggle_play_pause)
        self.labelComboBox.currentIndexChanged.connect(self.update_annotation)
        self.setTimeToVideoButton.clicked.connect(self.set_annotation_time_to_video)
        self.prevButton.clicked.connect(self.go_to_previous_annotation)
        self.nextButton.clicked.connect(self.go_to_next_annotation)
        self.slider.sliderMoved.connect(self.seek_slider)
        self.player.positionChanged.connect(self.update_slider)
        self.player.durationChanged.connect(self.update_duration)
        self.back5sButton.clicked.connect(lambda: self.step_video(-5000))
        self.back1sButton.clicked.connect(lambda: self.step_video(-1000))
        self.forward1sButton.clicked.connect(lambda: self.step_video(1000))
        self.forward5sButton.clicked.connect(lambda: self.step_video(5000))
        self.backFrameButton.clicked.connect(lambda: self.step_frame(-1))
        self.forwardFrameButton.clicked.connect(lambda: self.step_frame(1))
        self.addAnnotationButton.clicked.connect(self.add_annotation_at_current_time)
        self.removeAnnotationButton.clicked.connect(self.remove_selected_annotation)
        self.actionOpen_Settings.triggered.connect(self.show_config_dialog)
        
        # self.space_shortcut = 
        QShortcut(QKeySequence("Space"), self).activated.connect(self.toggle_play_pause)


        self.left_shortcut = QShortcut(QKeySequence("Left"), self)
        self.left_shortcut.activated.connect(lambda: self.step_frame(-1))

        self.right_shortcut = QShortcut(QKeySequence("Right"), self)
        self.right_shortcut.activated.connect(lambda: self.step_frame(1))


        # Ctrl+Arrow for 1 sec
        self.ctrl_left_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)
        self.ctrl_left_shortcut.activated.connect(lambda: self.step_video(-1000))
        self.ctrl_right_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        self.ctrl_right_shortcut.activated.connect(lambda: self.step_video(1000))

        # Ctrl+Shift+Arrow for 5 sec
        self.ctrl_shift_left_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Left"), self)
        self.ctrl_shift_left_shortcut.activated.connect(lambda: self.step_video(-5000))
        self.ctrl_shift_right_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Right"), self)
        self.ctrl_shift_right_shortcut.activated.connect(lambda: self.step_video(5000))


        self.load_settings()



    def load_osl_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open OSL JSON File", "", "JSON Files (*.json)")
        if file_path:
            logging.info(f"Loading OSL JSON file: {file_path}")
            self.load_osl_json_from_file(file_path)

    def load_osl_json_from_file(self, file_path):
        file_path = os.path.abspath(file_path)
        self.videoListWidget.clear()
        try:
            with open(file_path, 'r') as f:
                self.osl_data = json.load(f)
            logging.info(f"Loaded JSON with {len(self.osl_data.get('videos', []))} videos")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load JSON: {e}")
            return

        self.available_labels = self.osl_data.get("labels", [])
        self.labelComboBox.clear()
        self.labelComboBox.addItems(self.available_labels)

        for video in self.osl_data.get("videos", []):
            path = video.get("path")
            item_text = f"{path} ({len(video.get('annotations', []))} events)"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, video)
            self.videoListWidget.addItem(item)

        self.video_dir = os.path.dirname(file_path)

    def save_osl_json(self):
        if not self.osl_data:
            logging.warning("No data to save.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save OSL JSON File", "", "JSON Files (*.json)")
        if not file_path:
            logging.info("Save cancelled.")
            return
        try:
            with open(file_path, 'w') as f:
                json.dump(self.osl_data, f, indent=2)
            logging.info(f"Annotations saved to {file_path}")
            QMessageBox.information(self, "Saved", f"Annotations saved to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save JSON: {e}")

    def load_video(self, item):
        self.current_video_info = item.data(Qt.ItemDataRole.UserRole)
        video_rel_path = self.current_video_info.get("path")
        if os.path.isabs(video_rel_path):
            self.current_video_path = video_rel_path
        else:
            self.current_video_path = os.path.normpath(os.path.join(self.video_dir, video_rel_path))
        self.current_annotations = self.current_video_info.get("annotations", [])
        self.current_annotation_index = None

        logging.info(f"Selected video: {self.current_video_path}")

        self.annotationListWidget.clear()

        for idx, ann in enumerate(self.current_annotations):
            hms = ms_to_hms_ms(ann["position"])
            label = ann["label"]
            display = f"[{hms}] {label}"
            ann_item = QListWidgetItem(display)
            ann_item.setData(Qt.ItemDataRole.UserRole, idx)
            self.annotationListWidget.addItem(ann_item)


        if os.path.exists(self.current_video_path):
            self.player.setSource(QUrl.fromLocalFile(self.current_video_path))
            self.player.play()
            self.playButton.setText("Pause")
            logging.info("Started video playback.")
        else:
            QMessageBox.warning(self, "File not found", f"Video file not found:\n{self.current_video_path}")

    def select_annotation(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        self.current_annotation_index = idx
        ann = self.current_annotations[idx]

        self._updating_selection = True
        self.labelComboBox.blockSignals(True)
        self.labelComboBox.setCurrentText(ann["label"])
        self.labelComboBox.blockSignals(False)
        self.annotationTimeLabel.setText(ms_to_hms_ms(ann["position"]))
        self._updating_selection = False

        if "metadata" in ann:
            pretty = json.dumps(ann["metadata"], indent=2, ensure_ascii=False)
            self.metadataTextEdit.setText(pretty)
        else:
            self.metadataTextEdit.setText("")

        jump_to = max(0, ann["position"] - self.jump_before_ms)  # 5000 ms = 5 seconds
        self.player.setPosition(jump_to)
        self.player.play()
        self.playButton.setText("Pause")
        logging.info(f"Selected annotation at idx={idx}, time={ann['position']}ms, label={ann['label']}")

    def update_annotation(self):
        if self.current_annotation_index is None or self._updating_selection:
            return
        new_label = self.labelComboBox.currentText()

        try:
            new_time = hms_ms_to_ms(self.timeLineEdit.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid time format", "Please enter time as HH:MM:SS:ZZZ")
            return

        ann = self.current_annotations[self.current_annotation_index]
        ann["label"] = new_label
        ann["position"] = new_time


        # hms = ms_to_hms(ann["position"])
        # label = ann["label"]
        display = f"[{ms_to_hms(new_time)}] {new_label}"
        # ann_item = QListWidgetItem(display)

        item = self.annotationListWidget.item(self.current_annotation_index)
        # item.setText(f"[{new_time / 1000:.1f}s] {new_label}")
        item.setText(display)

        logging.info(f"Updated annotation idx={self.current_annotation_index} to time={new_time}ms, label={new_label}")

    def toggle_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.playButton.setText("Play")
            logging.info("Paused video.")
        else:
            self.player.play()
            self.playButton.setText("Pause")
            logging.info("Playing video.")

    def go_to_previous_annotation(self):
        current_time = self.player.position()
        prev_idx = None
        for i, ann in enumerate(self.current_annotations):
            if ann["position"] < current_time:
                prev_idx = i
            else:
                break
        if prev_idx is not None:
            self.annotationListWidget.setCurrentRow(prev_idx)
            self.select_annotation(self.annotationListWidget.currentItem())
            logging.info(f"Jumped to previous annotation idx={prev_idx}.")

    def go_to_next_annotation(self):
        current_time = self.player.position()
        for i, ann in enumerate(self.current_annotations):
            if ann["position"] > current_time:
                self.annotationListWidget.setCurrentRow(i)
                self.select_annotation(self.annotationListWidget.currentItem())
                logging.info(f"Jumped to next annotation idx={i}.")
                break

    def update_slider(self, position):
        self.slider.blockSignals(True)
        duration = self.player.duration()
        if duration > 0:
            slider_value = int((position / duration) * 1000)
            self.slider.setValue(slider_value)
        self.timeLabel.setText(f"{ms_to_time(position)} / {ms_to_time(duration)}")
        self.highlight_current_annotation(position)
        self.slider.blockSignals(False)

    def highlight_current_annotation(self, position):
        for i, ann in enumerate(self.current_annotations):
            if abs(ann["position"] - position) < 500:
                self.annotationListWidget.setCurrentRow(i)
                logging.info(f"Highlighting annotation idx={i} at {position}ms.")
                break

    def update_duration(self, duration):
        self.slider.setValue(0)

    def seek_slider(self, value):
        duration = self.player.duration()
        if duration > 0:
            pos = int((value / 1000) * duration)
            self.player.setPosition(pos)
            self.timeLabel.setText(f"{ms_to_time(pos)} / {ms_to_time(duration)}")
            logging.info(f"Seeked video to {pos}ms.")


    def step_video(self, ms_delta):
        """Jump forward/backward in the video by ms_delta milliseconds."""
        pos = self.player.position()
        duration = self.player.duration()
        new_pos = min(max(pos + ms_delta, 0), duration)
        self.player.setPosition(new_pos)

    def step_frame(self, direction):
        """
        Step one frame forward (direction=1) or backward (direction=-1).
        Most videos are ~25-30 FPS, so 1 frame ≈ 33ms or 40ms.
        Adjust as needed for your typical frame rate.
        """
        frame_ms = 40  # ~25 FPS; adjust as needed
        self.step_video(frame_ms * direction)

    def add_annotation_at_current_time(self):
        if not self.current_video_info:
            QMessageBox.warning(self, "No video", "Please select a video first.")
            return
        current_time = int(self.player.position())
        current_label = self.labelComboBox.currentText() or (self.available_labels[0] if self.available_labels else "Event")
        # Create new annotation
        new_annotation = {
            "position": current_time,
            "label": current_label,
            "metadata": {}
        }
        # Insert in sorted order
        inserted = False
        for idx, ann in enumerate(self.current_annotations):
            if current_time < ann["position"]:
                self.current_annotations.insert(idx, new_annotation)
                inserted = True
                break
        if not inserted:
            self.current_annotations.append(new_annotation)
        self.current_video_info["annotations"] = self.current_annotations

        # Refresh the annotation list widget
        from utils import ms_to_hms
        self.annotationListWidget.clear()
        for idx, ann in enumerate(self.current_annotations):
            hms = ms_to_hms_ms(ann["position"])
            label = ann["label"]
            display = f"[{hms}] {label}"
            ann_item = QListWidgetItem(display)
            ann_item.setData(Qt.ItemDataRole.UserRole, idx)
            self.annotationListWidget.addItem(ann_item)

        # Set selection to the newly added annotation
        for idx, ann in enumerate(self.current_annotations):
            if ann is new_annotation:
                self.annotationListWidget.setCurrentRow(idx)
                break

        logging.info(f"Added annotation at {current_time}ms, label={current_label}")

    def remove_selected_annotation(self):
        selected_row = self.annotationListWidget.currentRow()
        if selected_row < 0 or selected_row >= len(self.current_annotations):
            QMessageBox.warning(self, "No Selection", "Please select an annotation to remove.")
            return

        # Confirm deletion (optional, can be removed if not desired)
        ret = QMessageBox.question(
            self, "Remove Annotation",
            "Are you sure you want to remove the selected annotation?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        # Remove from list and data
        removed = self.current_annotations.pop(selected_row)
        self.current_video_info["annotations"] = self.current_annotations

        # Refresh list widget
        from utils import ms_to_hms
        self.annotationListWidget.clear()
        for idx, ann in enumerate(self.current_annotations):
            hms = ms_to_hms_ms(ann["position"])
            label = ann["label"]
            display = f"[{hms}] {label}"
            ann_item = QListWidgetItem(display)
            ann_item.setData(Qt.ItemDataRole.UserRole, idx)
            self.annotationListWidget.addItem(ann_item)

        # Optionally select the next annotation
        if self.current_annotations:
            next_row = min(selected_row, len(self.current_annotations) - 1)
            self.annotationListWidget.setCurrentRow(next_row)
        else:
            self.current_annotation_index = None

        logging.info(f"Removed annotation at {removed['position']}ms, label={removed['label']}")

    def set_annotation_time_to_video(self):
        if self.current_annotation_index is None:
            QMessageBox.warning(self, "No annotation selected", "Please select an annotation to update.")
            return

        current_time = int(self.player.position())
        ann = self.current_annotations[self.current_annotation_index]
        ann["position"] = current_time

        # Resort the annotations list by position (time)
        self.current_annotations.sort(key=lambda a: a["position"])
        self.current_video_info["annotations"] = self.current_annotations

        # Refresh the annotation list widget
        from utils import ms_to_hms, ms_to_hms_ms
        self.annotationListWidget.clear()
        new_index = 0
        for idx, a in enumerate(self.current_annotations):
            hms = ms_to_hms_ms(a["position"])
            label = a["label"]
            display = f"[{hms}] {label}"
            ann_item = QListWidgetItem(display)
            ann_item.setData(Qt.ItemDataRole.UserRole, idx)
            self.annotationListWidget.addItem(ann_item)
            if a is ann:
                new_index = idx

        # Update the time label
        self.annotationTimeLabel.setText(ms_to_hms_ms(current_time))
        # Select the updated annotation in the new position
        self.annotationListWidget.setCurrentRow(new_index)
        self.current_annotation_index = new_index

        logging.info(f"Annotation updated and resorted to {current_time}ms (index {new_index})")

    def show_config_dialog(self):
        dialog = ConfigDialog(self, self.jump_before_ms)
        if dialog.exec():
            self.jump_before_ms = dialog.get_jump_before()
            self.save_settings()   # Persist!


    def save_settings(self):
        settings = QSettings("OSLActionSpotting", "DatasetAnnotationTool")
        settings.setValue("jump_before_ms", self.jump_before_ms)


    def load_settings(self):
        settings = QSettings("OSLActionSpotting", "DatasetAnnotationTool")
        # get returns QVariant; int(None) raises TypeError, so handle missing gracefully
        self.jump_before_ms = settings.value("jump_before_ms", 5000)

