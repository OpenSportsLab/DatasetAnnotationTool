import os
import json
from PyQt6 import uic
from PyQt6.QtWidgets import QDialog, QMessageBox
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings

class ConfigDialog(QDialog):
    """Configuration dialog for user settings."""
    def __init__(self, parent=None, current_jump_before=5000):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "ui/configdialog.ui"), self)
        self.jumpBeforeSpinBox.setValue(current_jump_before)
        self.okButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

    def get_jump_before(self):
        """Return the currently set 'jump before annotation' value."""
        return self.jumpBeforeSpinBox.value()


class DownloadThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    cancelled_signal = pyqtSignal()

    def __init__(self, api_key, osl_json_url, output_dir, dry_run=True):
        super().__init__()
        self.api_key = api_key
        self.osl_json_url = osl_json_url
        self.output_dir = output_dir
        self.dry_run = dry_run
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        try:
            from huggingface_hub import hf_hub_download, HfApi, HfFolder
            from urllib.parse import urlparse

            HfFolder.save_token(self.api_key)

            def human_size(num):
                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                    if num < 1024.0:
                        return f"{num:3.1f} {unit}"
                    num /= 1024.0
                return f"{num:.1f} PB"

            def fix_hf_url(hf_url):
                return hf_url.replace("/blob/", "/resolve/")

            def parse_hf_url(hf_url):
                url = fix_hf_url(hf_url)
                parsed = urlparse(url)
                parts = parsed.path.strip("/").split("/")
                if "datasets" in parts:
                    datasets_idx = parts.index("datasets")
                    parts = parts[datasets_idx + 1:]
                if len(parts) < 4 or parts[2] != "resolve":
                    raise ValueError(f"URL does not look like a valid HuggingFace dataset file URL: {url}")
                repo_id = f"{parts[0]}/{parts[1]}"
                revision = parts[3]
                path_in_repo = "/".join(parts[4:])
                return repo_id, revision, path_in_repo

            def get_json_repo_folder(path_in_repo):
                folder = os.path.dirname(path_in_repo)
                return folder if folder and folder != '.' else ''

            repo_id, revision, path_in_repo = parse_hf_url(self.osl_json_url)
            repo_json_folder = get_json_repo_folder(path_in_repo)

            self.log_signal.emit(f"⬇️ Downloading OSL JSON from {repo_id}@{revision}: {path_in_repo}")
            os.makedirs(self.output_dir, exist_ok=True)
            hf_json_path = hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename=path_in_repo,
                revision=revision,
                local_dir=self.output_dir,
                local_dir_use_symlinks=False,
            )
            self.log_signal.emit(f"  → Saved as {hf_json_path}")

            # Load OSL JSON and extract video paths
            with open(hf_json_path, "r") as f:
                osl = json.load(f)
            videos = osl.get("videos", [])
            self.log_signal.emit(f"Found {len(videos)} video files to download.")

            repo_paths = [video["path"].lstrip("/") for video in videos]
            def repo_full_path(rel_path):
                if repo_json_folder and not rel_path.startswith(repo_json_folder + "/"):
                    return os.path.join(repo_json_folder, rel_path)
                return rel_path
            allow_patterns = sorted(set([repo_full_path(rel_path) for rel_path in repo_paths]))

            if self.dry_run:
                # DRY RUN LOGIC
                try:
                    api = HfApi()
                    info_obj = api.repo_info(repo_id=repo_id, revision=revision, repo_type="dataset", files_metadata=True)
                    size_lookup = {f.rfilename: f.size for f in info_obj.siblings}
                except Exception as e:
                    self.log_signal.emit(f"[ERROR] Could not fetch repo files info: {e}")
                    size_lookup = {}

                total_size = 0
                missing_files = []
                for full_repo_path in allow_patterns:
                    size = size_lookup.get(full_repo_path)
                    if size is not None:
                        size_str = human_size(size)
                        total_size += size
                    else:
                        size_str = "Not found"
                        missing_files.append(full_repo_path)
                    self.log_signal.emit(f"[DRY RUN] {full_repo_path}: {size_str}")
                self.log_signal.emit("-" * 48)
                self.log_signal.emit(f"Total estimated storage needed: {human_size(total_size)}")
                if missing_files:
                    self.log_signal.emit(f"WARNING: {len(missing_files)} files not found in repo!")
                    for f in missing_files:
                        self.log_signal.emit(f"  - {f}")
                self.progress_signal.emit(100)
                self.finished_signal.emit()
                return

            # Download logic (per-file, so we can check for cancel)
            total_files = len(allow_patterns)
            downloaded = 0

            def progress_callback():
                nonlocal downloaded
                downloaded += 1
                percent = int((downloaded / total_files) * 100)
                self.progress_signal.emit(percent)

            self.log_signal.emit(f"Downloading {len(allow_patterns)} files using hf_hub_download...")
            self.progress_signal.emit(0)

            for allow_pattern in allow_patterns:
                if self._stop_requested:
                    self.log_signal.emit("Download cancelled by user.")
                    self.finished_signal.emit()
                    return
                self.log_signal.emit(f"Downloading {allow_pattern}...")
                hf_hub_download(
                    repo_id=repo_id,
                    repo_type="dataset",
                    filename=allow_pattern,
                    revision=revision,
                    local_dir=self.output_dir,
                    local_dir_use_symlinks=False,
                )
                progress_callback()

        except Exception as e:
            self.log_signal.emit(f"[ERROR] {e}")

        self.finished_signal.emit()


class DownloaderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "ui", "downloaderdialog.ui"), self)

        settings = QSettings("OSLActionSpotting", "DatasetAnnotationTool/Downloader")
        self.hf_api_key = settings.value("hf_api_key", "")
        self.url = settings.value("url", "")
        self.output_dir = settings.value("output_dir", "")

        self.lineEditApiKey.setText(self.hf_api_key)
        self.lineEditUrl.setText(self.url)
        self.lineEditOutputDir.setText(self.output_dir)

        self.lineEditApiKey.textChanged.connect(lambda: setattr(self, 'hf_api_key', self.lineEditApiKey.text().strip()))
        self.lineEditUrl.textChanged.connect(lambda: setattr(self, 'url', self.lineEditUrl.text().strip()))
        self.lineEditOutputDir.textChanged.connect(lambda: setattr(self, 'output_dir', self.lineEditOutputDir.text().strip()))

        self.pushButtonDownload.clicked.connect(self.start_download)
        self.pushButtonCancel.clicked.connect(self.on_cancel)
        self.pushButtonExit.clicked.connect(self.close)

    def start_download(self):
        api_key = self.lineEditApiKey.text().strip()
        url = self.lineEditUrl.text().strip()
        outdir = self.lineEditOutputDir.text().strip()
        dry_run = self.checkBoxDryRun.isChecked()
        if not api_key or not url:
            QMessageBox.warning(self, "Missing input", "Please provide both API key and OSL JSON URL.")
            return

        self.textEditLog.clear()
        self.progressBar.setValue(0)
        self.pushButtonDownload.setEnabled(False)
        self.pushButtonExit.setEnabled(False)

        self.worker = DownloadThread(api_key, url, outdir, dry_run)
        self.worker.log_signal.connect(self.textEditLog.append)
        self.worker.progress_signal.connect(self.progressBar.setValue)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.cancelled_signal.connect(self.on_cancel)
        self.worker.start()

    def on_finished(self):
        self.pushButtonDownload.setEnabled(True)
        self.pushButtonCancel.setEnabled(True)
        self.pushButtonExit.setEnabled(True)
        QMessageBox.information(self, "Done", "Download finished!")

    def on_cancel(self):
        if hasattr(self, "worker") and self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.textEditLog.append("Cancelling download… (the current file must finish downloading before stopping)")
            self.textEditLog.append("You can exit the downloader tool, but the download of the last video will continue in the background.")
            self.pushButtonCancel.setEnabled(False)
            self.pushButtonExit.setEnabled(True)
        else:
            self.reject()  # Close the dialog if worker is not running

    def closeEvent(self, event):
        settings = QSettings("OSLActionSpotting", "DatasetAnnotationTool/Downloader")
        settings.setValue("hf_api_key", self.hf_api_key)
        settings.setValue("url", self.url)
        settings.setValue("output_dir", self.output_dir)
