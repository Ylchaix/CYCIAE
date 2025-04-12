import os
import time
import logging
import yaml
from typing import List, Optional
import psutil
import pyautogui
import subprocess
import win32gui
import win32api
import win32con
import configparser

# Set up logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, format='%(message)s')

def load_config(config_file: str) -> configparser.ConfigParser:
    """Load and return the configuration from the specified file."""
    config = configparser.ConfigParser()
    config.read(config_file)
    return config

config = load_config('config_main.ini')
# Configuration
R3D_PATH = config.get('Paths', 'R3D_PATH')
SOFTWARE_NAMES = ['1_GEOMETRY', '2_initial', '3_convert', '4_clip', '5_exam', '6_divide']
CONFIG_PATH = 'config_layers.yaml'

class AutoPre3D:
    def __init__(self, mode: str):
        self.mode = mode
        self.load_config()

    def load_config(self):
        """Load configuration from YAML file"""
        with open(CONFIG_PATH, 'r') as file:
            self.config = yaml.safe_load(file)

    @staticmethod
    def find_window(window_name: str) -> int:
        """Find the window by its name and bring it to the foreground"""
        handle = win32gui.FindWindow(None, window_name)
        if handle:
            win32gui.SetForegroundWindow(handle)
            return handle
        logging.error(f"Window not found: {window_name}")
        return 0

    @staticmethod
    def find_dialog_window() -> int:
        """Find the file dialog window"""
        # Try to find common file dialog titles
        for title in ["Open: Select File for Unit 2", "Open", "Save As", "Select File"]:
            handle = win32gui.FindWindow("#32770", title)
            if handle:
                win32gui.SetForegroundWindow(handle)
                return handle
        logging.error("File dialog window not found")
        return 0

    @staticmethod
    def exec_cmd(commands: List[str], stay_time: float = 0.1):
        """Simulate keyboard input for commands"""
        for cmd in commands:
            for char in cmd:
                if char == '-':
                    win32api.keybd_event(109, 0, 0, 0)
                elif char == '.':
                    win32api.keybd_event(110, 0, 0, 0)
                elif char.isdigit():
                    win32api.keybd_event(int(char) + 96, 0, 0, 0)
                else:
                    win32api.keybd_event(ord(char.upper()), 0, 0, 0)
                time.sleep(0.05)
            win32api.keybd_event(13, 0, 0, 0)  # Enter key
            time.sleep(stay_time)

    @staticmethod
    def click_button(window_handle, button_text):
        """Find and click a button with the given text in the specified window"""
        # Get all child windows
        def callback(hwnd, hwnds):
            if win32gui.GetWindowText(hwnd) == button_text:
                win32gui.SendMessage(hwnd, win32con.BM_CLICK, 0, 0)
                return False
            return True
        
        win32gui.EnumChildWindows(window_handle, callback, [])

    def run_software(self, software_name: str) -> Optional[int]:
        """Run specified software and return its window handle"""
        exe_path = os.path.join(R3D_PATH, f"{software_name}.exe")
        logging.info(f"Opening: {software_name}")
        win32api.ShellExecute(1, 'open', exe_path, '', '', 1)
        time.sleep(1)
        window_handle = self.find_window(software_name)

        if window_handle:
            return window_handle
        logging.error(f"Unable to find software window: {software_name}")
        return None

    def run_1_geometry(self, filename: str):
        """Run 1_GEOMETRY software"""
        window_handle = self.run_software('1_GEOMETRY')
        if window_handle:
            logging.info("Opening .dxf file")
            self.exec_cmd([filename, '0', '0'], 0.1)
            time.sleep(2)
            win32gui.PostMessage(window_handle, win32con.WM_CLOSE, 0, 0)

    def run_2_initial(self, option: str, slice_name: str):
        """Run 2_initial software"""
        window_handle = self.run_software('2_initial')
        if window_handle:
            slice_config = self.config['slices'][slice_name]
            zmin, zmax = slice_config['zmin'], slice_config['zmax']
            potentials = slice_config['potential']
            
            # Execute option commands
            for cmd in self.config['options'][option]['exec_cmd']:
                self.exec_cmd(cmd, 0.15)
            time.sleep(0.5)

            for p in potentials:
                self.exec_cmd([f"{zmin}", f"{zmax}", f"{p}"], 0.3)

    def run_other_softwares(self):
        """Run remaining software in sequence"""
        for software_name in SOFTWARE_NAMES[2:5]:
            window_handle = self.run_software(software_name)
            if window_handle:
                time.sleep(1)
                win32gui.PostMessage(window_handle, win32con.WM_CLOSE, 0, 0)

    def run_6_divide(self, output_filename: str):
        """Run 6_divide software and save to the specified filename"""
        window_handle = self.run_software('6_divide')
        if window_handle:
            logging.info(f"Working with 6_divide, saving to {output_filename}")
            time.sleep(1)
            
            # Click File menu or press Alt+F
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)  # Alt key down
            win32api.keybd_event(ord('F'), 0, 0, 0)  # F key
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)  # Alt key up
            time.sleep(0.3)
            
            # Navigate to Open menu item
            win32api.keybd_event(ord('O'), 0, 0, 0)  # O key for Open
            time.sleep(0.3)
            
            # Now we should be in the file dialog
            dialog_handle = self.find_dialog_window()
            if dialog_handle:
                # Type the filename in the file name field
                self.exec_cmd([output_filename], 0.1)
                time.sleep(0.2)
                
                # Click the "Open" button or press Enter
                # First try to find and click the button
                self.click_button(dialog_handle, "打开(O)")
                time.sleep(0.5)
                
                # If button clicking doesn't work, try pressing Enter
                win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
                time.sleep(0.5)
            
            # Wait for processing to complete
            time.sleep(2)
            
            # # Close the application
            win32gui.PostMessage(window_handle, win32con.WM_CLOSE, 0, 0) # 关闭主窗口

    def run(self, filename: str, option: str):
        """Main execution logic"""
        logging.info("Starting automated task")
        name = filename.replace('.dxf', '')

        self.run_1_geometry(filename)
        self.run_2_initial(option, name)

        if self.mode == 'R': # Run
            self.run_other_softwares()
            
            # Generate output filename based on filename and option
            name_prefix = 'L' if option == 'L' else 'S'
            name_suffix = filename.replace('.dxf', '').replace('L', '')  # Get numeric part
            output_filename = f"{name_prefix}{name_suffix}.txt"
            
            # Run 6_divide with the generated output filename
            self.run_6_divide(output_filename)

        logging.info("Automated task completed")



