# Installation

## Requirements

- Python 3.8 or later
- [PyQt5](https://pypi.org/project/PyQt5/)
- [OpenCV](https://pypi.org/project/opencv-python/)
- Other requirements listed in `requirements.txt` (if present)

## Setup Steps

1. **Clone the repository:**
    ```bash
    git clone https://github.com/OpenSportsLab/DatasetAnnotationTool.git
    cd DatasetAnnotationTool
    ```

2. **(Optional) Create a virtual environment:**
    ```bash
    python -m venv osl-visualizer
    source osl-visualizer/bin/activate
    ```

3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Run the application:**
    ```bash
    python osl_visualizer/main.py
    ```

## Troubleshooting

- If you have issues with Qt or video playback, check [Troubleshooting](troubleshooting.md).
