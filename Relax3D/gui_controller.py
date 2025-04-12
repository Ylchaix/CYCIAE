import sys
import os
import yaml
import subprocess
# Import existing script
import auto_relax3d
# Set up logging
import win32gui
import win32api
import win32con
import time         
import shutil
import select 
import configparser
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
# from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
#                              QHBoxLayout, QLabel, QComboBox, QLineEdit, 
#                              QPushButton, QRadioButton, QButtonGroup, QFileDialog,
#                              QGroupBox, QMessageBox, QListWidget, QCheckBox, QGridLayout)
# from PyQt5.QtCore import Qt, QThread, pyqtSignal
# from PyQt5.QtGui import QFont, QIcon, QKeyEvent
import logging
# ---------------------------------------------------------------------------- #
# Set up logging & load_config 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FormattedLogHandler(logging.Handler):
    """Custom log handler that applies emoji formatting"""
    def __init__(self):
        super().__init__()
        
    def emit(self, record):
        # Format the message based on level/content
        msg = self.format(record)
        # This formatter will be called by both console logging and widget logging
        
class EmojiFormatter(logging.Formatter):
    """Custom formatter that adds emoji prefixes based on log level and content"""
    def format(self, record):
        # Get the original message
        msg = super().format(record)
        
        # Extract just the message part without timestamp and level
        # This depends on your format but typically we can extract after the last ' - '
        if ' - ' in msg:
            message_part = msg.split(' - ')[-1]
        else:
            message_part = msg
            
        # Add emoji based on level and content
        if record.levelno >= logging.ERROR or "error" in message_part.lower():
            return msg.replace(message_part, f"❌ {message_part}")
        elif record.levelno >= logging.WARNING or "warning" in message_part.lower():
            return msg.replace(message_part, f"⚠️ {message_part}")
        elif "completed" in message_part.lower() or "success" in message_part.lower():
            return msg.replace(message_part, f"✅ {message_part}")
        elif "cpu usage" in message_part.lower():
            # Special handling for CPU messages
            try:
                percentage = float(message_part.split("Current CPU usage:")[1].split("%")[0].strip())
                if percentage < 5:
                    return msg.replace(message_part, f"⚡ CPU IDLE: {percentage}%")
                elif percentage > 80:
                    return msg.replace(message_part, f"🔥 HIGH CPU: {percentage}%")
                else:
                    return msg.replace(message_part, f"⚙️ CPU: {percentage}%")
            except:
                return msg.replace(message_part, f"🔹 {message_part}")
        else:
            return msg.replace(message_part, f"🔹 {message_part}")

def load_config(config_file: str) -> configparser.ConfigParser:
    """Load and return the configuration from the specified file."""
    config = configparser.ConfigParser()
    config.read(config_file)
    return config
# ---------------------------------------------------------------------------- #

# Custom QTextEdit-based logger
class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.NoWrap)
        font = QFont("Courier New", 9)
        self.setFont(font)
        self.setStyleSheet("background-color: #F8F8F8;")
        
    def append_log(self, message, level=logging.INFO):
        """Add a new log entry with timestamp and appropriate formatting"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Color-code based on log level
        if level == logging.ERROR:
            html_message = f'<span style="color: red;">[{timestamp}] ERROR: {message}</span>'
        elif level == logging.WARNING:
            html_message = f'<span style="color: orange;">[{timestamp}] WARNING: {message}</span>'
        elif level == logging.INFO:
            html_message = f'<span style="color: blue;">[{timestamp}] {message}</span>' # INFO: {message}</span>
        else:
            html_message = f'<span style="color: black;">[{timestamp}] {message}</span>'
            
        self.append(html_message)
        # Auto-scroll to the bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

# Custom handler for Python's logging module
class QTextEditLogger(logging.Handler):
    def __init__(self, log_widget):
        super().__init__()
        self.log_widget = log_widget
        self.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        
    def emit(self, record):
        msg = self.format(record)
        self.log_widget.append_log(msg, record.levelno)

class SliceListWidget(QListWidget):
    """Custom list widget with keyboard navigation and enter key processing for slices"""
    enterPressed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SingleSelection)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard navigation and Enter key"""
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
            current_row = self.currentRow()
            total_rows = self.count()
            
            if event.key() == Qt.Key_Up and current_row > 0:
                self.setCurrentRow(current_row - 1)
            elif event.key() == Qt.Key_Down and current_row < total_rows - 1:
                self.setCurrentRow(current_row + 1)
            elif event.key() == Qt.Key_Left and current_row > 0:
                self.setCurrentRow(current_row - 1)
            elif event.key() == Qt.Key_Right and current_row < total_rows - 1:
                self.setCurrentRow(current_row + 1)
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            current_item = self.currentItem()
            if current_item:
                self.enterPressed.emit(current_item.text())
        else:
            super().keyPressEvent(event)

class AutoPre3DThread(QThread):
    """Thread for running AutoPre3D operations to keep UI responsive"""
    finished = pyqtSignal()
    log_message = pyqtSignal(str)
    
    def __init__(self, mode, filename, option):
        QThread.__init__(self)
        self.mode = mode
        self.filename = filename
        self.option = option
        
    def run(self):
        try:
            self.log_message.emit(f"Starting task with mode: {self.mode}, file: {self.filename}, option: {self.option}")
            auto_pre3d = auto_relax3d.AutoPre3D(self.mode)
            auto_pre3d.run(self.filename, self.option)
            self.log_message.emit("Task completed successfully")
        except Exception as e:
            self.log_message.emit(f"Error: {str(e)}")
        finally:
            self.finished.emit()

class AutoRe3DThread(QThread):
    """Thread for running AutoRe3D operations"""
    finished = pyqtSignal()
    log_message = pyqtSignal(str)  # Changed back to just emitting the raw message
    
    def __init__(self, option):
        QThread.__init__(self)
        self.option = option
        self.should_terminate = False
        self.auto_re3d = None  # Will hold our AutoRe3D instance
        
    def run(self):
        try:
            self.log_message.emit(f"Starting Relax3D automation with option: {self.option}")
            
            # Create the AutoRe3D instance
            self.auto_re3d = auto_relax3d.AutoRe3D()
            
            # Set up logging handler to capture and redirect logs
            self._setup_logging()
            
            # Run the task
            self.log_message.emit(f"Running Relax3D with option: {self.option}")
            result = self.auto_re3d.run_relax2000_task(self.option)
            
            if result:
                self.log_message.emit("Relax3D automation completed successfully")
            else:
                if self.should_terminate:
                    self.log_message.emit("Relax3D automation was terminated by user")
                else:
                    self.log_message.emit("Relax3D automation failed to complete")
                    
        except Exception as e:
            self.log_message.emit(f"Error running Relax3D automation: {str(e)}")
        finally:
            # Cleanup
            self._cleanup_logging()
            
            # Signal that we're done
            self.finished.emit()
    
    def _setup_logging(self):
        """Set up a custom logging handler to capture logs from AutoRe3D"""
        # Create a custom handler to capture log messages
        self.log_handler = CustomLogHandler(self)
        
        # Configure the handler
        self.log_handler.setLevel(logging.INFO)
        
        # Add the handler to the root logger
        logging.getLogger().addHandler(self.log_handler)
    
    def _cleanup_logging(self):
        """Clean up the custom logging handler"""
        if hasattr(self, 'log_handler'):
            logging.getLogger().removeHandler(self.log_handler)
    
    def request_termination(self):
        """Request termination of the automation task"""
        self.should_terminate = True
        self.log_message.emit("Process termination requested")
        
        # Forward termination request to the AutoRe3D instance
        if self.auto_re3d:
            self.auto_re3d.terminate()