class AutoRe3D:
    """Class to handle automated Relax3D operations"""
    
    def __init__(self, config_file='config_main.ini'):
        """Initialize with the config file path"""
        self.config = self.load_config(config_file)
        self.process = None
        self.relax_process = None
        self.should_terminate = False
        
    def load_config(self, config_file: str) -> configparser.ConfigParser:
        """Load and return the configuration from the specified file."""
        config = configparser.ConfigParser()
        config.read(config_file)
        return config
        
    def run_software(self, path: str) -> subprocess.Popen:
        """Run the specified software and return the process."""
        logging.info(f"Running software: {path}")
        try:
            self.process = subprocess.Popen(path, cwd=os.path.dirname(path))
            time.sleep(3)  # Wait for the software to start
            return self.process
        except subprocess.SubprocessError as e:
            logging.error(f"Error starting software: {e}")
            return None
            
    def exec_cmd(self, commands: List[str], interval: float = 0.1):
        """Simulate keyboard input for commands."""
        for cmd in commands:
            if self.should_terminate:
                break
            pyautogui.typewrite(cmd)
            pyautogui.press('enter')
            time.sleep(interval)
            
    def get_relax2000_process(self, software_name: str) -> psutil.Process:
        """Get the process for the Relax2000 software."""
        for process in psutil.process_iter(['name', 'exe']):
            if process.info['name'].lower() == software_name.lower():
                self.relax_process = process
                return process
        return None
        
    def wait_for_cpu_usage_drop(self, process: psutil.Process, threshold: float, 
                                check_interval: int, timeout: int) -> bool:
        """Wait for the process CPU usage to drop below the threshold."""
        start_time = time.time()
        while time.time() - start_time < timeout and not self.should_terminate:
            try:
                cpu_percent = process.cpu_percent(interval=1)
                logging.info(f"Current CPU usage: {cpu_percent}%")
                if cpu_percent < threshold:
                    return True
            except psutil.NoSuchProcess:
                logging.error("Process has ended")
                return False
            time.sleep(check_interval)
        
        if self.should_terminate:
            logging.info("Process termination requested - stopping CPU monitoring")
            return False
            
        logging.error(f"Timeout waiting for CPU usage to drop (after {timeout} seconds)")
        return False
        
    def run_relax2000_task(self, option: str):
        """Run the Relax2000 task with the specified option (L or S)."""
        if option not in ['L', 'S']:
            logging.error("Invalid option. Please choose L or S.")
            return False
            
        commands_section = f'Commands-{option}'
        
        r3d_path = self.config.get('Paths', 'R3D_PATH')
        software_name = self.config.get('Software', 'SOFTWARE_NAME')
        cpu_threshold = self.config.getfloat('Thresholds', 'CPU_THRESHOLD')
        check_interval = self.config.getint('Intervals', 'CHECK_INTERVAL')
        process_timeout = self.config.getint('Timeouts', 'PROCESS_TIMEOUT')
        
        init_commands = self.config.get(commands_section, 'INIT_COMMANDS').split(', ')
        iter_command = self.config.get(commands_section, 'ITER_COMMAND')
        output_command = self.config.get(commands_section, 'OUTPUT_COMMAND')

        software_path = os.path.join(r3d_path, software_name)

        logging.info("Starting automated task")

        if not self.run_software(software_path):
            logging.error("Failed to start the software")
            return False

        pyautogui.press('space')
        time.sleep(3)
        self.exec_cmd(init_commands)

        if self.should_terminate:
            return False

        logging.info("Waiting for INIT process to complete...")
        relax_process = self.get_relax2000_process(software_name)
        if relax_process and self.wait_for_cpu_usage_drop(relax_process, cpu_threshold, check_interval, process_timeout):
            logging.info("INIT process completed")
            self.exec_cmd([iter_command])

            if self.should_terminate:
                return False
                
            logging.info("Waiting for ITER process to complete...")
            if self.wait_for_cpu_usage_drop(relax_process, cpu_threshold, check_interval, process_timeout):
                logging.info("ITER process completed")
                self.exec_cmd([output_command])
            else:
                logging.error("ITER process did not complete within the expected time")
                return False
        else:
            logging.error("INIT process did not complete within the expected time")
            return False

        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logging.error(f"{software_name} did not exit within 30 seconds after OUTPUT, terminating")
            self.process.terminate()

        logging.info("Automated task completed")
        return True
    
    def terminate(self):
        """Request termination of the running task"""
        self.should_terminate = True
        logging.info("Termination requested")
        
        # Try to terminate the processes
        if self.process:
            try:
                self.process.terminate()
            except:
                pass
                
        if self.relax_process:
            try:
                self.relax_process.terminate()
            except:
                pass

# Main function for direct script execution
def main():
    option = input("Choose option (L or S): ").upper()
    auto_re3d = AutoRe3D()
    auto_re3d.run_relax2000_task(option)

if __name__ == "__main__":
    main()