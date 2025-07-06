from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex
from utils import ms_to_hms_ms

class VideoListModel(QAbstractListModel):
    def __init__(self, videos=None):
        super().__init__()
        self.videos = videos or []

    def rowCount(self, parent=QModelIndex()):
        return len(self.videos)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self.videos)):
            return None
        video = self.videos[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            path = video.get("path", "unknown")
            n_events = len(video.get("annotations", []))
            return f"{path} ({n_events} events)"
        if role == Qt.ItemDataRole.UserRole:
            return video
        return None

    def set_videos(self, videos):
        self.beginResetModel()
        self.videos = videos or []
        self.endResetModel()

class AnnotationListModel(QAbstractListModel):
    def __init__(self, annotations=None):
        super().__init__()
        self.annotations = annotations or []

    def rowCount(self, parent=QModelIndex()):
        return len(self.annotations)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self.annotations)):
            return None
        ann = self.annotations[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"[{ms_to_hms_ms(ann['position'])}] {ann['label']}"
        if role == Qt.ItemDataRole.UserRole:
            return ann
        return None

    def set_annotations(self, annotations):
        self.beginResetModel()
        self.annotations = annotations or []
        self.endResetModel()

    def add_annotation(self, annotation):
        idx = 0
        while idx < len(self.annotations) and annotation["position"] > self.annotations[idx]["position"]:
            idx += 1
        self.beginInsertRows(QModelIndex(), idx, idx)
        self.annotations.insert(idx, annotation)
        self.endInsertRows()
        return idx

    def remove_annotation(self, idx):
        self.beginRemoveRows(QModelIndex(), idx, idx)
        del self.annotations[idx]
        self.endRemoveRows()
