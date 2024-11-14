import sys
import os
import time
import threading
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
import serial
from serial.tools import list_ports
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QDialog, QTextEdit, QLabel,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QSpinBox,
    QPushButton, QLineEdit, QFileDialog, QMenuBar, QAction,
    QMessageBox, QComboBox, QWidgetAction
)
# Custom Imports
from SIX_SERVER_READER import PotentiostatReader
import AMUZA_Master

# Global variables
t_buffer = 1 #65
t_sampling = 10 #91
sample_rate = 1
connection = None  # This will be initialized after the user clicks 'Connect'
selected_wells = set()  # Set to store wells selected with click-and-drag (used for RUNPLATE)
ctrl_selected_wells = set()  # Set to store wells selected with Ctrl+Click (used for MOVE)


class WellLabel(QLabel):

    """Custom QLabel for well plate cells that supports click-and-drag and Ctrl+Click selection."""
    def __init__(self, well_id):
        super().__init__(well_id)
        self.well_id = well_id
        self.setFixedSize(50, 50)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: white; border: 1px solid black;")
        self.selected = False
        self.ctrl_selected = False

    def select(self):
        """Mark this cell as selected and change its color."""
        self.selected = True
        self.setStyleSheet("background-color: lightblue; border: 1px solid black;")

    def deselect(self):
        """Mark this cell as deselected and change its color."""
        self.selected = False
        self.setStyleSheet("background-color: white; border: 1px solid black;")

    def ctrl_select(self):
        """Mark this cell as Ctrl+selected for MOVE command."""
        self.ctrl_selected = True
        self.setStyleSheet("background-color: lightgreen; border: 1px solid black;")

    def ctrl_deselect(self):
        """Deselect this cell for MOVE command."""
        self.ctrl_selected = False
        self.setStyleSheet("background-color: white; border: 1px solid black;")

