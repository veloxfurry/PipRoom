# PIPROOM — Python Package Manager

<p align="center">
  <img src="assets/piproom-mark.svg" alt="PIPROOM logo" width="120">
</p>

<p align="center">
  **A simple desktop interface for managing Python packages.**
</p>

PIPROOM is a lightweight Python package manager with a graphical interface built using **CustomTkinter**. It makes installing and updating Python libraries easier without having to type pip commands manually.

## Features

- **Install packages** — install one or multiple Python packages.
- **Version selection** — install a specific version, for example `pandas==2.2.3`.
- **Update packages** — upgrade packages that are already installed.
- **Update pip** — keep the package installer up to date.
- **Installation progress** — monitor package installation activity.
- **Live output log** — view pip output directly inside the application.
- **Quick package buttons** — quickly enter popular Python libraries.
- **Python environment visibility** — see the exact Python executable used for installations.
- **Command copying** — copy a command to list packages installed in the active Python environment.

## Interface

PIPROOM features a dark graphite interface with an ocean-blue accent and a custom application logo.

## Requirements

- Windows
- Python 3
- CustomTkinter 5.2.2 or newer

## Installation

### Option 1 — Run from source

1. Clone the repository:

   ```bash
   git clone https://github.com/veloxfurry/PipRoom.git
   ```

2. Open the project folder.

3. Run the launcher:

   ```bat
   run_windows.bat
   ```

The launcher checks for Python, installs the required CustomTkinter dependency if needed, and starts PIPROOM.

### Option 2 — Install dependencies manually

```bash
py -m pip install -r requirements.txt
```

Then start the application:

```bash
py py_library_manager.py
```

## How package installation works

PIPROOM runs pip through the Python interpreter currently used by the application:

```python
sys.executable -m pip install PACKAGE_NAME
```

This helps ensure that packages are installed into the same Python environment that PIPROOM is using.

**Note:** If you have multiple Python versions installed, packages may be installed into a different environment than the one used by another terminal or application.

## Project Structure

```text
PipRoom/
├── assets/
│   └── piproom-mark.svg
├── py_library_manager.py
├── requirements.txt
├── run_windows.bat
└── README.md
```

## Built With

- [Python](https://www.python.org/)
- [CustomTkinter](https://customtkinter.tomschimansky.com/)
- [pip](https://pip.pypa.io/)

## Platform Support

PIPROOM is currently designed for **Windows**.

## License

No license has been specified yet. All rights remain with the project owner unless a license is added to this repository.
