import os
from PyQt6 import uic
from PyQt6.QtWidgets import QDialog

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