class PlotWindow(QMainWindow):
    """Window for displaying and saving sensor data in real-time with automatic logging."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Plot")
        self.setGeometry(200, 200, 1000, 800)
        self.data_list = []
        self.is_recording = False
        self.connection_status = False
        self.serial_connection = None
        self.default_file_path = None
        self.loaded_file_path = None  # Keep track of the loaded file
        self.current_plot_type = "default"  # Tracks whether we are showing "default", "record", or "load"
        self.gain_values = {
            "Glutamate": 0.97,
            "Glutamine": 0.418,
            "Glucose": 0.6854,
            "Lactate": 0.0609
        }

        # Calibration values
        self.calibration_glutamate = 0.0
        self.calibration_glutamine = 0.0
        self.calibration_glucose = 0.0
        self.calibration_lactate = 0.0

        # Set up the matplotlib figure and canvas
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.nav_toolbar = NavigationToolbar(self.canvas, self)

        # Set up the menu bar with "File" and "Sensor" dropdown menus
        menu_bar = self.menuBar()
        
        # File Menu
        file_menu = menu_bar.addMenu("File")
        load_action = QAction("Load New", self)
        load_action.triggered.connect(self.load_file)
        file_menu.addAction(load_action)
        save_action = QAction("Save As", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        # Sensor Menu
        sensor_menu = menu_bar.addMenu("Sensor")
        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self.connect_to_sensor)
        sensor_menu.addAction(connect_action)

        # Start Record action
        self.start_record_action = QAction("Start Record", self, checkable=True)
        self.start_record_action.triggered.connect(self.toggle_record)
        menu_bar.addAction(self.start_record_action)

        # Add Calibrate action to the Sensor Menu
        calibrate_action = QAction("Calibrate", self)
        calibrate_action.triggered.connect(self.calibrate_sensors)
        sensor_menu.addAction(calibrate_action)

        # Status label for connection state
        self.status_label = QLabel("Disconnected")
        self.status_label.setAlignment(Qt.AlignRight)

        # Create a widget to hold the status label and add it to the menu bar
        status_widget = QWidget(self)
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.status_label)
        status_layout.setContentsMargins(0, 3, 20, 0)
        status_widget.setLayout(status_layout)

        # Add the status widget to the right side of the menu bar
        menu_bar.setCornerWidget(status_widget, Qt.TopRightCorner)

    
        gain_layout = QHBoxLayout()
        self.gain_inputs = {}
        for metabolite in ["Glutamate", "Glutamine", "Glucose", "Lactate"]:
            label = QLabel(f"{metabolite} Gain:")
            input_field = QLineEdit()
            input_field.setText(str(self.gain_values[metabolite]))
            input_field.setFixedWidth(60)
            input_field.returnPressed.connect(self.update_gain_values)
            gain_layout.addWidget(label)
            gain_layout.addWidget(input_field)
            self.gain_inputs[metabolite] = input_field

        # Add a horizontal stretch to push the Calibration Settings button to the right
        gain_layout.addStretch()

        # Create and add the Calibration Settings button
        calibration_button = QPushButton("Calibration Settings", self)
        calibration_button.setFixedWidth(140)
        calibration_button.clicked.connect(self.open_calibration_settings)
        gain_layout.addWidget(calibration_button)

        # Combine status and gain layouts into a single box layout
        box_layout = QVBoxLayout()
        box_layout.addLayout(gain_layout)

        # Main layout with plot and controls
        graph_layout = QVBoxLayout()
        graph_layout.addWidget(self.canvas)
        graph_layout.addWidget(self.nav_toolbar)
        graph_layout.addLayout(box_layout)

        # Set up the central widget with main layout
        central_widget = QWidget()
        central_widget.setLayout(graph_layout)
        self.setCentralWidget(central_widget)

        self.update_plot()


    def start_datalogger(self):
        """Start the data logger in a separate thread with automatic logging."""
        self.is_recording = True
        self.current_plot_type = "record"  # Set the plot type to record

    def run_datalogger(self, file_path):
        """Run the data logger, save data to file, and log updates to the command line."""
        try:
            print(f"Starting data logger on COM port: {self.selected_port}")
            DataLogger = PotentiostatReader(com_port=self.selected_port, baud_rate=9600, timeout=0.5, output_filename=file_path)
            with open(file_path, "w") as file:
                while self.connection_status:
                    self.data_list = DataLogger.run()
                    QTimer.singleShot(0, lambda: self.update_plot(file_path))
                    print(f"Logged data {self.data_list}")
                    time.sleep(1)
        except Exception as e:
            print(f"Error during data logging: {str(e)}")


    def update_plot(self, file_path=None):
        """Update the plot with data from the specified file or show default if no file is provided."""
        if file_path is None:
            # Show default sine wave plot
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            x = np.linspace(0, 10, 100)
            y = np.sin(x)
            ax.plot(x, y, label="Default Sine Wave")
            ax.set_xlabel("X-axis")
            ax.set_ylabel("Y-axis")
            ax.set_title("Default Plot: Sine Wave")
            ax.legend()
            ax.grid(True)
            self.current_plot_type = "default"  # Set the plot type to default
            self.figure.subplots_adjust(top=0.955, bottom=0.066, left=0.079, right=0.990)
            self.canvas.draw()
        else:
            # Process loaded file or recorded data file
            self.figure.clear()
            self.current_plot_type = "load" if file_path == self.loaded_file_path else "record"

            # Implement the file loading logic specific to your file structure
            with open(file_path, "r", newline="") as file:
                lines = file.readlines()
            data = [line.strip().split("\t") for line in lines]
            df = pd.DataFrame(data)
            df = df.loc[:, :8]
            new_header = df.iloc[1]
            df = df[3:]
            df.columns = new_header

            index = []
            for i in range(3, len(df) + 2):
                a = df.loc[i, "counter"]
                if not a.isdigit():
                    index.append(i)
                    break

            df2 = df.loc[0 : index[0] - 1, :]
            df2 = df2.apply(pd.to_numeric)

            glutamate = df2["#1ch1"] - df2["#1ch2"]
            glutamine = df2["#1ch3"] - df2["#1ch1"]
            glucose = df2["#1ch5"] - df2["#1ch4"]
            lactate = df2["#1ch6"] - df2["#1ch4"]

            results = pd.DataFrame({
                "Glutamate": glutamate * self.gain_values["Glutamate"],
                "Glutamine": glutamine * self.gain_values["Glutamine"],
                "Glucose": glucose * self.gain_values["Glucose"],
                "Lactate": lactate * self.gain_values["Lactate"],
            })

            ax = self.figure.add_subplot(111)
            for column in results.columns:
                ax.plot(df2["t[min]"], results[column], label=column)

            ax.set_xlabel("Time (minutes)")
            ax.set_ylabel("mA")
            ax.set_title("Time Series Data for Selected Channels")
            ax.legend()
            ax.grid(True)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=12))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=12))

            # Apply tight layout
            self.figure.subplots_adjust(top=0.955, bottom=0.066, left=0.079, right=0.990)
            self.canvas.draw()

    def calibrate_sensors(self):
        """Perform calibration of the sensors based on current data values."""
        if not self.is_recording:
            QMessageBox.warning(self, "Calibration Error", "Calibration can only be performed during data recording.")
            return
        try:
            # Extract the current values from data_list
            current_glutamate = self.data_list[0] - self.data_list[1]
            current_glutamine = self.data_list[2] - self.data_list[0]
            current_glucose = self.data_list[4] - self.data_list[3]
            current_lactate = self.data_list[5] - self.data_list[3]

            # Update gain values based on calibration
            if self.calibration_glutamate > 0:
                self.gain_values["Glutamate"] = self.calibration_glutamate / current_glutamate
            if self.calibration_glutamine > 0:
                self.gain_values["Glutamine"] = self.calibration_glutamine / current_glutamine
            if self.calibration_glucose > 0:
                self.gain_values["Glucose"] = self.calibration_glucose / current_glucose
            if self.calibration_lactate > 0:
                self.gain_values["Lactate"] = self.calibration_lactate / current_lactate

            QMessageBox.information(self, "Calibration", "Calibration completed successfully.")
            if self.parent:
                self.parent.add_to_display("Calibration completed and gain values updated.")
            self.update_gain_values()
        except Exception as e:
            QMessageBox.critical(self, "Calibration Error", f"Failed to calibrate sensors: {str(e)}")

    def open_calibration_settings(self):
        """Open the Calibration Settings dialog."""
        dialog = CalibrationSettingsDialog(self)
        dialog.exec_()
        if self.parent:
            self.parent.add_to_display("Calibration settings updated.")

    def save_file(self):
        """Save a copy of the current data file to a specified location based on current plot type."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Text Files (*.txt)")
        if file_path:
            try:
                if file_path.endswith(".txt"):
                    if self.current_plot_type == "record" and self.default_file_path:
                        # Save the recorded file
                        with open(self.default_file_path, "r") as source_file:
                            with open(file_path, "w") as dest_file:
                                dest_file.write(source_file.read())
                        QMessageBox.information(self, "Success", f"Data successfully saved to {file_path}")
                    elif self.current_plot_type == "load" and self.loaded_file_path:
                        # Save the loaded file
                        with open(self.loaded_file_path, "r") as source_file:
                            with open(file_path, "w") as dest_file:
                                dest_file.write(source_file.read())
                        QMessageBox.information(self, "Success", f"Data successfully saved to {file_path}")
                    else:
                        QMessageBox.warning(self, "Warning", "No data available to save for the default plot.")
                else:
                    QMessageBox.warning(self, "Warning", "Please use a .txt extension to save the data.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def load_file(self):
        """Open a file dialog to select a file and load it into the plot."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            self.loaded_file_path = file_path  # Track the loaded file path
            self.update_plot(file_path)  # Load and plot the selected file

    def toggle_record(self):
        """Toggle the recording state and start/stop data logging with user-specified file name."""
        if self.start_record_action.isChecked():
            if self.connection_status:
                # Ensure the 'Recorded_Files' folder exists
                recorded_folder = "Recorded_Files"
                os.makedirs(recorded_folder, exist_ok=True)

                # Prompt the user to choose a file name
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save Recorded Data",
                    os.path.join(recorded_folder, "Sensor_readings.txt"),
                    "Text Files (*.txt)"
                )

                if file_path:
                    # Start data logging with the chosen file path
                    self.is_recording = True
                    self.current_record_file_path = file_path
                    threading.Thread(target=self.run_datalogger, args=(file_path,), daemon=True).start()
                else:
                    # User canceled the file dialog, uncheck the record action
                    self.start_record_action.setChecked(False)
            else:
                QMessageBox.warning(self, "Warning", "Please connect to the sensor before recording.")
                self.start_record_action.setChecked(False)
        else:
            # Stop recording
            self.is_recording = False

    def connect_to_sensor(self):
        """Open a dialog to select a COM port and connect to the sensor."""
        ports = [port.device for port in list_ports.comports()]
        if not ports:
            QMessageBox.warning(self, "No Ports Found", "No COM ports are available.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Select COM Port")

        layout = QVBoxLayout()
        port_selector = QComboBox()
        port_selector.addItems(ports)
        layout.addWidget(QLabel("Available COM Ports:"))
        layout.addWidget(port_selector)

        connect_button = QPushButton("Connect")
        connect_button.clicked.connect(lambda: self.establish_connection(dialog, port_selector.currentText()))
        layout.addWidget(connect_button)

        dialog.setLayout(layout)
        dialog.exec_()

    def establish_connection(self, dialog, selected_port):
        """Establish a connection to the selected COM port and start continuous logging."""
        try:
            # Attempt to connect to the selected COM port
            self.serial_connection = serial.Serial(selected_port, baudrate=9600, timeout=1)
            self.selected_port = selected_port
            self.connection_status = True
            self.status_label.setText("Connected")
            dialog.accept()

            # Print the successful connection message
            print(f"Connected to COM port: {self.selected_port}")

            # Start continuous logging in a separate thread
            logger_folder = "Sensor_Readings"
            os.makedirs(logger_folder, exist_ok=True)
            current_time = datetime.now()
            filename = f"Sensor_readings_{current_time.strftime('%d_%m_%y_%H_%M')}.txt"
            log_file_path = os.path.join(logger_folder,filename)
            threading.Thread(target=self.run_datalogger, args=(log_file_path,), daemon=True).start()

            # Inform the user of successful connection
            QMessageBox.information(self, "Info", "Connected to sensor and started continuous logging.")
        except serial.SerialException as e:
            # Handle connection error
            QMessageBox.critical(self, "Connection Error", f"Could not connect to {selected_port}.\nError: {e}")
            self.status_label.setText("Disconnected")
            self.selected_port = None




    def update_gain_values(self):
        """Update gain values based on user input and re-plot the data."""
        for metabolite, input_field in self.gain_inputs.items():
            try:
                new_value = float(input_field.text())
                self.gain_values[metabolite] = new_value
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", f"Please enter a valid number for {metabolite} gain.")
                return
        # Re-plot based on current mode (recording, loaded file, or default)
        if self.loaded_file_path:
            self.update_plot(self.loaded_file_path)
        elif self.is_recording:
            self.update_plot(self.default_file_path)
        else:
            self.update_plot()

class SettingsDialog(QDialog):
    """Settings window to adjust t_sampling and t_buffer."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.parent = parent  # Store the reference to the parent AMUZAGUI

        # Layout for the form
        layout = QFormLayout()

        # Spin boxes for t_sampling and t_buffer
        self.sampling_time_spinbox = QSpinBox()
        self.sampling_time_spinbox.setRange(1, 1000)
        self.sampling_time_spinbox.setValue(t_sampling)

        self.buffer_time_spinbox = QSpinBox()
        self.buffer_time_spinbox.setRange(1, 1000)
        self.buffer_time_spinbox.setValue(t_buffer)

        # Add to layout
        layout.addRow("Sampling Time (t_sampling):", self.sampling_time_spinbox)
        layout.addRow("Buffer Time (t_buffer):", self.buffer_time_spinbox)

        # Add Ok and Cancel buttons
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept_settings)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def accept_settings(self):
        """Update t_sampling and t_buffer when OK is pressed."""
        global t_sampling, t_buffer
        t_sampling = self.sampling_time_spinbox.value()
        t_buffer = self.buffer_time_spinbox.value()
        super().accept()

