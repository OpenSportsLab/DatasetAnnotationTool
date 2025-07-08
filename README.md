# OSL Dataset Visualizer

[![Documentation Status](https://img.shields.io/badge/docs-online-brightgreen)](https://opensportslab.github.io/DatasetAnnotationTool/)


This is a simple PyQt5-based visualizer for datasets in the OSL (Open Sports Lab) JSON format.

## Features

- Load and view OSL JSON files.
- Display dataset contents in a user-friendly interface.
- Easy to extend with visual overlays and timeline viewers.

---

## 🔧 Environment Setup

We recommend using [Anaconda](https://www.anaconda.com/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html) for managing your Python environment.

### Step 1 – Create a new Conda environment

```bash
conda create -n osl-visualizer python=3.9 -y
conda activate osl-visualizer
````

### Step 2 – Install dependencies

```bash
pip install pyqt6
```

Optionally, if you plan to add video rendering or computer vision:

```bash
pip install opencv-python
```

---

## 🚀 Run the Visualizer

From the root of the project folder, launch the app with:

```bash
python osl_visualizer/main.py
```

A window will open where you can load your OSL JSON files.


Tips: Download a dataset from HF and run the app with that dataset
```bash
python tools/download_osl_hf.py \
--url https://huggingface.co/datasets/OpenSportsLab/HistWC/blob/main/HistWC-finals.json \
--output-dir /Users/giancos/Documents/HistWC/
python osl_visualizer/main.py --osl_file /Users/giancos/Documents/HistWC/HistWC-finals.json
```

---

## 🚀 Run the Installer

This script is automatically called whenever you push to Github

```bash
pip install pyinstaller
```

pyinstaller --onefile --windowed main.py

---

## Build the docs

```bash 
pip install mkdocs mkdocs-material mkdocstrings[python]
mkdocs gh-deploy
```

---

## 📄 License

This project is open source and free to use under the MIT License.
