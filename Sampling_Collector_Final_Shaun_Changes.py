import sys
import os
import time
import random
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QDialog,
    QTextEdit,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QSpinBox,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QComboBox,
)

# Custom Imports
# from SIX_SERVER_READER import PotentiostatReader  # Uncomment when available
# import AMUZA_Master  # Uncomment when available

# Configure matplotlib
plt.rcParams["axes.grid"] = True  # Enable grid globally for better visualization

# Global variables
t_buffer = 1  # Buffer time in seconds
t_sampling = 10  # Sampling time in seconds
sample_rate = 1  # Data logging sample rate
connection = None  # Placeholder for external connection (e.g., AMUZA device)
selected_wells = set()  # Store wells selected with click-and-drag (RUNPLATE)
ctrl_selected_wells = set()  # Store wells selected with Ctrl+Click (MOVE)


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
        self.setGeometry(200, 200, 1100, 800)

        # Data and state initialization
        self.data_list = []  # Stores incoming data
        self.is_recording = False
        self.connection_status = False
        self.serial_connection = None
        self.default_file_path = None
        self.loaded_file_path = None  # Keep track of the loaded file
        self.current_plot_type = "default"  # Tracks "default", "record", or "load"
        self.gain_values = {
            "Glutamate": 0.97,
            "Glutamine": 0.418,
            "Glucose": 0.6854,
            "Lactate": 0.0609,
        }

        # Calibration values
        self.calibration_glutamate = 1.0
        self.calibration_glutamine = 1.0
        self.calibration_glucose = 1.0
        self.calibration_lactate = 1.0

        # Main layout
        main_layout = QVBoxLayout()

        # Create a vertical layout for the graph (canvas + toolbar)
        graph_layout = QVBoxLayout()

        # Set up the matplotlib figure and canvas
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.nav_toolbar = NavigationToolbar(self.canvas, self)

        # Add the canvas and navigation toolbar to the graph layout
        graph_layout.addWidget(self.canvas)
        graph_layout.addWidget(self.nav_toolbar)

        # Create a QTextEdit widget for instructions
        self.instructions_text = QTextEdit(self)
        self.instructions_text.setReadOnly(True)
        self.instructions_text.setStyleSheet(
            "background-color: #F7F7F7; border: 1px solid #D0D0D0;"
        )
        self.instructions_text.setText(
            "Plot Instructions:\n"
            "1. Connect the Sensor:\n"
            "    o Click 'Connect to AMUZA' in the main window.\n\n"
            "2. Click 'Start DataLogger' to open the plotting window.\n\n"
            "3. Calibrate the Gain Values:\n"
            "    o Click 'Calibration Settings' to set expected concentrations.\n\n"
            "4. Use 'Load File' to load a saved graph.\n\n"
            "5. Use the toolbar for zooming and panning.\n\n"
            "6. Modify the gain values at the bottom for quick changes to the plot."
        )
        self.instructions_text.setFixedWidth(300)

        # Combine graph and instructions layout
        plot_instructions_layout = QHBoxLayout()
        plot_instructions_layout.addLayout(graph_layout)
        plot_instructions_layout.addWidget(self.instructions_text)

        # Gain input layout
        self.gain_inputs = {}
        gain_layout = QHBoxLayout()
        for metabolite in ["Glutamate", "Glutamine", "Glucose", "Lactate"]:
            label = QLabel(f"{metabolite} Gain:")
            input_field = QLineEdit()
            input_field.setText(str(self.gain_values[metabolite]))
            input_field.setFixedWidth(60)
            input_field.returnPressed.connect(self.update_gain_values)
            gain_layout.addWidget(label)
            gain_layout.addWidget(input_field)
            self.gain_inputs[metabolite] = input_field

        # Add Calibration Settings button
        calibration_button = QPushButton("Calibration Settings", self)
        calibration_button.setFixedWidth(140)
        calibration_button.clicked.connect(self.open_calibration_settings)
        gain_layout.addWidget(calibration_button)

        # Add the graph, instructions, and gain layout
        main_layout.addLayout(plot_instructions_layout)
        main_layout.addLayout(gain_layout)

        # Set up the central widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Initialize the plot and set up animation
        self.lines = {}  # Store line objects for each metabolite
        self.init_plot()
        self.animation = FuncAnimation(
            self.figure, self.update_plot, interval=1000, blit=True
        )

    def init_plot(self):
        """Initialize the plot with empty lines for each metabolite."""
        self.ax.clear()
        self.ax.set_title("Real-Time Metabolite Data")
        self.ax.set_xlabel("Time (minutes)")
        self.ax.set_ylabel("Signal (mA)")
        self.current_plot_type = "default"
        self.ax.grid(True)

        for metabolite in ["Glutamate", "Glutamine", "Glucose", "Lactate"]:
            (line,) = self.ax.plot([], [], label=metabolite)
            self.lines[metabolite] = line

        self.ax.legend()

    def update_plot(self, frame):
        """Update the plot with new data."""
        if not self.data_list:
            return self.lines.values()  # Return line objects for blitting

        time_data = list(range(len(self.data_list)))
        for metabolite, line in self.lines.items():
            metabolite_data = [d[metabolite] for d in self.data_list]
            line.set_data(time_data, metabolite_data)

        # Adjust axes limits
        self.ax.relim()
        self.ax.autoscale_view()

        return self.lines.values()  # Return updated lines for blitting

    def update_gain_values(self):
        """Update gain values from user input."""
        for metabolite, input_field in self.gain_inputs.items():
            try:
                new_value = float(input_field.text())
                self.gain_values[metabolite] = new_value
                # Apply gain to existing data
                self.data_list = [
                    {
                        k: (v * self.gain_values[k] if k == metabolite else v)
                        for k, v in d.items()
                    }
                    for d in self.data_list
                ]
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    f"Please enter a valid number for {metabolite} gain.",
                )
                return
        self.update_plot(None)

    def plot_loaded_file(self, file_path):
        """Plot data from the loaded file."""
        self.current_plot_type = "load" if file_path else "record"

        # Implement the file loading logic specific to your file structure
        try:
            df = pd.read_csv(file_path, delimiter="\t", skiprows=3)
            glutamate = df["#1ch1"] - df["#1ch2"]
            glutamine = df["#1ch3"] - df["#1ch1"]
            glucose = df["#1ch5"] - df["#1ch4"]
            lactate = df["#1ch6"] - df["#1ch4"]

            results = pd.DataFrame(
                {
                    "Glutamate": glutamate * self.gain_values["Glutamate"],
                    "Glutamine": glutamine * self.gain_values["Glutamine"],
                    "Glucose": glucose * self.gain_values["Glucose"],
                    "Lactate": lactate * self.gain_values["Lactate"],
                }
            )

            self.ax.clear()
            for column in results.columns:
                self.ax.plot(df["t[min]"], results[column], label=column)

            self.ax.set_xlabel("Time (minutes)")
            self.ax.set_ylabel("mA")
            self.ax.set_title("Time Series Data for Selected Channels")
            self.ax.legend()
            self.ax.grid(True)
            self.ax.xaxis.set_major_locator(plt.MaxNLocator(nbins=12))
            self.ax.yaxis.set_major_locator(plt.MaxNLocator(nbins=12))

            self.canvas.draw()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def write_data_to_file(self, data):
        """Write mock or live data to the specified file."""
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w") as file:
                file.write("Time\tGlutamate\tGlutamine\tGlucose\tLactate\n")

        with open(self.file_path, "a") as file:
            current_time = datetime.now().strftime("%H:%M:%S")
            line = f"{current_time}\t{data['Glutamate']}\t{data['Glutamine']}\t{data['Glucose']}\t{data['Lactate']}\n"
            file.write(line)

    def open_calibration_settings(self):
        """Open the Calibration Settings dialog."""
        dialog = CalibrationSettingsDialog(self)
        dialog.exec_()
        self.update_gain_values()


