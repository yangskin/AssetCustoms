"""
Test script: verify PySide6 + unreal_qt integration.
Creates a simple Qt message box with an OK button inside UE Editor.
"""
import unreal
import importlib
import unreal_qt
importlib.reload(unreal_qt)
from PySide6 import QtWidgets

# Ensure QApplication is initialized
unreal_qt.setup()

# Create a message box
msg = QtWidgets.QMessageBox()
msg.setWindowTitle("PySide6 Test")
msg.setText("PySide6 is working inside Unreal Editor!")
msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
msg.show()

# Let unreal_qt manage the widget lifetime and parent it to Slate
unreal_qt.wrap(msg)

unreal.log("test_qt_messagebox: QMessageBox shown successfully")