class CalibrationSettingsDialog(QDialog):
    """Dialog for adjusting calibration values for each metabolite."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration Settings")

        # Layout for the form
        layout = QFormLayout()

        # Get the current calibration values from the parent (PlotWindow)
        self.parent = parent

        # Calibration input fields for each metabolite
        self.calibration_inputs = {}
        for metabolite in ["Glutamate", "Glutamine", "Glucose", "Lactate"]:
            label = QLabel(f"{metabolite} Calibration:")
            input_field = QLineEdit()

            # Set the input field to the current calibration value
            current_value = getattr(self.parent, f"calibration_{metabolite.lower()}", 0.0)
            input_field.setText(str(current_value))

            layout.addRow(label, input_field)
            self.calibration_inputs[metabolite] = input_field

        # Ok button
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def accept(self):
        """Save calibration values when OK is pressed."""
        parent = self.parent
        if parent:
            try:
                # Update calibration values in the parent
                parent.calibration_glutamate = float(self.calibration_inputs["Glutamate"].text())
                parent.calibration_glutamine = float(self.calibration_inputs["Glutamine"].text())
                parent.calibration_glucose = float(self.calibration_inputs["Glucose"].text())
                parent.calibration_lactate = float(self.calibration_inputs["Lactate"].text())
                QMessageBox.information(self, "Success", "Calibration values updated successfully.")
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers for calibration values.")
        super().accept()

class AMUZAGUI(QWidget):
    def __init__(self):
        super().__init__()

        # Set up the window
        self.setWindowTitle("AMUZA Controller")
        self.setGeometry(100, 100, 900, 400)
        self.setFixedSize(900, 500) #Prevents the window from being resized 

        # Main layout - Horizontal
        self.main_layout = QHBoxLayout(self)

        # Left side layout for commands
        self.command_layout = QVBoxLayout()

        # Display screen at the top left for showing output text with history
        self.display_screen = QTextEdit(self)
        self.display_screen.setReadOnly(True)
        self.display_screen.setFixedHeight(230)  # Set height to 160 pixels
        self.display_screen.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # Add vertical scroll bar
        self.command_layout.addWidget(self.display_screen)

        # Store display history
        self.display_history = []

        # Connect button
        self.connect_button = QPushButton("Connect to AMUZA", self)
        self.connect_button.clicked.connect(self.connect_to_amuza)
        self.command_layout.addWidget(self.connect_button)

        # Control buttons (initially greyed out and disabled)
        self.start_datalogger_button = QPushButton("Start DataLogger", self)
        self.start_datalogger_button.setEnabled(False)
        self.start_datalogger_button.setStyleSheet("background-color: lightgrey")
        self.start_datalogger_button.clicked.connect(self.open_plot_window)
        self.command_layout.addWidget(self.start_datalogger_button)

        self.insert_button = QPushButton("INSERT", self)
        self.insert_button.setEnabled(False)
        self.insert_button.setStyleSheet("background-color: lightgrey")
        self.insert_button.clicked.connect(self.on_insert)
        self.command_layout.addWidget(self.insert_button)

        self.eject_button = QPushButton("EJECT", self)
        self.eject_button.setEnabled(False)
        self.eject_button.setStyleSheet("background-color: lightgrey")
        self.eject_button.clicked.connect(self.on_eject)
        self.command_layout.addWidget(self.eject_button)

        self.runplate_button = QPushButton("RUNPLATE", self)
        self.runplate_button.setEnabled(False)
        self.runplate_button.setStyleSheet("background-color: lightgrey")
        self.runplate_button.clicked.connect(self.on_runplate)
        self.command_layout.addWidget(self.runplate_button)

        self.move_button = QPushButton("MOVE", self)
        self.move_button.setEnabled(False)
        self.move_button.setStyleSheet("background-color: lightgrey")
        self.move_button.clicked.connect(self.on_move)
        self.command_layout.addWidget(self.move_button)

        # Settings button
        self.settings_button = QPushButton("Settings", self)
        self.settings_button.clicked.connect(self.open_settings_dialog)
        self.command_layout.addWidget(self.settings_button)

        # Add the command layout to the main layout (on the left side)
        self.main_layout.addLayout(self.command_layout)

        # Right side layout for the well plate
        self.plate_layout = QGridLayout()
        self.well_labels = {}
        self.start_row, self.start_col = None, None
        self.is_dragging = False

        self.setup_well_plate()

        # Add the well plate layout to the main layout (on the right side)
        self.main_layout.addLayout(self.plate_layout)

        # Set the layout for the QWidget
        self.setLayout(self.main_layout)

    def setup_well_plate(self):
        """Create a grid of 8x12 QLabel items representing the well plate."""
        rows = "ABCDEFGH"
        columns = range(1, 13)

        for i, row in enumerate(rows):
            for j, col in enumerate(columns):
                well_id = f"{row}{col}"
                label = WellLabel(well_id)
                self.well_labels[(i, j)] = label
                self.plate_layout.addWidget(label, i, j)

        # Add Clear button at the bottom spanning the full width
        clear_button = QPushButton("Clear", self)
        clear_button.clicked.connect(self.clear_plate_selection)
        self.plate_layout.addWidget(clear_button, len(rows), 0, 1, len(columns))

    def clear_plate_selection(self):
        """Clear all selected wells (both drag and Ctrl+Click selections)."""
        for label in self.well_labels.values():
            label.deselect()
            label.ctrl_deselect()
        selected_wells.clear()
        ctrl_selected_wells.clear()

    def add_to_display(self, message):
        """Add a new message to the display history and update the display screen."""
        self.display_history.append(message)
        # Limit history to last 50 messages for readability
        self.display_history = self.display_history[-50:]
        # Display the history in the QTextEdit
        self.display_screen.setPlainText("\n".join(self.display_history))
    
    def order(self, well_positions):
        """Orders the selction sequence to run from A1 to A12 down till G12"""
        sorted_well_positions = sorted(well_positions, key=lambda x: (x[0], int(x[1:])))
        return sorted_well_positions

    def on_runplate(self):
        """Display the selected wells for RUNPLATE in the console and display screen."""
        if selected_wells:
            self.well_list = self.order(list(selected_wells))
            self.add_to_display(f"Running Plate on wells: {', '.join(self.well_list)}\nSampled:")
            if connection is None:
                QMessageBox.critical(self, "Error", "Please connect to AMUZA first!")
                return

            # Reset method list
            self.method = []
            # Adjust temperature before starting
            connection.AdjustTemp(6)
            # Map the wells and create method sequences
            locations = connection.well_mapping(self.well_list)
            for loc in locations:
                # Append the method sequence for each location
                self.method.append(AMUZA_Master.Sequence([AMUZA_Master.Method([loc], t_sampling)]))
            # Start the Control_Move process
            self.Control_Move(self.method, t_sampling)

        else:
            self.add_to_display("No wells selected for RUNPLATE.")

    def on_move(self):
        """Display the selected wells for MOVE in the console and display screen."""
        if ctrl_selected_wells:
            self.well_list = self.order(list(ctrl_selected_wells))
            self.add_to_display(f"Moving to wells: {', '.join(self.well_list)}")
            self.add_to_display(f"Sampled: ")
            if connection is None:
                QMessageBox.critical(self, "Error", "Please connect to AMUZA first!")
                return
            # Reset method list
            self.method = []
            
            # Adjust temperature before moving
            connection.AdjustTemp(6)

            # Map the wells and move
            locations = connection.well_mapping(self.well_list)
            for loc in locations:
                # Append the method sequence for each location
                self.method.append(AMUZA_Master.Sequence([AMUZA_Master.Method([loc], t_sampling)]))
            # Start the Control_Move process
            self.Control_Move(self.method, t_sampling)
        else:
            self.add_to_display("No wells selected for MOVE.")

    def Control_Move(self, method, duration):
        """Control the movement through wells using QTimer for non-blocking execution."""
        self.current_index = 0  # Track the current well index
        self.method = method
        self.duration = duration

        # Create a QTimer for handling the well movement
        self.move_timer = QTimer(self)
        self.move_timer.timeout.connect(self.execute_move)
        self.move_timer.start(t_buffer * 1000)  # Start timer with initial buffer time

    def execute_move(self):
        """Execute the move for the current well using QTimer."""
        if self.current_index < len(self.method):
            # Move to the current well and update the display
            current_method = self.method[self.current_index]
            connection.Move(current_method)
            # Get the current text from the display
            current_text = self.display_screen.toPlainText()
            # Update the current line by appending the new well to it
            updated_text = f"{current_text}{self.well_list[self.current_index]}, "
            # Set the updated text back to the display
            self.display_screen.setPlainText(updated_text)
            self.display_screen.moveCursor(self.display_screen.textCursor().End)
            # Increment the index and set a delay before the next move
            self.current_index += 1
            self.move_timer.setInterval((self.duration + 9) * 1000)  # Set interval for duration + delay
        else:
            # Stop the timer when all wells have been processed
            self.move_timer.stop()
            self.add_to_display(f"{', '.join(self.well_list)} Complete.")

    def open_settings_dialog(self):
        """Open the settings dialog to adjust t_sampling and t_buffer."""
        dialog = SettingsDialog(self)
        dialog.exec_()

    def open_plot_window(self):
        """Open a new window to display the data plot."""
        self.plot_window = PlotWindow(self)
        self.plot_window.show()

    def connect_to_amuza(self):
        """Connect to the AMUZA system."""
        global connection
        try:
            connection = AMUZA_Master.AmuzaConnection(True)
            connection.connect()
            QMessageBox.information(self, "Info", "Connected to AMUZA successfully!")
            self.enable_control_buttons()
            self.add_to_display("Connected to AMUZA.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect to AMUZA: {str(e)}")
            connection = None
            self.add_to_display("Failed to connect to AMUZA.")

    def enable_control_buttons(self):
        """Enable the control buttons after successful connection."""
        buttons = [
            self.start_datalogger_button, self.insert_button, 
            self.eject_button, self.runplate_button, self.move_button
        ]
        for button in buttons:
            button.setEnabled(True)
            button.setStyleSheet("")

    def on_insert(self):
        if connection is None:
            QMessageBox.critical(self, "Error", "Please connect to AMUZA first!")
            return
        connection.Insert()
        self.add_to_display("Inserting tray.")

    def on_eject(self):
        if connection is None:
            QMessageBox.critical(self, "Error", "Please connect to AMUZA first!")
            return
        connection.Eject()
        self.add_to_display("Ejecting tray.")

    def resizeEvent(self, event):
        """Lock the aspect ratio of the window."""
        width = event.size().width()
        height = event.size().height()
        aspect_ratio = 9 / 4
        new_height = int(width / aspect_ratio)
        self.resize(QSize(width, new_height))
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press event to start a selection or toggle a single well."""
        if event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                for (i, j), label in self.well_labels.items():
                    if label.geometry().contains(self.mapFromGlobal(event.globalPos())):
                        self.toggle_ctrl_well(i, j)
                        break
            else:
                for (i, j), label in self.well_labels.items():
                    if label.geometry().contains(self.mapFromGlobal(event.globalPos())):
                        self.start_row, self.start_col = i, j
                        self.is_dragging = True
                        self.update_selection(i, j)
                        break

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move event to update the selection during drag."""
        if self.is_dragging:
            for (i, j), label in self.well_labels.items():
                if label.geometry().contains(self.mapFromGlobal(event.globalPos())):
                    self.update_selection(i, j)
                    break

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release event to finish the selection."""
        if self.is_dragging:
            self.is_dragging = False

    def update_selection(self, end_row, end_col):
        """Update the selection from the start position to the current cursor position."""
        min_row, max_row = min(self.start_row, end_row), max(self.start_row, end_row)
        min_col, max_col = min(self.start_col, end_col), max(self.start_col, end_col)
        for label in self.well_labels.values():
            label.deselect()
        for i in range(min_row, max_row + 1):
            for j in range(min_col, max_col + 1):
                self.well_labels[(i, j)].select()
                selected_wells.add(self.well_labels[(i, j)].well_id)

    def toggle_ctrl_well(self, row, col):
        """Toggle the well selection for the MOVE command (Ctrl+Click functionality)."""
        label = self.well_labels[(row, col)]
        well_id = label.well_id
        if well_id in ctrl_selected_wells:
            ctrl_selected_wells.remove(well_id)
            label.ctrl_deselect()
        else:
            ctrl_selected_wells.add(well_id)
            label.ctrl_select()


# Start the application
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AMUZAGUI()
    window.show()
    sys.exit(app.exec_())