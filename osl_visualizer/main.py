import sys
import argparse
from PyQt6.QtWidgets import QApplication
from viewer import DatasetViewer

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OSL Dataset Visualizer")
    parser.add_argument('--osl_file', type=str, help='Path to an OSL JSON file to preload')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    viewer = DatasetViewer()

    if args.osl_file:
        viewer.load_osl_json_from_file(args.osl_file)

    viewer.show()
    sys.exit(app.exec())
