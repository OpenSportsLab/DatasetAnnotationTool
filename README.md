# OSL Dataset Visualizer

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
pip install PyQt5
```

Optionally, if you plan to add video rendering or computer vision:

```bash
pip install opencv-python
```

---

## 🚀 Run the Visualizer

From the root of the project folder, launch the app with:

```bash
python main.py
```

A window will open where you can load your OSL JSON files.

---

## 📄 License

This project is open source and free to use under the MIT License.
