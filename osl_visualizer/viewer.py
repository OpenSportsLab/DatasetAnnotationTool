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

from utils import ms_to_time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[logging.StreamHandler()]
)

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
        self.timeSpinBox.valueChanged.connect(self.update_annotation)
        self.prevButton.clicked.connect(self.go_to_previous_annotation)
        self.nextButton.clicked.connect(self.go_to_next_annotation)
        self.slider.sliderMoved.connect(self.seek_slider)
        self.player.positionChanged.connect(self.update_slider)
        self.player.durationChanged.connect(self.update_duration)

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
            timestamp = ann["position"] / 1000
            label = ann["label"]
            display = f"[{timestamp:.1f}s] {label}"
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
        self.timeSpinBox.blockSignals(True)
        self.timeSpinBox.setValue(ann["position"])
        self.timeSpinBox.blockSignals(False)
        self._updating_selection = False

        if "metadata" in ann:
            pretty = json.dumps(ann["metadata"], indent=2, ensure_ascii=False)
            self.metadataTextEdit.setText(pretty)
        else:
            self.metadataTextEdit.setText("")

        self.player.setPosition(ann["position"])
        self.player.play()
        self.playButton.setText("Pause")
        logging.info(f"Selected annotation at idx={idx}, time={ann['position']}ms, label={ann['label']}")

    def update_annotation(self):
        if self.current_annotation_index is None or self._updating_selection:
            return
        new_label = self.labelComboBox.currentText()
        new_time = self.timeSpinBox.value()
        ann = self.current_annotations[self.current_annotation_index]
        ann["label"] = new_label
        ann["position"] = new_time

        item = self.annotationListWidget.item(self.current_annotation_index)
        item.setText(f"[{new_time / 1000:.1f}s] {new_label}")

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