class CustomLogHandler(logging.Handler):
    """Custom logging handler to redirect logs to QThread signals"""
    
    def __init__(self, thread):
        super().__init__()
        self.thread = thread
    
    def emit(self, record):
        """Process a log record by sending it through the thread's signal"""
        try:
            # Just emit the raw message without any formatting
            msg = record.getMessage()
            self.thread.log_message.emit(msg)
        except Exception as e:
            # In case of error, try to emit an error message
            try:
                self.thread.log_message.emit(f"Error in log handler: {str(e)}")
            except:
                pass  # If that fails too, just give up

class ChangeFileNameThread(QThread):
    """Thread for running file renaming operations"""
    finished = pyqtSignal()
    log_message = pyqtSignal(str, int)  # Changed to emit both message and log level
    
    def __init__(self, model_type, label):
        QThread.__init__(self)
        self.model_type = model_type  # 'L' or 'S'
        self.label = label
        
    def run(self):
        config = load_config('config_main.ini')
        try:
            self.log_message.emit(f"🔹 Starting file renaming with model type: {self.model_type}, label: {self.label}", logging.INFO)

            # Get current date in MMDD format
            current_date = datetime.now().strftime("%m%d")
            
            # Use the thread parameters instead of environment variables
            Model = self.model_type
            Label = self.label
            cyclotron_type = config.get('Paths', 'CYCLOTRON_TYPE')
            # Define the target directory
            target_directory = config.get('Paths', 'TARGET_OUTPUT_PATH')
            
            # Log parameters for debugging
            self.log_message.emit(f"🔹 Using Model: {Model}, Label: {Label}, Date: {current_date}", logging.INFO)
            
            # Define the file mappings
            file_mappings = {
                "RELAX3D_V.OUT": f"cyc_{cyclotron_type}_C{Model}{current_date}{Label}.efld",
                "convert.dat": f"cyc_{cyclotron_type}_C{Model}{current_date}{Label}.head"
            }
            
            
            # Create the target directory if it doesn't exist
            os.makedirs(target_directory, exist_ok=True)
            
            # Rename and move the files
            for old_name, new_name in file_mappings.items():
                if os.path.exists(old_name):
                    # Rename the file
                    os.rename(old_name, new_name)
                    self.log_message.emit(f"🔹 Renamed '{old_name}' to '{new_name}'", logging.INFO)
                    
                    # Move the file to the target directory
                    target_path = os.path.join(target_directory, new_name)
                    shutil.move(new_name, target_path)
                    self.log_message.emit(f"🔹 Moved '{new_name}' to '{target_path}'", logging.INFO)
                else:
                    self.log_message.emit(f"❌ File '{old_name}' not found in the current directory", logging.ERROR)
            
            self.log_message.emit(f"✅ File renaming and moving completed.", logging.INFO)
                    
        except Exception as e:
            self.log_message.emit(f"❌ Error running file renaming operations: {str(e)}", logging.ERROR)
        finally:
            self.finished.emit()

