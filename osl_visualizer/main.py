import json
import os
import sys
import argparse
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QSplitter, QComboBox, QSpinBox,
    QFormLayout, QSlider, QMessageBox, QTextEdit, QSizePolicy
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt, QUrl

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[logging.StreamHandler()]
)

def ms_to_time(ms):
    seconds = ms // 1000
    return f"{seconds // 60:02}:{seconds % 60:02}"

class DatasetViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OSL Dataset Visualizer")
        self.resize(1600, 800)

        self.osl_data = None
        self.current_annotations = []
        self.current_video_path = ""
        self.video_dir = os.getcwd()
        self.current_annotation_index = None
        self.available_labels = []
        self.current_video_info = None

        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # Left Panel - Video List and Load/Save
        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self.load_video)
        self.video_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        load_btn = QPushButton("Load OSL JSON")
        load_btn.clicked.connect(self.load_osl_json)
        save_btn = QPushButton("Save OSL JSON")
        save_btn.clicked.connect(self.save_osl_json)

        left_panel = QVBoxLayout()
        left_panel.addWidget(load_btn)
        left_panel.addWidget(save_btn)
        left_panel.addWidget(QLabel("Games"))
        left_panel.addWidget(self.video_list)
        left_panel.addStretch()
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        splitter.addWidget(left_widget)

        # Center Panel - Video and Controls
        self.video_widget = QVideoWidget()
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.player.setVideoOutput(self.video_widget)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderMoved.connect(self.seek_slider)

        self.time_label = QLabel("00:00 / 00:00")

        self.player.positionChanged.connect(self.update_slider)
        self.player.durationChanged.connect(self.update_duration)

        video_controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_play_pause)
        video_controls.addWidget(self.play_button)

        center_panel = QVBoxLayout()
        center_panel.addWidget(self.video_widget)

        slider_layout = QHBoxLayout()
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.time_label)
        center_panel.addLayout(slider_layout)
        center_panel.addLayout(video_controls)
        center_panel.addStretch()
        center_widget = QWidget()
        center_widget.setLayout(center_panel)
        splitter.addWidget(center_widget)

        # Right Panel - Annotation List, Editor, Metadata display, Next/Prev
        self.annotation_list = QListWidget()
        self.annotation_list.itemClicked.connect(self.select_annotation)
        self.annotation_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.label_dropdown = QComboBox()
        self.label_dropdown.currentIndexChanged.connect(self.update_annotation)
        self.time_spinbox = QSpinBox()
        self.time_spinbox.setRange(0, 10_000_000)
        self.time_spinbox.setSingleStep(1000)
        self.time_spinbox.valueChanged.connect(self.update_annotation)
        self._updating_selection = False

        form_layout = QFormLayout()
        form_layout.addRow("Label", self.label_dropdown)
        form_layout.addRow("Timestamp (ms)", self.time_spinbox)

        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Next/Prev below the panel
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.go_to_previous_annotation)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.go_to_next_annotation)
        nav_buttons_layout = QHBoxLayout()
        nav_buttons_layout.addWidget(self.prev_button)
        nav_buttons_layout.addWidget(self.next_button)
        nav_buttons_layout.addStretch()

        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Annotations"))
        right_panel.addWidget(self.annotation_list)
        right_panel.addWidget(QLabel("Edit Annotation"))
        right_panel.addLayout(form_layout)
        right_panel.addWidget(QLabel("Metadata"))
        right_panel.addWidget(self.metadata_text)
        right_panel.addLayout(nav_buttons_layout)
        right_panel.addStretch()
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        splitter.addWidget(right_widget)

        splitter.setSizes([250, 1000, 350])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        main_layout.addWidget(splitter)

    def load_osl_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open OSL JSON File", "", "JSON Files (*.json)")
        if file_path:
            logging.info(f"Loading OSL JSON file: {file_path}")
            self.load_osl_json_from_file(file_path)

    def load_osl_json_from_file(self, file_path):
        file_path = os.path.abspath(file_path)
        self.video_list.clear()
        with open(file_path, 'r') as f:
            self.osl_data = json.load(f)
        logging.info(f"Loaded JSON with {len(self.osl_data.get('videos', []))} videos")

        self.available_labels = self.osl_data.get("labels", [])
        self.label_dropdown.clear()
        self.label_dropdown.addItems(self.available_labels)

        for video in self.osl_data.get("videos", []):
            path = video.get("path")
            item_text = f"{path} ({len(video.get('annotations', []))} events)"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, video)
            self.video_list.addItem(item)

        self.video_dir = os.path.dirname(file_path)

    def save_osl_json(self):
        if not self.osl_data:
            logging.warning("No data to save.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save OSL JSON File", "", "JSON Files (*.json)")
        if not file_path:
            logging.info("Save cancelled.")
            return
        with open(file_path, 'w') as f:
            json.dump(self.osl_data, f, indent=2)
        logging.info(f"Annotations saved to {file_path}")
        QMessageBox.information(self, "Saved", f"Annotations saved to {file_path}")

    def load_video(self, item):
        self.current_video_info = item.data(Qt.UserRole)
        self.current_video_path = os.path.join(self.video_dir, self.current_video_info.get("path"))
        self.current_annotations = self.current_video_info.get("annotations", [])
        self.current_annotation_index = None

        logging.info(f"Selected video: {self.current_video_path}")

        self.annotation_list.clear()
        for idx, ann in enumerate(self.current_annotations):
            timestamp = ann["position"] / 1000
            label = ann["label"]
            display = f"[{timestamp:.1f}s] {label}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, idx)
            self.annotation_list.addItem(item)

        if os.path.exists(self.current_video_path):
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(self.current_video_path)))
            self.player.play()
            self.play_button.setText("Pause")
            logging.info("Started video playback.")

    def select_annotation(self, item):
        idx = item.data(Qt.UserRole)
        self.current_annotation_index = idx
        ann = self.current_annotations[idx]

        # Prevent unwanted updates when programmatically setting values
        self._updating_selection = True

        self.label_dropdown.blockSignals(True)
        self.label_dropdown.setCurrentText(ann["label"])
        self.label_dropdown.blockSignals(False)

        self.time_spinbox.blockSignals(True)
        self.time_spinbox.setValue(ann["position"])
        self.time_spinbox.blockSignals(False)

        self._updating_selection = False

        # Show metadata as pretty-printed JSON in the QTextEdit
        if "metadata" in ann:
            pretty = json.dumps(ann["metadata"], indent=2, ensure_ascii=False)
            self.metadata_text.setText(pretty)
        else:
            self.metadata_text.setText("")

        self.player.setPosition(ann["position"])
        self.player.play()
        self.play_button.setText("Pause")
        logging.info(f"Selected annotation at idx={idx}, time={ann['position']}ms, label={ann['label']}")

    def update_annotation(self):
        # Avoid unwanted data update when programmatically changing selection
        if self.current_annotation_index is None or self._updating_selection:
            return
        new_label = self.label_dropdown.currentText()
        new_time = self.time_spinbox.value()
        ann = self.current_annotations[self.current_annotation_index]
        ann["label"] = new_label
        ann["position"] = new_time

        item = self.annotation_list.item(self.current_annotation_index)
        item.setText(f"[{new_time / 1000:.1f}s] {new_label}")

        logging.info(f"Updated annotation idx={self.current_annotation_index} to time={new_time}ms, label={new_label}")

    def toggle_play_pause(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_button.setText("Play")
            logging.info("Paused video.")
        else:
            self.player.play()
            self.play_button.setText("Pause")
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
            self.annotation_list.setCurrentRow(prev_idx)
            self.select_annotation(self.annotation_list.currentItem())
            logging.info(f"Jumped to previous annotation idx={prev_idx}.")

    def go_to_next_annotation(self):
        current_time = self.player.position()
        for i, ann in enumerate(self.current_annotations):
            if ann["position"] > current_time:
                self.annotation_list.setCurrentRow(i)
                self.select_annotation(self.annotation_list.currentItem())
                logging.info(f"Jumped to next annotation idx={i}.")
                break

    def update_slider(self, position):
        self.slider.blockSignals(True)
        duration = self.player.duration()
        if duration > 0:
            slider_value = int((position / duration) * 1000)
            self.slider.setValue(slider_value)
        self.time_label.setText(f"{ms_to_time(position)} / {ms_to_time(duration)}")
        self.highlight_current_annotation(position)
        self.slider.blockSignals(False)

    def highlight_current_annotation(self, position):
        for i, ann in enumerate(self.current_annotations):
            if abs(ann["position"] - position) < 500:
                self.annotation_list.setCurrentRow(i)
                logging.info(f"Highlighting annotation idx={i} at {position}ms.")
                break

    def update_duration(self, duration):
        self.slider.setValue(0)

    def seek_slider(self, value):
        duration = self.player.duration()
        if duration > 0:
            pos = int((value / 1000) * duration)
            self.player.setPosition(pos)
            self.time_label.setText(f"{ms_to_time(pos)} / {ms_to_time(duration)}")
            logging.info(f"Seeked video to {pos}ms.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="OSL Dataset Visualizer")
    parser.add_argument('--osl_file', type=str, help='Path to an OSL JSON file to preload')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    viewer = DatasetViewer()

    if args.osl_file:
        logging.info(f"Autoloading file from --osl_file: {args.osl_file}")
        viewer.load_osl_json_from_file(args.osl_file)

    viewer.show()
    sys.exit(app.exec_())
