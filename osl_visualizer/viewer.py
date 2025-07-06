import os
import os
import json
import logging

from PyQt6 import uic
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QInputDialog
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QSettings
from PyQt6.QtGui import QShortcut, QKeySequence

from models import VideoListModel, AnnotationListModel
from dialogs import ConfigDialog
from utils import ms_to_time, ms_to_hms_ms

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[logging.StreamHandler()]
)

class StatusBarHandler(logging.Handler):
    def __init__(self, status_bar):
        super().__init__()
        self.status_bar = status_bar

    def emit(self, record):
        msg = self.format(record)
        # Display message on status bar
        self.status_bar.showMessage(msg, 5000)  # Display for 5 seconds (5000 ms)

class DatasetViewer(QMainWindow):
    """Main window for the OSL Dataset Visualizer application."""
    def __init__(self):
        super().__init__()
        uic.loadUi(os.path.join(os.path.dirname(__file__), "ui/mainwindow.ui"), self)

        # Replace placeholder with QVideoWidget for video playback
        placeholder = self.videoWidgetPlaceholder
        layout = placeholder.parent().layout()
        self.videoWidget = QVideoWidget(self)
        layout.replaceWidget(placeholder, self.videoWidget)
        placeholder.deleteLater()
        self.videoWidget.setMinimumSize(300, 200)
        self.videoWidget.show()

        # Set Logging Configuration
        status_bar_handler = StatusBarHandler(self.statusBar)
        status_bar_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
        status_bar_handler.setFormatter(formatter)
        logging.getLogger().addHandler(status_bar_handler)

        # State variables
        self.osl_data = None
        self.current_video_info = None
        self.jump_before_ms = 5000
        self.last_osl_dir = ""

        # Multimedia
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.videoWidget)

        # Models
        self.videoModel = VideoListModel([])
        self.annotationModel = AnnotationListModel([])

        # Attach models to QListView widgets
        self.videoListView.setModel(self.videoModel)
        self.annotationListView.setModel(self.annotationModel)

        # Connect UI signals
        self._connect_signals()
        self._setup_shortcuts()
        self.load_settings()

    def _connect_signals(self):
        """Connects all UI widgets to their respective slots."""
        self.loadButton.clicked.connect(self.load_osl_json)
        self.saveButton.clicked.connect(self.save_osl_json)
        self.saveAsButton.clicked.connect(self.save_as_osl_json)
        self.videoListView.clicked.connect(self.on_video_selected)
        self.annotationListView.clicked.connect(self.on_annotation_selected)
        self.playButton.clicked.connect(self.toggle_play_pause)
        self.labelComboBox.currentIndexChanged.connect(self.update_annotation_label)
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
        self.addLabelButton.clicked.connect(self.add_label)
        self.removeLabelButton.clicked.connect(self.remove_label)
        self.actionOpen_Settings.triggered.connect(self.show_config_dialog)
        

    def _setup_shortcuts(self):
        """Sets up keyboard shortcuts for video controls and annotation."""
        QShortcut(QKeySequence("Space"), self).activated.connect(self.toggle_play_pause)
        QShortcut(QKeySequence("A"), self).activated.connect(self.add_annotation_at_current_time)
        QShortcut(QKeySequence("S"), self).activated.connect(self.set_annotation_time_to_video)
        QShortcut(QKeySequence("Left"), self).activated.connect(lambda: self.step_frame(-1))
        QShortcut(QKeySequence("Right"), self).activated.connect(lambda: self.step_frame(1))
        QShortcut(QKeySequence("Ctrl+Left"), self).activated.connect(lambda: self.step_video(-1000))
        QShortcut(QKeySequence("Ctrl+Right"), self).activated.connect(lambda: self.step_video(1000))
        QShortcut(QKeySequence("Ctrl+Shift+Left"), self).activated.connect(lambda: self.step_video(-5000))
        QShortcut(QKeySequence("Ctrl+Shift+Right"), self).activated.connect(lambda: self.step_video(5000))
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_osl_json)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.save_as_osl_json)

    # ---------- File Operations ----------

    def load_osl_json(self):
        """Open a file dialog to select and load an OSL JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open OSL JSON File", self.last_osl_dir, "JSON Files (*.json)")
        self.load_osl_json_from_file(file_path)
        
    def load_osl_json_from_file(self, file_path):
        """Load OSL JSON data from the specified file path."""
        if file_path:
            logging.info(f"Loading OSL JSON file: {file_path}")
            self.last_osl_dir = os.path.dirname(file_path)
            try:
                with open(file_path, 'r') as f:
                    self.osl_data = json.load(f)
                videos = self.osl_data.get("videos", [])
                self.videoModel.set_videos(videos)
                self.current_video_info = None
                self.annotationModel.set_annotations([])
                self.labelComboBox.clear()
                self.labelComboBox.addItems(self.osl_data.get("labels", []))
                self.save_settings()
                if hasattr(self, "player"):
                    self.player.stop()       # Stop playback (if running)
                    self.player.setSource(QUrl.fromLocalFile(""))
                self.file_path = file_path
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load JSON: {e}")

    def save_osl_json(self):
        """Save current OSL JSON data to currentfile."""
        ret = QMessageBox.question(
            self,
            "Save OSL JSON file",
            f"Are you sure you want to save the OSL JSON file to {self.file_path}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return  # Cancel saving

        if not self.osl_data:
            logging.warning("No data to save.")
            return
        self.save_osl_json_from_file(self.file_path)

    def save_as_osl_json(self):
        """Open a file dialog and save current OSL JSON data to file."""
        if not self.osl_data:
            logging.warning("No data to save.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save OSL JSON File", self.last_osl_dir, "JSON Files (*.json)")
        self.save_osl_json_from_file(file_path)

    def save_osl_json_from_file(self, file_path):
        """Save current OSL JSON data to file."""
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

    # ---------- Model/View Selection ----------

    def on_video_selected(self, index):
        """Load the selected video and its annotations."""
        video = self.videoModel.data(index, Qt.ItemDataRole.UserRole)
        self.current_video_info = video
        annotations = video.get("annotations", [])
        self.annotationModel.set_annotations(annotations)

        # Load video file
        video_rel_path = video.get("path")
        if os.path.isabs(video_rel_path):
            current_video_path = video_rel_path
        else:
            current_video_path = os.path.normpath(os.path.join(self.last_osl_dir, video_rel_path))

        if os.path.exists(current_video_path):
            self.player.setSource(QUrl.fromLocalFile(current_video_path))
            # self.player.play()
            # self.playButton.setText("Pause")
            # logging.info("Started video playback.")
        else:
            QMessageBox.warning(self, "File not found", f"Video file not found:\n{current_video_path}")

    def on_annotation_selected(self, index):
        """Select and display details for a specific annotation."""
        ann = self.annotationModel.data(index, Qt.ItemDataRole.UserRole)
        self.labelComboBox.blockSignals(True)
        self.labelComboBox.setCurrentText(ann["label"])
        self.labelComboBox.blockSignals(False)
        # self.annotationTimeLabel.setText(ms_to_hms_ms(ann["position"]))
        if "metadata" in ann:
            pretty = json.dumps(ann["metadata"], indent=2, ensure_ascii=False)
            self.metadataTextEdit.setText(pretty)
        else:
            self.metadataTextEdit.setText("")
        jump_to = max(0, ann["position"] - self.jump_before_ms)
        self.player.setPosition(jump_to)
        # self.player.play()
        # self.playButton.setText("Pause")
        logging.info(f"Selected annotation at time={ann['position']}ms, label={ann['label']}")

    # ---------- Annotation Editing ----------

    def update_annotation_label(self):
        """Update the label of the currently selected annotation."""
        idx = self.annotationListView.currentIndex().row()
        if idx < 0 or idx >= len(self.annotationModel.annotations):
            return
        ann = self.annotationModel.annotations[idx]
        ann["label"] = self.labelComboBox.currentText()
        self.annotationModel.dataChanged.emit(
            self.annotationModel.index(idx),
            self.annotationModel.index(idx)
        )

    def set_annotation_time_to_video(self):
        """Set the time of the current annotation to the current video position, resort and refresh."""
        idx = self.annotationListView.currentIndex().row()
        if idx < 0 or idx >= len(self.annotationModel.annotations):
            QMessageBox.warning(self, "No annotation selected", "Please select an annotation to update.")
            return
        current_time = int(self.player.position())
        ann = self.annotationModel.annotations[idx]
        ann["position"] = current_time
        # Resort
        anns = self.annotationModel.annotations
        anns.sort(key=lambda a: a["position"])
        self.annotationModel.set_annotations(anns)
        # Find new index
        for new_idx, a in enumerate(anns):
            if a is ann:
                self.annotationListView.setCurrentIndex(self.annotationModel.index(new_idx))
                # self.annotationTimeLabel.setText(ms_to_hms_ms(current_time))
                break

    def add_annotation_at_current_time(self):
        """Add a new annotation at the current video time in chronological order."""
        if not self.current_video_info:
            QMessageBox.warning(self, "No video", "Please select a video first.")
            return
        current_time = int(self.player.position())
        current_label = self.labelComboBox.currentText() # or (self.osl_data["labels"][0] if self.osl_data and "labels" in self.osl_data and self.osl_data["labels"] else "Event")
        new_annotation = {
            "position": current_time,
            "label": current_label,
            "metadata": {}
        }
        idx = self.annotationModel.add_annotation(new_annotation)
        self.current_video_info["annotations"] = self.annotationModel.annotations
        self.annotationListView.setCurrentIndex(self.annotationModel.index(idx))
        logging.info(f"Added annotation at {current_time}ms, label={current_label}")

    def remove_selected_annotation(self):
        """Remove the currently selected annotation from the list."""
        idx = self.annotationListView.currentIndex().row()
        if idx < 0 or idx >= len(self.annotationModel.annotations):
            QMessageBox.warning(self, "No Selection", "Please select an annotation to remove.")
            return
        ret = QMessageBox.question(
            self, "Remove Annotation",
            "Are you sure you want to remove the selected annotation?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        self.annotationModel.remove_annotation(idx)
        self.current_video_info["annotations"] = self.annotationModel.annotations
        logging.info(f"Removed annotation at idx={idx}")
    
    # ---------- Label Management ----------

    def add_label(self):
        text, ok = QInputDialog.getText(self, "Add Label", "Enter new label:")
        if ok and text.strip():
            if "labels" not in self.osl_data:
                self.osl_data["labels"] = []
            if text not in self.osl_data["labels"]:
                self.osl_data["labels"].append(text)
                self.labelComboBox.addItem(text)
                logging.info(f"Added label: {text}")
            else:
                QMessageBox.information(self, "Duplicate", f"Label '{text}' already exists.")

    def remove_label(self):
        label = self.labelComboBox.currentText()
        if not label:
            QMessageBox.warning(self, "No Selection", "No label selected.")
            return
        ret = QMessageBox.question(
            self, "Remove Label",
            f"Are you sure you want to remove the label '{label}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        if "labels" in self.osl_data and label in self.osl_data["labels"]:
            self.osl_data["labels"].remove(label)
            self.labelComboBox.removeItem(self.labelComboBox.currentIndex())
            logging.info(f"Removed label: {label}")
        else:
            QMessageBox.warning(self, "Error", f"Label '{label}' not found.")


    # ---------- Video Playback Controls ----------

    def toggle_play_pause(self):
        """Toggle play/pause state of the video."""
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.playButton.setText("Play")
            logging.info("Paused video.")
        else:
            self.player.play()
            self.playButton.setText("Pause")
            logging.info("Playing video.")

    def go_to_previous_annotation(self):
        """Go to the annotation before the current playback time."""
        pos = self.player.position()
        prev_idx = None
        for i, ann in enumerate(self.annotationModel.annotations):
            if ann["position"] < pos:
                prev_idx = i
            else:
                break
        if prev_idx is not None:
            self.annotationListView.setCurrentIndex(self.annotationModel.index(prev_idx))
            self.on_annotation_selected(self.annotationModel.index(prev_idx))

    def go_to_next_annotation(self):
        """Go to the annotation after the current playback time."""
        pos = self.player.position()
        for i, ann in enumerate(self.annotationModel.annotations):
            if ann["position"] > pos:
                self.annotationListView.setCurrentIndex(self.annotationModel.index(i))
                self.on_annotation_selected(self.annotationModel.index(i))
                break

    def update_slider(self, position):
        """Update the slider position and time display."""
        self.slider.blockSignals(True)
        duration = self.player.duration()
        if duration > 0:
            slider_value = int((position / duration) * 1000)
            self.slider.setValue(slider_value)
        self.timeLabel.setText(f"{ms_to_time(position)} / {ms_to_time(duration)}")
        # self.highlight_current_annotation(position)
        self.slider.blockSignals(False)

    # def highlight_current_annotation(self, position):
    #     """Highlight the annotation closest to the current playback position."""
    #     for i, ann in enumerate(self.annotationModel.annotations):
    #         if abs(ann["position"] - position) < 500:
    #             self.annotationListView.setCurrentIndex(self.annotationModel.index(i))
    #             break

    def update_duration(self, duration):
        """Reset the slider when video duration changes (e.g., new video loaded)."""
        self.slider.setValue(0)

    def seek_slider(self, value):
        """Seek the video to the position indicated by the slider."""
        duration = self.player.duration()
        if duration > 0:
            pos = int((value / 1000) * duration)
            self.player.setPosition(pos)
            self.timeLabel.setText(f"{ms_to_time(pos)} / {ms_to_time(duration)}")
            logging.info(f"Seeked video to {pos}ms.")

    # ---------- Video Stepping ----------

    def step_video(self, ms_delta):
        """Jump forward or backward by ms_delta milliseconds."""
        pos = self.player.position()
        duration = self.player.duration()
        new_pos = min(max(pos + ms_delta, 0), duration)
        self.player.setPosition(new_pos)

    def step_frame(self, direction):
        """Jump forward/backward by one frame (approx 40 ms at 25 FPS)."""
        frame_ms = 40  # Adjust for your FPS if needed
        self.step_video(frame_ms * direction)

    # ---------- Settings Persistence ----------

    def show_config_dialog(self):
        """Open the configuration/settings dialog for the user to change settings."""
        dialog = ConfigDialog(self, self.jump_before_ms)
        if dialog.exec():
            self.jump_before_ms = dialog.get_jump_before()
            self.save_settings()   # Persist!

    def save_settings(self):
        """Save persistent user settings using QSettings."""
        settings = QSettings("OSLActionSpotting", "DatasetAnnotationTool")
        settings.setValue("jump_before_ms", self.jump_before_ms)
        settings.setValue("last_osl_dir", self.last_osl_dir)

    def load_settings(self):
        """Load persistent user settings using QSettings."""
        settings = QSettings("OSLActionSpotting", "DatasetAnnotationTool")
        try:
            self.jump_before_ms = int(settings.value("jump_before_ms", 5000))
        except (TypeError, ValueError):
            self.jump_before_ms = 5000
        self.last_osl_dir = settings.value("last_osl_dir", "")