class AutoRelax3D(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setup_logging()
        self.load_config()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("AutoPre3D Controller")
        self.setGeometry(300, 300, 900, 700)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        self.setCentralWidget(main_widget)
        main_widget.setLayout(main_layout)
        
        # Create a splitter for main content and log
        self.main_splitter = QSplitter(Qt.Vertical)
        
        # Create top content widget
        top_content = QWidget()
        top_layout = QVBoxLayout(top_content)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create top section with two columns
        control_layout = QHBoxLayout()
        
        # Left column - Slice selection
        left_column = QVBoxLayout()
        slice_group = QGroupBox("Layer Selection")
        slice_layout = QVBoxLayout()
        
        # Instructions label
        instructions = QLabel("Select layer to process:")
        instructions1 = QLabel("(use arrow keys to navigate, press Enter to process)")
        slice_layout.addWidget(instructions)
        slice_layout.addWidget(instructions1)
        
        # List widget for slices
        self.slice_list = SliceListWidget()
        self.slice_list.setMinimumHeight(200)
        self.slice_list.itemSelectionChanged.connect(self.update_selection_info)
        self.slice_list.enterPressed.connect(self.process_selected_layer)
        slice_layout.addWidget(self.slice_list)
        
        slice_group.setLayout(slice_layout)
        left_column.addWidget(slice_group)
        
        # Single file processing (keeping the browse option)
        single_file_group = QGroupBox("Single File Processing")
        single_file_layout = QHBoxLayout()
        
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select .dxf file")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_file)
        
        single_file_layout.addWidget(self.file_input)
        single_file_layout.addWidget(browse_button)
        single_file_group.setLayout(single_file_layout)
        left_column.addWidget(single_file_group)
        
        # Right column - Selected file information and options
        right_column = QVBoxLayout()
        
        # Selection information
        info_group = QGroupBox("Selection Information")
        info_layout = QFormLayout()  # Changed to FormLayout for better alignment
        
        # Layer name (read-only)
        self.layer_label = QLabel("Layer:")
        self.layer_value = QLabel("No layer selected")
        info_layout.addRow(self.layer_label, self.layer_value)
        
        # Z-Min (editable)
        self.zmin_label = QLabel("Z-Min:")
        self.zmin_input = QLineEdit()
        self.zmin_input.setValidator(QDoubleValidator())  # Only accept numeric values
        info_layout.addRow(self.zmin_label, self.zmin_input)
        
        # Z-Max (editable)
        self.zmax_label = QLabel("Z-Max:")
        self.zmax_input = QLineEdit()
        self.zmax_input.setValidator(QDoubleValidator())  # Only accept numeric values
        info_layout.addRow(self.zmax_label, self.zmax_input)
        
        # Potentials (editable)
        self.potentials_label = QLabel("Potentials:")
        self.potentials_input = QLineEdit()
        self.potentials_input.setPlaceholderText("Comma-separated integers")
        # Connect enter key press to save function
        self.potentials_input.returnPressed.connect(self.save_slice_changes)
        info_layout.addRow(self.potentials_label, self.potentials_input)
        
        # Save button for changes
        self.save_info_button = QPushButton("Save Changes")
        self.save_info_button.clicked.connect(self.save_slice_changes)
        info_layout.addRow("", self.save_info_button)
        
        # Initially disable the editing fields until a slice is selected
        self.enable_slice_editing(False)
        
        info_group.setLayout(info_layout)
        right_column.addWidget(info_group)
        
        # Option selection
        option_group = QGroupBox("Processing Options")
        option_layout = QGridLayout()
        
        # Mode selection
        mode_label = QLabel("Mode:")
        self.preview_radio = QRadioButton("Preview (P)")
        self.run_radio = QRadioButton("Run (R)")
        self.run_radio.setChecked(True)  # Default option
        
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.preview_radio, 1)
        self.mode_group.addButton(self.run_radio, 2)
        
        # Field selection
        field_label = QLabel("Field Type:")
        self.large_radio = QRadioButton("Large Field (L)")
        self.small_radio = QRadioButton("Small Field (S)")
        self.large_radio.setChecked(True)  # Default option
        
        self.field_group = QButtonGroup()
        self.field_group.addButton(self.large_radio, 1)
        self.field_group.addButton(self.small_radio, 2)
        
        option_layout.addWidget(mode_label, 0, 0)
        option_layout.addWidget(self.preview_radio, 0, 1)
        option_layout.addWidget(self.run_radio, 0, 2)
        option_layout.addWidget(field_label, 1, 0)
        option_layout.addWidget(self.large_radio, 1, 1)
        option_layout.addWidget(self.small_radio, 1, 2)
        
        option_group.setLayout(option_layout)
        right_column.addWidget(option_group)
        
        # Add columns to control layout
        control_layout.addLayout(left_column, 1)
        control_layout.addLayout(right_column, 1)
        
        # Add control layout to top layout
        top_layout.addLayout(control_layout)
        
        # Additional processing options
        additional_options_group = QGroupBox("Additional Processing")
        additional_options_layout = QGridLayout()
        # ---------------------------------------------------------------------------- #
        # AutoRe3D options
        auto_re3d_label = QLabel("Run AutoRe3D:")
        self.auto_re3d_large_btn = QPushButton("Large Field (L)")
        self.auto_re3d_large_btn.clicked.connect(lambda: self.run_auto_re3d('L'))
        self.auto_re3d_small_btn = QPushButton("Small Field (S)")
        self.auto_re3d_small_btn.clicked.connect(lambda: self.run_auto_re3d('S'))
        
        # Add termination button
        self.terminate_auto_re3d_btn = QPushButton("Terminate AutoRe3D")
        self.terminate_auto_re3d_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.terminate_auto_re3d_btn.clicked.connect(self.terminate_auto_re3d)
        self.terminate_auto_re3d_btn.setEnabled(False)  # Initially disabled
        # ---------------------------------------------------------------------------- #
        # Change filename options
        change_filename_label = QLabel("Change Output File Names:")
        label_label = QLabel("Label:")
        self.label_input = QLineEdit("A")
        self.label_input.setMaxLength(1)
        self.label_input.setFixedWidth(60)
        self.change_filename_btn = QPushButton("Change Filenames")
        self.change_filename_btn.clicked.connect(self.run_change_filename)
        # ---------------------------------------------------------------------------- #
        # Layout grid
        additional_options_layout.addWidget(auto_re3d_label, 0, 0)
        additional_options_layout.addWidget(self.auto_re3d_large_btn, 0, 1)
        additional_options_layout.addWidget(self.auto_re3d_small_btn, 0, 2)
        additional_options_layout.addWidget(self.terminate_auto_re3d_btn, 0, 3)
        additional_options_layout.addWidget(change_filename_label, 1, 0)
        additional_options_layout.addWidget(label_label, 1, 1)
        additional_options_layout.addWidget(self.label_input, 1, 2)
        additional_options_layout.addWidget(self.change_filename_btn, 1, 3)
        
        additional_options_group.setLayout(additional_options_layout)
        top_layout.addWidget(additional_options_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.process_button = QPushButton("Process Selected Layer")
        self.process_button.clicked.connect(self.process_current_selection)
        
        self.start_single_button = QPushButton("Process Single File")
        self.start_single_button.clicked.connect(self.start_single_process)
        
        exit_button = QPushButton("Exit")
        exit_button.clicked.connect(self.close)
        
        button_layout.addStretch()
        button_layout.addWidget(self.process_button)
        button_layout.addWidget(self.start_single_button)
        button_layout.addWidget(exit_button)
        button_layout.addStretch()
        
        top_layout.addLayout(button_layout)
        
        # Add the top content to the splitter
        self.main_splitter.addWidget(top_content)
        
        # Create log widget
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        
        self.log_widget = LogWidget()
        log_layout.addWidget(self.log_widget)
        
        # Add clear log button
        clear_log_button = QPushButton("Clear Log")
        clear_log_button.clicked.connect(self.clear_log)
        log_layout.addWidget(clear_log_button)
        
        log_group.setLayout(log_layout)
        
        # Add log group to splitter
        self.main_splitter.addWidget(log_group)
        
        # Set initial splitter sizes (60% top, 40% log)
        self.main_splitter.setSizes([400, 300])
        
        # Add splitter to main layout
        main_layout.addWidget(self.main_splitter)
    
    def setup_logging(self):
        """Set up logging to the log widget"""
        # Create custom formatter for console (with timestamp)
        console_formatter = EmojiFormatter('%(asctime)s - %(levelname)s - %(message)s', 
                                        datefmt='%Y-%m-%d %H:%M:%S')
        
        # Create formatter for widget (without timestamp since widget adds its own)
        widget_formatter = EmojiFormatter('%(levelname)s - %(message)s')
        
        # Configure console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        
        # Create handler that writes log messages to the LogWidget
        self.log_handler = QTextEditLogger(self.log_widget)
        self.log_handler.setFormatter(widget_formatter)
        self.log_handler.setLevel(logging.INFO)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove any existing handlers and add our custom handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        root_logger.addHandler(console_handler)
        root_logger.addHandler(self.log_handler)
        
        # Log that logging is set up
        logging.info("Logging system initialized")
    
    def clear_log(self):
        """Clear the log widget"""
        self.log_widget.clear()
        logging.info("Log cleared")
    
    def load_config(self):
        """Load configuration from YAML file"""
        try:
            with open('config_layers.yaml', 'r') as file:
                self.config = yaml.safe_load(file)
            
            # Populate slice list from config
            if 'slices' in self.config:
                for slice_name in self.config['slices']:
                    self.slice_list.addItem(slice_name)
                
                if self.slice_list.count() > 0:
                    self.slice_list.setCurrentRow(0)
                    
            logging.info("Configuration loaded successfully")
        except Exception as e:
            logging.error(f"Error loading configuration: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load config_layers.yaml: {str(e)}")
    # ---------------------------------------------------------------------------- #
    def enable_slice_editing(self, enable=True):
        """Enable or disable slice property editing"""
        self.zmin_input.setEnabled(enable)
        self.zmax_input.setEnabled(enable)
        self.potentials_input.setEnabled(enable)
        self.save_info_button.setEnabled(enable)
    
    def update_selection_info(self):
        """Update information display based on selected slice"""
        current_item = self.slice_list.currentItem()
        if current_item:
            slice_name = current_item.text()
            if slice_name in self.config['slices']:
                slice_data = self.config['slices'][slice_name]
                
                # Update the form fields
                self.layer_value.setText(slice_name)
                self.zmin_input.setText(str(slice_data['zmin']))
                self.zmax_input.setText(str(slice_data['zmax']))
                
                # Convert potential list to comma-separated string
                potentials_str = ', '.join(map(str, slice_data['potential']))
                self.potentials_input.setText(potentials_str)
                
                # Enable editing
                self.enable_slice_editing(True)
                
                # Auto-populate single file field with selected slice
                self.file_input.setText(f"{slice_name}.dxf")
                
                logging.info(f"Selected layer: {slice_name}")
            else:
                self.layer_value.setText(slice_name)
                self.zmin_input.clear()
                self.zmax_input.clear()
                self.potentials_input.clear()
                self.enable_slice_editing(False)
                logging.warning(f"Layer {slice_name} found in list but not in config")
        else:
            self.layer_value.setText("No layer selected")
            self.zmin_input.clear()
            self.zmax_input.clear()
            self.potentials_input.clear()
            self.enable_slice_editing(False)
    
    def save_slice_changes(self):
        """Save the edited slice properties to the config"""
        current_item = self.slice_list.currentItem()
        if not current_item:
            return
            
        slice_name = current_item.text()
        if slice_name not in self.config['slices']:
            logging.warning(f"Cannot save: Layer {slice_name} not found in config")
            QMessageBox.warning(self, "Warning", f"Layer {slice_name} not found in configuration")
            return
            
        try:
            # Get and validate the input values
            zmin = float(self.zmin_input.text())
            zmax = float(self.zmax_input.text())
            
            # Parse potentials from comma-separated string and ensure they are integers
            potentials_text = self.potentials_input.text().strip()
            if potentials_text:
                # Split by comma, remove whitespace, convert to integers
                potentials = [int(float(p.strip())) for p in potentials_text.split(',')]
            else:
                potentials = []
                
            # Update the configuration
            self.config['slices'][slice_name]['zmin'] = zmin
            self.config['slices'][slice_name]['zmax'] = zmax
            self.config['slices'][slice_name]['potential'] = potentials
            
            # Save the configuration to the file
            with open('config_layers.yaml', 'w') as file:
                yaml.dump(self.config, file, default_flow_style=False)
                
            logging.info(f"Updated configuration for layer {slice_name}")
            # Brief flash message instead of a dialog box for better UX with enter key
            # self.statusBar().showMessage(f"Successfully updated layer {slice_name}", 3000)
            QMessageBox.information(self, "Success", f"Successfully updated layer {slice_name}")
            
            
        except ValueError as e:
            logging.error(f"Invalid input format: {str(e)}")
            QMessageBox.warning(self, "Error", f"Invalid input format: {str(e)}")
        except Exception as e:
            logging.error(f"Error saving configuration: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")
    
    def browse_file(self):
        """Open file dialog to select DXF file"""
        filename, _ = QFileDialog.getOpenFileName(self, "Select DXF File", "", "DXF Files (*.dxf)")
        if filename:
            base_filename = os.path.basename(filename)
            self.file_input.setText(base_filename)
            logging.info(f"Selected file: {base_filename}")
    
    def process_current_selection(self):
        """Process the currently selected layer"""
        current_item = self.slice_list.currentItem()
        if current_item:
            self.process_selected_layer(current_item.text())
        else:
            QMessageBox.warning(self, "Warning", "Please select a layer first")
            logging.warning("No layer selected for processing")
    
    def process_selected_layer(self, layer_name):
        """Process the selected layer"""
        if not layer_name:
            QMessageBox.warning(self, "Warning", "Invalid layer name")
            logging.warning("Invalid layer name")
            return
            
        filename = f"{layer_name}.dxf"
        
        # Get selected options
        mode = 'P' if self.preview_radio.isChecked() else 'R'
        option = 'L' if self.large_radio.isChecked() else 'S'
        
        # Disable UI during processing
        self.disable_ui()
        logging.info(f"Processing layer {layer_name} with mode={mode}, option={option}")
        
        # Start worker thread
        self.worker = AutoPre3DThread(mode, filename, option)
        self.worker.finished.connect(self.process_finished)
        self.worker.log_message.connect(self.log_worker_message)
        self.worker.start()
    
    def start_single_process(self):
        """Start processing a single file"""
        filename = self.file_input.text()
        
        if not filename:
            QMessageBox.warning(self, "Warning", "Please select a DXF file")
            logging.warning("No file selected for processing")
            return
        
        if not filename.endswith('.dxf'):
            QMessageBox.warning(self, "Warning", "Selected file must be a DXF file")
            logging.warning(f"Selected file {filename} is not a DXF file")
            return
        
        # Get selected options
        mode = 'P' if self.preview_radio.isChecked() else 'R'
        option = 'L' if self.large_radio.isChecked() else 'S'
        
        # Disable UI during processing
        self.disable_ui()
        logging.info(f"Processing single file {filename} with mode={mode}, option={option}")
        
        # Start worker thread
        self.worker = AutoPre3DThread(mode, filename, option)
        self.worker.finished.connect(self.process_finished)
        self.worker.log_message.connect(self.log_worker_message)
        self.worker.start()
    # ---------------------------------------------------------------------------- #
    def run_auto_re3d(self, option):
        """Run the auto_relax3d.py script with the specified option"""
        # Disable UI during processing
        self.disable_ui()
        logging.info(f"Running AutoRe3D with option {option}")
        
        # Start worker thread
        self.auto_re3d_worker = AutoRe3DThread(option)
        self.auto_re3d_worker.finished.connect(self.auto_re3d_finished)
        self.auto_re3d_worker.log_message.connect(self.handle_auto_re3d_log)
        self.auto_re3d_worker.start()
        
        # Enable the terminate button
        self.terminate_auto_re3d_btn.setEnabled(True)

    def terminate_auto_re3d(self):
        """Terminate the running AutoRe3D process"""
        if hasattr(self, 'auto_re3d_worker') and self.auto_re3d_worker.isRunning():
            self.log_widget.append_log("🔶 Requesting termination of AutoRe3D process...", logging.WARNING)
            self.auto_re3d_worker.request_termination()
            
            # Disable the terminate button until it's actually terminated
            self.terminate_auto_re3d_btn.setEnabled(False)

    def auto_re3d_finished(self):
        """Called when the AutoRe3D thread finishes"""
        self.log_widget.append_log("🔹 AutoRe3D thread finished", logging.INFO)
        self.enable_ui()
        self.terminate_auto_re3d_btn.setEnabled(False)

    def handle_auto_re3d_log(self, message):
        """Special handler for auto_relax3d logs to format them nicely"""
        # Add special formatting for CPU usage logs
        if "Current CPU usage" in message:
            # Extract the percentage from the message
            try:
                percentage = float(message.split("Current CPU usage:")[1].split("%")[0].strip())
                
                # Format based on percentage value
                if percentage < 5:
                    # Process is likely idle
                    self.log_widget.append_log(f"⚡ CPU IDLE: {percentage}%", logging.INFO)
                elif percentage > 80:
                    # High CPU usage
                    self.log_widget.append_log(f"🔥 HIGH CPU: {percentage}%", logging.WARNING)
                else:
                    # Normal operation
                    self.log_widget.append_log(f"⚙️ CPU: {percentage}%", logging.INFO)
            except:
                # If parsing fails, just log the original message
                self.log_widget.append_log(f"🔹 {message}", logging.INFO)
        elif "process completed" in message.lower() or "completed successfully" in message.lower():
            # Highlight process completion
            self.log_widget.append_log(f"✅ {message}", logging.INFO)
        elif "error" in message.lower() or "failed" in message.lower():
            # Highlight errors
            self.log_widget.append_log(f"❌ {message}", logging.ERROR)
        elif "terminated" in message.lower():
            # Highlight termination
            self.log_widget.append_log(f"🔶 {message}", logging.WARNING)
        else:
            # Regular log messages
            self.log_widget.append_log(f"🔹 {message}", logging.INFO)

    def terminate_auto_re3d(self):
        """Terminate only the auto_relax3d.py subprocess, not the entire application"""
        if hasattr(self, 'auto_re3d_worker') and self.auto_re3d_worker.isRunning():
            reply = QMessageBox.question(
                self,
                'Confirm Termination',
                'Are you sure you want to terminate the running AutoRe3D process?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                logging.info("Terminating AutoRe3D process by user request")
                # Request termination of the subprocess only
                self.auto_re3d_worker.request_termination()
                self.statusBar().showMessage("Termination requested. Please wait...", 5000)
            
    def auto_re3d_finished(self):
        """Called when AutoRe3D processing is complete"""
        self.enable_ui()
        # Disable the terminate button
        self.terminate_auto_re3d_btn.setEnabled(False)
        logging.info("AutoRe3D process completed or terminated")
        
    # ---------------------------------------------------------------------------- #
    def run_change_filename(self):
        """Run the _ChangeOutFileName.py script"""
        # Get the label from input
        label = self.label_input.text()
        if not label:
            QMessageBox.warning(self, "Warning", "Please enter a label")
            logging.warning("No label entered for filename change")
            return
            
        # Get model type from radio buttons
        model_type = 'L' if self.large_radio.isChecked() else 'S'
        
        # Disable UI during processing
        self.disable_ui()
        logging.info(f"Changing output filenames (Model: {model_type}, Label: {label})")
        
        # Start worker thread
        self.change_filename_worker = ChangeFileNameThread(model_type, label)
        self.change_filename_worker.finished.connect(self.process_finished)
        self.change_filename_worker.log_message.connect(self.log_worker_message)
        self.change_filename_worker.start()
    
    def log_worker_message(self, message):
        """Handle log messages from worker threads"""
        logging.info(message)
    
    def disable_ui(self):
        """Disable UI controls during processing"""
        self.start_single_button.setEnabled(False)
        self.process_button.setEnabled(False)
        self.slice_list.setEnabled(False)
        self.auto_re3d_large_btn.setEnabled(False)
        self.auto_re3d_small_btn.setEnabled(False)
        # Don't disable the terminate button if we're running AutoRe3D
        if hasattr(self, 'auto_re3d_worker') and self.auto_re3d_worker.isRunning():
            self.terminate_auto_re3d_btn.setEnabled(True)
        else:
            self.terminate_auto_re3d_btn.setEnabled(False)
        self.change_filename_btn.setEnabled(False)
        logging.info("UI controls disabled during processing")
    
    def enable_ui(self):
        """Enable UI controls after processing"""
        self.start_single_button.setEnabled(True)
        self.process_button.setEnabled(True)
        self.slice_list.setEnabled(True)
        self.auto_re3d_large_btn.setEnabled(True)
        self.auto_re3d_small_btn.setEnabled(True)
        self.change_filename_btn.setEnabled(True)
        logging.info("UI controls enabled - ready for next operation")
    
    def process_finished(self):
        """Called when processing is complete"""
        self.enable_ui()
        logging.info("Process completed")


# ---------------------------------------------------------------------------- #

# ---------------------------------------------------------------------------- #

class CombineAutomationThread(QThread):
    update_progress = pyqtSignal(int, str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    
    def __init__(self, file_type, min_value, max_value, folder_path):
        super().__init__()
        self.file_type = file_type
        self.min_value = min_value
        self.max_value = max_value
        self.folder_path = folder_path
        self.running = True
        
    def run(self):
        try:
            # Generate file list based on range
            file_list = self.generate_file_list()
            total_files = len(file_list)
            
            if total_files == 0:
                self.error_signal.emit("No matching files found in the selected range.")
                return
                
            self.update_progress.emit(0, f"Starting to process {total_files} files...")
            
            # Start combine software
            combine_path = self.findcombine_exe()
            if not combine_path:
                self.error_signal.emit("combine.exe not found. Please check installation.")
                return
                
            win32api.ShellExecute(1, 'open', combine_path, '', '', 1)
            time.sleep(1)
            
            # Find software window
            window_handle = self.find_window("combine")
            if not window_handle:
                self.error_signal.emit("Could not find combine window.")
                return
                
            # Process each file
            for i, file_name in enumerate(file_list):
                if not self.running:
                    break
                    
                self.update_progress.emit(int((i / total_files) * 100), f"Processing {file_name}...")
                
                # Click File menu or press Alt+F
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)  # Alt key down
                win32api.keybd_event(ord('F'), 0, 0, 0)  # F key
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)  # Alt key up
                time.sleep(0.5)
                
                # # Navigate to Open menu item
                # win32api.keybd_event(ord('O'), 0, 0, 0)  # O key for Open
                # time.sleep(1)
                
                # Now we should be in the file dialog
                dialog_handle = self.find_dialog_window()
                if dialog_handle:
                    # Clear the input field by selecting all text (Ctrl+A) and deleting it
                    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)  # Ctrl key down
                    win32api.keybd_event(ord('A'), 0, 0, 0)  # A key down
                    win32api.keybd_event(ord('A'), 0, win32con.KEYEVENTF_KEYUP, 0)  # A key up
                    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)  # Ctrl key up
                    time.sleep(0.2)
                    
                    # Delete the selected text
                    win32api.keybd_event(win32con.VK_DELETE, 0, 0, 0)  # Delete key
                    win32api.keybd_event(win32con.VK_DELETE, 0, win32con.KEYEVENTF_KEYUP, 0)
                    time.sleep(0.2)
                    
                    # Type the filename in the file name field
                    self.type_string(file_name)
                    time.sleep(0.5)
                    
                    # Press Enter after typing the filename
                    win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)  # Press Enter
                    win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)  # Release Enter
                    time.sleep(2)  # Wait for processing to complete
                else:
                    self.error_signal.emit(f"Could not find file dialog while processing {file_name}")
                    break
            
            # Close the application when done
            if window_handle:
                win32gui.PostMessage(window_handle, win32con.WM_CLOSE, 0, 0)
            
            # Process the relax3d.dat file - remove first 3 lines
            self.process_relax3d_dat_file()
                
            self.update_progress.emit(100, "All files processed successfully!")
            self.finished_signal.emit()
            
        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")
            logger.error(f"Error in automation thread: {e}", exc_info=True)
    
    def findcombine_exe(self):
        """Find combine.exe in common locations"""
        # Try to find in standard installation directory
        config = load_config('config_main.ini')
        r3d_path = config.get('Paths', 'R3D_PATH')
        common_paths = [
            os.path.join(r3d_path, "combine.exe"),
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), "combine.exe"),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), "combine.exe")
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        # Let user select the executable
        return None
    
    def generate_file_list(self):
        """Generate list of files within the specified range"""
        files = []
        
        # Generate all possible numeric values in the range
        values = []
        current = self.min_value
        while current <= self.max_value:
            values.append(current)
            # Handle decimal increments (.5, .6 etc.)
            if current == int(current):
                # If it's a whole number, next check x.5, x.6 etc.
                for decimal in [0.5, 0.6]:
                    if current + decimal <= self.max_value:
                        values.append(current + decimal)
            current = int(current) + 1
        
        # Create filenames and check if they exist
        for value in values:
            # Format with or without decimal part
            if value == int(value):
                filename = f"{self.file_type}{int(value)}.txt"
            else:
                filename = f"{self.file_type}{value}.txt"
                
            full_path = os.path.join(self.folder_path, filename)
            if os.path.exists(full_path):
                files.append(filename)
                
        return files
    
    def find_window(self, window_name):
        """Find window by name"""
        handle = win32gui.FindWindow(None, window_name)
        if handle:
            win32gui.SetForegroundWindow(handle)
            return handle
        return None
    
    def find_dialog_window(self):
        """Find file dialog window"""
        # Try to find common file dialog titles
        for title in ["Open: Select File for Unit 10", "Open", "Save As", "Select File"]:
            handle = win32gui.FindWindow("#32770", title)
            if handle:
                win32gui.SetForegroundWindow(handle)
                return handle
        return None
    
    def click_button(self, window_handle, button_text):
        """Find and click a button with the given text"""
        def callback(hwnd, hwnds):
            if win32gui.GetWindowText(hwnd) == button_text:
                win32gui.SendMessage(hwnd, win32con.BM_CLICK, 0, 0)
                return False
            return True
        
        win32gui.EnumChildWindows(window_handle, callback, [])
    
    def type_string(self, text):
        """Type a string using keyboard simulation"""
        for char in text:
            if char == '-':
                win32api.keybd_event(189, 0, 0, 0)  # Hyphen key
            elif char == '.':
                win32api.keybd_event(190, 0, 0, 0)  # Period key
            elif char.isdigit():
                # Convert '0' to '9' to corresponding virtual key codes
                key_code = ord(char) + 48
                win32api.keybd_event(key_code, 0, 0, 0)
            else:
                # Convert 'a' to 'z' to corresponding virtual key codes
                key_code = ord(char.upper())
                win32api.keybd_event(key_code, 0, 0, 0)
            time.sleep(0.05)
    
    def stop(self):
        """Stop the automation process"""
        self.running = False
        
    def process_relax3d_dat_file(self):
        """Process relax3d.dat file: remove first 3 lines and log them"""
        try:
            # Look for relax3d.dat in the folder path
            dat_file_path = os.path.join(self.folder_path, "relax3d.dat")
            
            # Also check the current directory if not found
            if not os.path.exists(dat_file_path):
                dat_file_path = "relax3d.dat"
                
            # Check if the file exists
            if not os.path.exists(dat_file_path):
                self.update_progress.emit(95, f"Warning: relax3d.dat file not found in {self.folder_path} or current directory")
                return
                
            # Read the file content
            with open(dat_file_path, 'r') as file:
                lines = file.readlines()
                
            # Check if we have at least 3 lines
            if len(lines) < 3:
                self.update_progress.emit(95, f"Warning: relax3d.dat has fewer than 3 lines ({len(lines)} lines found)")
                return
                
            # Store the first 3 lines for logging
            removed_lines = lines[:3]
            
            # Write back the file without the first 3 lines
            with open(dat_file_path, 'w') as file:
                file.writelines(lines[3:])
                
            # Log the removed lines
            log_message = "Removed the following lines from relax3d.dat:\n"
            for i, line in enumerate(removed_lines):
                log_message += f"Line {i+1}: {line.strip()}\n"
                
            self.update_progress.emit(98, log_message)
            
        except Exception as e:
            self.update_progress.emit(95, f"Error processing relax3d.dat: {str(e)}")


class CombineAutomationGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.folder_path = ""
        self.automation_thread = None
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Combine Software Automation")
        self.setGeometry(100, 100, 500, 500)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # File type selection
        file_type_group = QGroupBox("File Type")
        file_type_layout = QHBoxLayout()
        
        self.file_type_group = QButtonGroup()
        self.radio_l = QRadioButton("L Files")
        self.radio_s = QRadioButton("S Files")
        self.radio_l.setChecked(True)
        
        self.file_type_group.addButton(self.radio_l)
        self.file_type_group.addButton(self.radio_s)
        
        file_type_layout.addWidget(self.radio_l)
        file_type_layout.addWidget(self.radio_s)
        file_type_group.setLayout(file_type_layout)
        
        # Range selection for L files
        l_range_group = QGroupBox("L File Range")
        l_range_layout = QHBoxLayout()
        
        l_min_label = QLabel("Min:")
        self.l_min_spin = QDoubleSpinBox()
        self.l_min_spin.setRange(1, 10)
        self.l_min_spin.setValue(1)
        self.l_min_spin.setSingleStep(0.1)
        
        l_max_label = QLabel("Max:")
        self.l_max_spin = QDoubleSpinBox()
        self.l_max_spin.setRange(1, 10)
        self.l_max_spin.setValue(10)
        self.l_max_spin.setSingleStep(0.1)
        
        l_range_layout.addWidget(l_min_label)
        l_range_layout.addWidget(self.l_min_spin)
        l_range_layout.addWidget(l_max_label)
        l_range_layout.addWidget(self.l_max_spin)
        l_range_group.setLayout(l_range_layout)
        
        # Range selection for S files
        s_range_group = QGroupBox("S File Range")
        s_range_layout = QHBoxLayout()
        
        s_min_label = QLabel("Min:")
        self.s_min_spin = QDoubleSpinBox()
        self.s_min_spin.setRange(1, 5)
        self.s_min_spin.setValue(1)
        self.s_min_spin.setSingleStep(0.1)
        
        s_max_label = QLabel("Max:")
        self.s_max_spin = QDoubleSpinBox()
        self.s_max_spin.setRange(1, 5)
        self.s_max_spin.setValue(2.5)
        self.s_max_spin.setSingleStep(0.1)
        
        s_range_layout.addWidget(s_min_label)
        s_range_layout.addWidget(self.s_min_spin)
        s_range_layout.addWidget(s_max_label)
        s_range_layout.addWidget(self.s_max_spin)
        s_range_group.setLayout(s_range_layout)
        
        # Folder selection
        folder_group = QGroupBox("Folder Selection")
        folder_layout = QHBoxLayout()
        
        self.folder_label = QLabel("No folder selected")
        self.folder_button = QPushButton("Select Folder")
        self.folder_button.clicked.connect(self.select_folder)
        
        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.folder_button)
        folder_group.setLayout(folder_layout)
        
        # Control buttons
        buttons_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Automation")
        self.start_button.clicked.connect(self.start_automation)
        self.start_button.setEnabled(False)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_automation)
        self.stop_button.setEnabled(False)
        
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        # Log window
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        
        # Add all widgets to main layout
        main_layout.addWidget(file_type_group)
        main_layout.addWidget(l_range_group)
        main_layout.addWidget(s_range_group)
        main_layout.addWidget(folder_group)
        main_layout.addLayout(buttons_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(log_group)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Connect radio buttons to enable/disable appropriate spinboxes
        self.radio_l.toggled.connect(self.toggle_range_groups)
        self.radio_s.toggled.connect(self.toggle_range_groups)
        
        # Initial toggle
        self.toggle_range_groups()
        
        # Log initial message
        self.log_message("Application started. Please select a folder and configure options.")
    
    def toggle_range_groups(self):
        """Enable/disable range groups based on file type selection"""
        l_selected = self.radio_l.isChecked()
        self.l_min_spin.setEnabled(l_selected)
        self.l_max_spin.setEnabled(l_selected)
        self.s_min_spin.setEnabled(not l_selected)
        self.s_max_spin.setEnabled(not l_selected)
    
    def select_folder(self):
        """Open folder selection dialog"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with TXT Files")
        if folder:
            self.folder_path = folder
            self.folder_label.setText(f"...{folder[-30:]}" if len(folder) > 30 else folder)
            self.start_button.setEnabled(True)
            self.log_message(f"Selected folder: {folder}")
    
    def start_automation(self):
        """Start the automation process"""
        if not self.folder_path:
            QMessageBox.warning(self, "Warning", "Please select a folder first.")
            return
        
        # Get configuration
        file_type = "L" if self.radio_l.isChecked() else "S"
        
        if file_type == "L":
            min_value = self.l_min_spin.value()
            max_value = self.l_max_spin.value()
        else:
            min_value = self.s_min_spin.value()
            max_value = self.s_max_spin.value()
        
        if min_value > max_value:
            QMessageBox.warning(self, "Warning", "Minimum value cannot be greater than maximum value.")
            return
        
        # Create and start the automation thread
        self.automation_thread = CombineAutomationThread(file_type, min_value, max_value, self.folder_path)
        self.automation_thread.update_progress.connect(self.update_progress)
        self.automation_thread.finished_signal.connect(self.automation_finished)
        self.automation_thread.error_signal.connect(self.handle_error)
        
        self.automation_thread.start()
        
        # Update UI
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.folder_button.setEnabled(False)
        
        self.log_message(f"Starting automation for {file_type} files from {min_value} to {max_value}...")
    
    def stop_automation(self):
        """Stop the automation process"""
        if self.automation_thread and self.automation_thread.isRunning():
            self.automation_thread.stop()
            self.log_message("Stopping automation... Please wait.")
    
    @pyqtSlot(int, str)
    def update_progress(self, value, message):
        """Update progress bar and log"""
        self.progress_bar.setValue(value)
        self.log_message(message)
    
    @pyqtSlot()
    def automation_finished(self):
        """Handle automation completion"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.folder_button.setEnabled(True)
        self.log_message("Automation completed!")
    
    @pyqtSlot(str)
    def handle_error(self, error_message):
        """Handle errors from the automation thread"""
        QMessageBox.critical(self, "Error", error_message)
        self.log_message(f"ERROR: {error_message}", logging.ERROR)
        self.automation_finished()
        
    def log_message(self, message, level=logging.INFO):
        """Add formatted message to log"""
        # Format based on content and level
        if level >= logging.ERROR or "error" in message.lower():
            formatted_message = f"❌ {message}"
        elif level >= logging.WARNING or "warning" in message.lower():
            formatted_message = f"⚠️ {message}"
        elif "selected" in message.lower() or "complete" in message.lower() or "success" in message.lower():
            formatted_message = f"✅ {message}"
        else:
            formatted_message = f"🔹 {message}"
        
        # Add timestamp and append to log
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {formatted_message}")
        
        # Scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Also log to console with appropriate level
        if level >= logging.ERROR:
            logger.error(message)
        elif level >= logging.WARNING:
            logger.warning(message)
        else:
            logger.info(message)
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.automation_thread and self.automation_thread.isRunning():
            reply = QMessageBox.question(self, "Exit", 
                                         "Automation is still running. Do you want to stop and exit?",
                                         QMessageBox.Yes | QMessageBox.No, 
                                         QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.automation_thread.stop()
                self.automation_thread.wait(1000)  # Wait for thread to finish
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()




class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dark_mode = False
        self.initial_splitter_sizes = [250, 750]  # 存储初始分割器大小
        self.init_ui()
        # 添加快捷键
        self.installEventFilter(self) # Esc恢复布局

        
    def init_ui(self):
        self.setWindowTitle("AutoRelax3D Console GUI")
        self.setGeometry(100, 100, 600, 900)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # 减少边距避免布局错乱
        
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Sidebar setup
        self.sidebar_container = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(10, 10, 10, 10)  # 统一边距
        self.sidebar_layout.setSpacing(5)  # 设置固定间距
        
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(250)
        self.list_widget.setIconSize(QSize(32, 32))
        self.list_widget.setProperty("class", "sidebar")  # 添加类属性方便样式表选择
        
        menu_items = [
            ("CombineAutomationGUI", "icon0.png"),
            ("AutoRelax3D", "icon1.png"),
            # ("Data Processing & Plotting", "icon2.png"),
            # ("BK Tracking Optimization", "icon3.png"),
            # ("PhaseSpace", "icon4.png"),
            # ("Settings", "icon5.png")
        ]
        
        for text, icon in menu_items:
            item = QListWidgetItem(QIcon(icon), text)
            item.setSizeHint(QSize(item.sizeHint().width(), 50))
            item.setFont(QFont('Arial', 10, QFont.Bold))
            self.list_widget.addItem(item)
        
        self.sidebar_layout.addWidget(self.list_widget)
        
        # Bottom buttons container
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(5, 5, 5, 5)  # 统一边距
        bottom_layout.setSpacing(10)  # 设置固定间距
        
        # Theme toggle button
        self.theme_button = QPushButton()
        self.theme_button.setMinimumHeight(50)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.theme_button.setProperty("class", "theme-button")  # 添加类属性方便样式表选择
        bottom_layout.addWidget(self.theme_button)
        
        # About button
        self.about_button = QPushButton("About")
        self.about_button.setMinimumHeight(50)
        self.about_button.clicked.connect(self.show_about_dialog)
        bottom_layout.addWidget(self.about_button)
        
        self.sidebar_layout.addWidget(bottom_container)
        
        # Stack widget setup
        self.stack = QStackedWidget()
        self.stack.setProperty("class", "main-content")  # 添加类属性方便样式表选择
        
        # 添加页面
        self.stack.addWidget(CombineAutomationGUI())
        self.stack.addWidget(AutoRelax3D())
        
        self.splitter.addWidget(self.sidebar_container)
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([250, 750])
        self.splitter.setHandleWidth(2)  # 设置分割线宽度
        
        self.main_layout.addWidget(self.splitter)
        
        self.list_widget.currentRowChanged.connect(self.display)
        self.apply_theme()  # 初次应用主题
        
    
    # 添加新的事件过滤器函数
    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            # 按下Esc键时恢复初始布局
            self.reset_layout()
            return True
        return super().eventFilter(source, event)

    # 添加重置布局函数
    def reset_layout(self):
        # 恢复分割器初始大小
        self.splitter.setSizes(self.initial_splitter_sizes)
        # 确保修改后能够正确显示
        self.update()
        
        # 提示用户已重置布局
        status_bar = self.statusBar()
        status_bar.showMessage("布局已重置", 2000)  # 显示2秒
    
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        
    def apply_theme(self):
        # 应用主题到主窗口
        if self.dark_mode:
            self.theme_button.setText("☀️ Light Mode")
            self.setStyleSheet(self.get_dark_theme())
        else:
            self.theme_button.setText("🌙 Dark Mode")
            self.setStyleSheet(self.get_light_theme())
            
        # 确保子窗口也应用了相同的主题
        for i in range(self.stack.count()):
            widget = self.stack.widget(i)
            if hasattr(widget, 'apply_theme'):
                widget.apply_theme(self.dark_mode)
            elif hasattr(widget, 'setStyleSheet'):
                # 如果子窗口没有apply_theme方法，但可以应用样式表
                if self.dark_mode:
                    widget.setStyleSheet(self.get_widget_dark_theme())
                else:
                    widget.setStyleSheet(self.get_widget_light_theme())
    
    def get_light_theme(self):
        return """
            QMainWindow { 
                background-color: #f5f6fa; 
            }
            QWidget {
                font-family: Arial;
            }
            QListWidget.sidebar {
                background-color: #ffffff;
                border: none;
                border-right: 1px solid #e1e4e8;
                font-size: 14px;
                color: #24292e;
                padding: 5px;
            }
            QListWidget.sidebar::item {
                padding: 12px;
                margin: 2px 5px;
                border-radius: 6px;
                height: 45px;
            }
            QListWidget.sidebar::item:selected {
                background-color: #0366d6;
                color: white;
            }
            QListWidget.sidebar::item:hover:!selected {
                background-color: #f1f2f6;
            }
            QPushButton {
                background-color: #0366d6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover { 
                background-color: #0258bd; 
            }
            QPushButton.theme-button {
                background-color: #0366d6;
            }
            QSplitter::handle {
                background-color: #e1e4e8;
                width: 2px;
            }
            QSplitter::handle:hover { 
                background-color: #0366d6; 
            }
            QStackedWidget.main-content {
                background-color: white;
                border-radius: 8px;
                margin: 5px;
                padding: 10px;
            }
            QLabel, QCheckBox, QRadioButton, QGroupBox {
                color: #24292e;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: white;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                padding: 5px;
                color: #24292e;
            }
        """
    
    def get_dark_theme(self):
        return """
            QMainWindow { 
                background-color: #1a1a1a; 
            }
            QWidget {
                font-family: Arial;
            }
            QListWidget.sidebar {
                background-color: #2d2d2d;
                border: none;
                border-right: 1px solid #404040;
                font-size: 14px;
                color: #ffffff;
                padding: 5px;
            }
            QListWidget.sidebar::item {
                padding: 12px;
                margin: 2px 5px;
                border-radius: 6px;
                height: 45px;
            }
            QListWidget.sidebar::item:selected {
                background-color: #0d47a1;
                color: white;
            }
            QListWidget.sidebar::item:hover:!selected {
                background-color: #404040;
            }
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover { 
                background-color: #1565c0; 
            }
            QPushButton.theme-button {
                background-color: #0d47a1;
            }
            QSplitter::handle {
                background-color: #404040;
                width: 2px;
            }
            QSplitter::handle:hover { 
                background-color: #0d47a1; 
            }
            QStackedWidget.main-content {
                background-color: #2d2d2d;
                border-radius: 8px;
                margin: 5px;
                padding: 10px;
            }
            QLabel, QCheckBox, QRadioButton, QGroupBox {
                color: #ffffff;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #3a3a3a;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 5px;
                color: #ffffff;
            }
        """
    
    def get_widget_light_theme(self):
        # 子窗口的亮色主题
        return """
            QWidget {
                background-color: white;
                color: #24292e;
                font-family: Arial;
            }
            QLabel, QCheckBox, QRadioButton, QGroupBox {
                color: #24292e;
            }
            QPushButton {
                background-color: #0366d6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover { 
                background-color: #0258bd; 
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: white;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                padding: 5px;
                color: #24292e;
            }
        """
    
    def get_widget_dark_theme(self):
        # 子窗口的暗色主题
        return """
            QWidget {
                background-color: #2d2d2d;
                color: white;
                font-family: Arial;
            }
            QLabel, QCheckBox, QRadioButton, QGroupBox {
                color: white;
            }
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover { 
                background-color: #1565c0; 
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #3a3a3a;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 5px;
                color: white;
            }
        """
    
    def display(self, index):
        self.stack.setCurrentIndex(index)

    
    def show_about_dialog(self):
        about = QDialog(self)
        about.setWindowTitle("About")
        layout = QVBoxLayout(about)
        
        title = QLabel("AutoRelax3D Console GUI")
        content = QLabel("Developed by [CYL]\nVersion: 1.01\n© 2025 All Rights Reserved")
        
        for label in [title, content]:
            label.setStyleSheet(
                "color: " + ("#ffffff" if self.dark_mode else "#24292e") +
                ";" + ("font-size: 18px; font-weight: bold;" if label == title else "font-size: 14px;")
            )
            layout.addWidget(label, alignment=Qt.AlignCenter)
        
        about.setStyleSheet(f"""
            QDialog {{
                background-color: {("#2d2d2d" if self.dark_mode else "white")};
                min-width: 300px;
                min-height: 150px;
            }}
        """)
        
        about.exec_()
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