class SettingsDialog(QDialog):
    """Settings window to adjust t_sampling and t_buffer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.parent = parent  # Reference to PlotWindow

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
        layout.addRow("Sampling Time (s):", self.sampling_time_spinbox)
        layout.addRow("Buffer Time (s):", self.buffer_time_spinbox)

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
            label = QLabel(f"{metabolite} [mM]")
            input_field = QLineEdit()

            # Set the input field to the current calibration value
            current_value = getattr(
                self.parent, f"calibration_{metabolite.lower()}", 0.0
            )
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
                parent.calibration_glutamate = float(
                    self.calibration_inputs["Glutamate"].text()
                )
                parent.calibration_glutamine = float(
                    self.calibration_inputs["Glutamine"].text()
                )
                parent.calibration_glucose = float(
                    self.calibration_inputs["Glucose"].text()
                )
                parent.calibration_lactate = float(
                    self.calibration_inputs["Lactate"].text()
                )
                QMessageBox.information(
                    self, "Success", "Calibration values updated successfully."
                )
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Please enter valid numbers for calibration values.",
                )
        super().accept()


class AMUZAGUI(QWidget):
    """Main GUI controller for the AMUZA system."""

    def __init__(self):
        super().__init__()

        # Set up the window
        self.setWindowTitle("AMUZA Controller")
        self.setGeometry(100, 100, 1250, 500)
        self.setFixedSize(1250, 500)  # Prevents the window from being resized

        # Main layout - Horizontal
        self.main_layout = QHBoxLayout(self)

        # Left side layout for commands
        self.command_layout = QVBoxLayout()

        # Display screen at the top left for showing output text with history
        self.display_screen = QTextEdit(self)
        self.display_screen.setReadOnly(True)
        self.display_screen.setFixedHeight(230)  # Set height to 230 pixels
        self.display_screen.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOn
        )  # Add vertical scroll bar
        self.command_layout.addWidget(self.display_screen)

        # Store display history
        self.display_history = []

        # Button styling
        rounded_button_style = """
            QPushButton {
                background-color: #FDFDFD ; /* Light grey background */
                border: 1px solid #D0D0D0; /* Neutral grey border */
                border-radius: 10px; /* Slight rounding of the corners */
                padding: 2px 8px; /* Adjusted padding for a more compact look */
                font-size: 13px; /* Smaller font size */
                max-width: 170px; /* Maximum width to fit the text comfortably */
                max-height: 32px; /* Maximum height for a smaller button */
            }
            QPushButton:hover {
                background-color: #C0C0C0; /* Darker grey on hover */
            }
            QPushButton:pressed {
                background-color: #D3D3D3; /* Even darker grey when pressed */
            }
        """

        # Connect button
        self.connect_button = QPushButton("Connect to AMUZA", self)
        self.connect_button.setStyleSheet(rounded_button_style)
        self.connect_button.clicked.connect(self.connect_to_amuza)
        self.command_layout.addWidget(self.connect_button)

        # Control buttons (initially greyed out and disabled)
        self.start_datalogger_button = QPushButton("Start DataLogger", self)
        self.start_datalogger_button.setEnabled(False)
        self.start_datalogger_button.setStyleSheet(rounded_button_style)
        self.start_datalogger_button.clicked.connect(self.open_plot_window)
        self.command_layout.addWidget(self.start_datalogger_button)

        self.insert_button = QPushButton("INSERT", self)
        self.insert_button.setEnabled(False)
        self.insert_button.setStyleSheet(rounded_button_style)
        self.insert_button.clicked.connect(self.on_insert)
        self.command_layout.addWidget(self.insert_button)

        self.eject_button = QPushButton("EJECT", self)
        self.eject_button.setEnabled(False)
        self.eject_button.setStyleSheet(rounded_button_style)
        self.eject_button.clicked.connect(self.on_eject)
        self.command_layout.addWidget(self.eject_button)

        self.runplate_button = QPushButton("RUNPLATE", self)
        self.runplate_button.setEnabled(False)
        self.runplate_button.setStyleSheet(rounded_button_style)
        self.runplate_button.clicked.connect(self.on_runplate)
        self.command_layout.addWidget(self.runplate_button)

        self.move_button = QPushButton("MOVE", self)
        self.move_button.setEnabled(False)
        self.move_button.setStyleSheet(rounded_button_style)
        self.move_button.clicked.connect(self.on_move)
        self.command_layout.addWidget(self.move_button)

        # Settings button
        self.settings_button = QPushButton("Settings", self)
        self.settings_button.setStyleSheet(rounded_button_style)
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

        # Instructions panel (right side)
        self.instructions_panel = QTextEdit(self)
        self.instructions_panel.setReadOnly(True)
        self.instructions_panel.setFixedWidth(350)  # Adjust width as needed
        self.instructions_panel.setStyleSheet(
            "background-color: #F7F7F7; border: 1px solid #D0D0D0;"
        )
        self.instructions_panel.setText(
            "Instructions:\n"
            "1. Connect to AMUZA using the 'Connect to AMUZA' button.\n"
            "\n"
            "2. Use 'EJECT' to remove the tray from inside the AMUZA and 'INSERT' to insert it.\n"
            "\n"
            "3. Select the well sampling area by clicking and dragging across the wells.\n"
            "\n"
            "4. Use 'RUNPLATE' to sample the selected wells in sequence.\n"
            "\n"
            "5. Select individual wells by Ctrl+Click for 'MOVE'.\n"
            "\n"
            "6. Use 'MOVE' to sample the selected wells in order.\n"
            "\n"
            "7. Use 'Settings' to adjust sampling and buffer times.\n"
            "\n"
            "8. Click 'Start DataLogger' to open the plotting window.\n"
            "\n"
            "9. Review messages and logs in the display panel."
            "\n"
            "\n"
            "Coded By: Noah Bernten         Noah.Bernten@mail.huji.ac.il"
        )

        # Add the well plate layout and instructions to the main layout
        self.main_layout.addLayout(self.plate_layout)
        self.main_layout.addWidget(self.instructions_panel)

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
        clear_button.setFixedHeight(40)
        clear_button.clicked.connect(self.clear_plate_selection)
        self.plate_layout.addWidget(clear_button, len(rows), 0, 1, len(columns))

    def clear_plate_selection(self):
        """Clear all selected wells (both drag and Ctrl+Click selections)."""
        for label in self.well_labels.values():
            label.deselect()
            label.ctrl_deselect()
        selected_wells.clear()
        ctrl_selected_wells.clear()
        self.add_to_display("All well selections cleared.")

    def add_to_display(self, message):
        """Add a new message to the display history and update the display screen."""
        self.display_history.append(message)
        # Limit history to last 50 messages for readability
        self.display_history = self.display_history[-50:]
        # Display the history in the QTextEdit
        self.display_screen.setPlainText("\n".join(self.display_history))

    def order(self, well_positions):
        """Orders the selection sequence to run from A1 to A12 down till H12."""
        sorted_well_positions = sorted(well_positions, key=lambda x: (x[0], int(x[1:])))
        return sorted_well_positions

    def apply_button_style(self, button):
        """Reapply the custom rounded style to the button."""
        rounded_button_style = """
            QPushButton {
                background-color: #FDFDFD ; /* Light grey background */
                border: 1px solid #D0D0D0; /* Neutral grey border */
                border-radius: 10px; /* Slight rounding of the corners */
                padding: 2px 8px; /* Adjusted padding for a more compact look */
                font-size: 13px; /* Smaller font size */
                max-width: 170px; /* Maximum width to fit the text comfortably */
                max-height: 32px; /* Maximum height for a smaller button */
            }
            QPushButton:hover {
                background-color: #C0C0C0; /* Darker grey on hover */
            }
            QPushButton:pressed {
                background-color: #D3D3D3; /* Even darker grey when pressed */
            }
        """
        button.setStyleSheet(rounded_button_style)

    def on_runplate(self):
        """Display the selected wells for RUNPLATE in the console and display screen."""
        if selected_wells:
            self.well_list = self.order(list(selected_wells))
            self.add_to_display(
                f"Running Plate on wells: {', '.join(self.well_list)}\nSampled:"
            )
            if connection is None:
                QMessageBox.critical(self, "Error", "Please connect to AMUZA first!")
                return

            # Reset method list
            self.method = []
            # Adjust temperature before starting (Placeholder)
            # connection.AdjustTemp(6)
            # Map the wells and create method sequences (Placeholder)
            # locations = connection.well_mapping(self.well_list)
            # for loc in locations:
            #     self.method.append(
            #         AMUZA_Master.Sequence([AMUZA_Master.Method([loc], t_sampling)])
            #     )
            # Start the Control_Move process (Placeholder)
            # self.Control_Move(self.method, t_sampling)

            # Since AMUZA_Master and actual connection are not defined,
            # we'll simulate the sampling process
            for well in self.well_list:
                self.add_to_display(f"Sampled well: {well}")
                time.sleep(t_sampling)  # Simulate sampling time

            self.add_to_display(f"{', '.join(self.well_list)} Complete.")
        else:
            self.add_to_display("No wells selected for RUNPLATE.")

    def on_move(self):
        """Display the selected wells for MOVE in the console and display screen."""
        if ctrl_selected_wells:
            self.well_list = self.order(list(ctrl_selected_wells))
            self.add_to_display(f"Moving to wells: {', '.join(self.well_list)}")
            self.add_to_display("Sampled:")
            if connection is None:
                QMessageBox.critical(self, "Error", "Please connect to AMUZA first!")
                return

            # Reset method list
            self.method = []
            # Adjust temperature before moving (Placeholder)
            # connection.AdjustTemp(6)
            # Map the wells and move (Placeholder)
            # locations = connection.well_mapping(self.well_list)
            # for loc in locations:
            #     self.method.append(
            #         AMUZA_Master.Sequence([AMUZA_Master.Method([loc], t_sampling)])
            #     )
            # Start the Control_Move process (Placeholder)
            # self.Control_Move(self.method, t_sampling)

            # Simulate moving and sampling
            for well in self.well_list:
                self.add_to_display(f"Sampled well: {well}")
                time.sleep(t_sampling)  # Simulate sampling time

            self.add_to_display(f"{', '.join(self.well_list)} Complete.")
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
            # Move to the current well and update the display (Placeholder)
            current_method = self.method[self.current_index]
            connection.Move(current_method)  # Placeholder

            # Update the display
            current_text = self.display_screen.toPlainText()
            updated_text = f"{current_text}{self.well_list[self.current_index]}, "
            self.display_screen.setPlainText(updated_text)
            self.display_screen.moveCursor(self.display_screen.textCursor().End)

            # Increment the index and set a delay before the next move
            self.current_index += 1
            self.move_timer.setInterval(
                (self.duration + 9) * 1000
            )  # Set interval for duration + delay
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
            # connection = AMUZA_Master.AmuzaConnection(True)
            # connection.connect()
            # Placeholder for actual connection
            connection = True  # Simulate successful connection
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
            self.start_datalogger_button,
            self.insert_button,
            self.eject_button,
            self.runplate_button,
            self.move_button,
        ]
        for button in buttons:
            button.setEnabled(True)
            self.apply_button_style(button)

    def on_insert(self):
        """Handle the INSERT button click."""
        if connection is None:
            QMessageBox.critical(self, "Error", "Please connect to AMUZA first!")
            return
        # connection.Insert()  # Placeholder
        self.add_to_display("Inserting tray.")

    def on_eject(self):
        """Handle the EJECT button click."""
        if connection is None:
            QMessageBox.critical(self, "Error", "Please connect to AMUZA first!")
            return
        # connection.Eject()  # Placeholder
        self.add_to_display("Ejecting tray.")

    def resizeEvent(self, event):
        """Lock the aspect ratio of the window."""
        width = event.size().width()
        aspect_ratio = 9 / 4
        new_height = int(width / aspect_ratio)
        self.resize(QSize(width, new_height))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
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

    def mouseMoveEvent(self, event):
        """Handle mouse move event to update the selection during drag."""
        if self.is_dragging:
            for (i, j), label in self.well_labels.items():
                if label.geometry().contains(self.mapFromGlobal(event.globalPos())):
                    self.update_selection(i, j)
                    break

    def mouseReleaseEvent(self, event):
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
        self.add_to_display(f"Selected wells: {', '.join(selected_wells)}")

    def toggle_ctrl_well(self, row, col):
        """Toggle the well selection for the MOVE command (Ctrl+Click functionality)."""
        label = self.well_labels[(row, col)]
        well_id = label.well_id
        if well_id in ctrl_selected_wells:
            ctrl_selected_wells.remove(well_id)
            label.ctrl_deselect()
            self.add_to_display(f"Deselected well: {well_id}")
        else:
            ctrl_selected_wells.add(well_id)
            label.ctrl_select()
            self.add_to_display(f"Selected well for MOVE: {well_id}")


class DataRecordThread(QThread):
    """Thread for recording data to a file."""

    def __init__(self, data_list, record_file_path, parent=None):
        super().__init__(parent)
        self.data_list = data_list
        self.record_file_path = record_file_path
        self.recording = True

    def run(self):
        try:
            with open(self.record_file_path, "a") as file:  # Open in append mode
                counter = 1
                start_time = time.time()

                while self.recording:
                    if self.data_list:
                        # Calculate elapsed time in minutes
                        elapsed_time = (time.time() - start_time) / 60
                        elapsed_time_str = f"{elapsed_time:.3f}"
                        data_str = "\t".join(map(str, self.data_list))
                        line = f"{counter}\t{elapsed_time_str}\t{data_str}\n"
                        file.write(line)
                        file.flush()
                        counter += 1
                    self.msleep(1000)  # Record every 1 second
        except Exception as e:
            print(f"Error while writing record data: {str(e)}")

    def stop(self):
        """Stop recording."""
        self.recording = False


class DataLoggerThread(QThread):
    """Thread for logging data from the sensor."""

    data_logged = pyqtSignal(list)  # Signal to emit the data to the main thread

    def __init__(self, selected_port, sample_rate, parent=None):
        super().__init__(parent)
        self.selected_port = selected_port
        self.sample_rate = sample_rate
        self.connection_status = True
        self.data_logger = None

    def run(self):
        try:
            # self.data_logger = PotentiostatReader(
            #     com_port=self.selected_port, baud_rate=9600, timeout=0.5
            # )
            # Placeholder for actual data logging
            while self.connection_status:
                # Simulate data retrieval from sensor
                data_list = {
                    "Glutamate": random.uniform(0.5, 1.5),
                    "Glutamine": random.uniform(0.2, 0.8),
                    "Glucose": random.uniform(0.3, 1.0),
                    "Lactate": random.uniform(0.05, 0.2),
                }
                self.data_logged.emit(data_list)  # Emit the data to the main thread
                self.msleep(self.sample_rate * 1000)  # Non-blocking sleep
        except Exception as e:
            print(f"Error during data logging: {str(e)}")

    def stop(self):
        """Stop data logging."""
        self.connection_status = False
        if self.data_logger:
            self.data_logger.close_serial_connection()


class MockDataGenerator(QThread):
    """Generates mock real-time data for metabolites."""

    data_generated = pyqtSignal(dict)  # Signal to emit generated data

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True

    def run(self):
        while self.running:
            # Generate mock data for each metabolite
            data = {
                "Glutamate": random.uniform(0.5, 1.5),
                "Glutamine": random.uniform(0.2, 0.8),
                "Glucose": random.uniform(0.3, 1.0),
                "Lactate": random.uniform(0.05, 0.2),
            }
            self.data_generated.emit(data)  # Emit the generated data
            time.sleep(1)  # Simulate 1-second intervals

    def stop(self):
        """Stop the mock data generator."""
        self.running = False


# Start the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AMUZAGUI()
    window.show()
    sys.exit(app.exec_())
