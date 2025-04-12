# GUI-Based Electric Field Simulation Automation Tool

A comprehensive automation tool for electric field calculation (Relax3d) using WIN32-based preprocessing and computation software.

## Environment Requirements

- **Operating System**: Windows 10 (required due to WIN32 software limitations)
- **Python Libraries**: See `requirements.txt` for the complete list of dependencies

## Project Structure

### Core Files

- `gui_controller.py` - Main graphical user interface application (formerly `gui.py`)
- `auto_relax3d.py` - Contains automated preprocessing and calculation functions for WIN32 software (formerly `_AutoRelax3D.py`)

### Configuration Files

- ```
  config_main.ini
  ```

   \- Defines working paths, output paths, and Relax3D input parameters (formerly 

  ```
  _config.ini
  ```

  )

  - `[Commands-L]` - Large area configuration commands
  - `[Commands-S]` - Small area configuration commands
  - Grid units: mm

- ```
  config_layers.yaml
  ```

   \- Configures layer heights and electrode voltage calibration (formerly 

  ```
  config.yaml
  ```

  )

  - Grid units: cm

### Utility Scripts

- `setup_compatibility.bat` - Modifies required WIN32 software (requires administrator privileges) (formerly `compat_change.bat`)
- `launch_with_admin.bat` - Automatically requests administrator privileges and launches the GUI interface (formerly `run_as_admin.bat`)

### Electrode Layer Files

- Naming convention: `L{number}.dxf` (e.g., `L1.dxf`, `L2.5.dxf`) representing Layer 1, Layer 2.5, etc.

## GUI Interface Guide

The GUI interface consists of two main pages and includes keyboard navigation:

- **Navigation**: Use Up/Down arrow keys to scroll through pages
- **Reset**: Press ESC to return to the initial layout

### Page 1: Combine.exe Automation

This page handles the automatic merging of preprocessed files.

1. **Input Selection**:
   - Select the output folder from the divide.exe preprocessing
2. **File Type Selection**:
   - `L` - Processes large area files (named `L{number}.txt`, e.g., `L1.txt`, `L2.5.txt`)
   - `S` - Processes small area files (named `S{number}.txt`, e.g., `S1.txt`, `S2.5.txt`)
3. **File Range Configuration**:
   - Set minimum and maximum range values to process specific file sets
   - Example: Setting S File Range Min:1 and Max:3 will process files with numbers between 1-3 (`S1.txt`, `S2.5.txt`, `S2.6.txt`, `S3.txt`)
4. **Output**:
   - Generates `relax3d.dat` with the first 3 lines automatically removed

### Page 2: Preprocessing and Electric Field Calculation

This page manages preprocessing automation and electric field calculations.

1. **Processing Options**:
   - Mode: Preview (`P`) or Run (`R`)
   - Area: Large area (`L`) or Small area (`S`) - grid divisions defined in `config_layers.yaml`
2. **Layer Selection**:
   - Automatically loads layer names from `config_layers.yaml` (e.g., `L5` for Layer 5)
   - Navigate using arrow keys (Up/Down or Left/Right)
   - Layer information appears in the Selection Information panel
3. **Layer Modification**:
   - Edit layer height and potential markers in the Selection Information area
   - Save changes by pressing Enter in the Potentials input field
   - Process the selected layer by pressing Enter or using the "Process Selected Layer"/"Process Single File" buttons
4. **Additional Processing**:
   - Relax3D calculation automation (parameters in `config_main.ini`)
   - Large area calculation: Press `L` button
   - Small area calculation: Press `S` button
   - Change output filenames by entering a Label to modify names with format `{current_date}{Label}`
5. **Logging**:
   - All process information displays in the Log panel

## Installation and Setup

1. Clone this repository

2. Install required Python libraries:

   ```
   pip install -r requirements.txt
   ```

   or run `pip_install_dependencies.bat`

3. Run `setup_compatibility.bat` with administrator privileges to configure the WIN32 software

4. Launch the application using `launch_with_admin.bat`

## File Naming Conventions

This project uses the following file naming conventions:

- **Electrode Layer Files**: `L{number}.dxf` (e.g., `L1.dxf`, `L2.5.dxf`) representing Layer 1, Layer 2.5, etc.

- Processed Files

  :

  - Large area: `L{number}.txt` (e.g., `L1.txt`, `L2.5.txt`)
  - Small area: `S{number}.txt` (e.g., `S1.txt`, `S2.5.txt`)

- Configuration Files

  : Prefix with 

  ```
  config_
  ```

   for clarity

  - `config_main.ini` (formerly `_config.ini`)
  - `config_layers.yaml` (formerly `config.yaml`)

- Core Scripts

  : Descriptive lowercase names with underscores

  - `gui_controller.py` (formerly `gui.py`)
  - `auto_relax3d.py` (formerly `_AutoRelax3D.py`)

- Utility Scripts

  : Verb-noun format for action scripts

  - `setup_compatibility.bat` (formerly `compat_change.bat`)
  - `pip_install_dependencies.bat`
  - `launch_with_admin.bat` (formerly `run_as_admin.bat`)

## License

This software is intended for internal use within our team only. All rights reserved.

### Third-Party Libraries

This project uses the following third-party libraries, each with their own licenses:

- **pyautogui**: BSD 3-Clause License
- **psutil**: BSD 3-Clause License
- **PyQt5**: GPL v3 License
- **pywin32**: Python Software Foundation License
- **PyYAML**: MIT License

If redistributing this software, please comply with the terms of all included third-party licenses, particularly the GPL v3 License of PyQt5 which requires derivative works to also be licensed under GPL v3.

*Note: For internal team use only. Not for redistribution or public use without permission.*

## Contact

[[Yukichoas@gmail.com](mailto:Yukichoas@gmail.com)]