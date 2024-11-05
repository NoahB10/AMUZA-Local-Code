import sys
import threading
import time
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QPushButton, QMessageBox, QDialog, QFormLayout, QSpinBox, QMainWindow, QLineEdit, QToolBar, QFileDialog, QMenuBar, QAction, QDockWidget
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QMouseEvent
from SIX_SERVER_READER import PotentiostatReader
import AMUZA_Master

# Global variables
t_buffer = 65
t_sampling = 91
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
    """Window for displaying the matplotlib plot embedded in a PyQt5 window with gain inputs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Plot")
        self.setGeometry(200, 200, 1000, 800)

        # Initial gain values
        self.gain_values = {
            "Glutamate": 0.97,
            "Glutamine": 0.418,
            "Glucose": 0.6854,
            "Lactate": 0.0609
        }

        # Set up the matplotlib figure and canvas
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)

        # Set up the navigation toolbar directly under the canvas
        self.nav_toolbar = NavigationToolbar(self.canvas, self)

        # Set up the File menu with Load and Save actions
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        
        load_action = QAction("Load New", self)
        load_action.triggered.connect(self.load_file)
        file_menu.addAction(load_action)
        
        save_action = QAction("Save As", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        # Add Start Record and Pause as toggle actions
        self.start_record_action = QAction("Start Record", self, checkable=True)
        self.start_record_action.triggered.connect(self.toggle_record)
        
        self.pause_action = QAction("Pause", self, checkable=True)
        self.pause_action.triggered.connect(self.toggle_pause)

        # Set default text for actions
        self.update_action_text()

        # Add Start Record and Pause actions directly to the menu bar
        menu_bar.addAction(self.start_record_action)
        menu_bar.addAction(self.pause_action)

        # Graph area layout
        graph_layout = QVBoxLayout()
        graph_layout.addWidget(self.canvas)
        graph_layout.addWidget(self.nav_toolbar)  # Navigation toolbar directly under the canvas

        # Gain inputs layout at the bottom
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

        # Add gain inputs to the bottom of graph_layout
        graph_layout.addLayout(gain_layout)
        
        # Set up the central widget with the main layout
        central_widget = QWidget()
        central_widget.setLayout(graph_layout)
        self.setCentralWidget(central_widget)

        # Initial plot
        self.plot_data()

    def update_action_text(self):
        """Update text for Start Record and Pause actions based on toggle state."""
        if self.start_record_action.isChecked():
            self.start_record_action.setText("Stop Recording")
        else:
            self.start_record_action.setText("Start Record")
        
        if self.pause_action.isChecked():
            self.pause_action.setText("Resume")
        else:
            self.pause_action.setText("Pause")

    def update_gain_values(self):
        """Update gain values based on user input and re-plot the data."""
        for metabolite, input_field in self.gain_inputs.items():
            try:
                new_value = float(input_field.text())
                self.gain_values[metabolite] = new_value
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", f"Please enter a valid number for {metabolite} gain.")
                return
        self.plot_data()  # Re-plot with updated gain values

    def toggle_record(self):
        """Toggle the recording state and update action text."""
        # Logic to start or stop recording can be added here
        self.update_action_text()

    def toggle_pause(self):
        """Toggle the pause state and update action text."""
        # Logic to pause or resume can be added here
        self.update_action_text()

    def plot_data(self, file_path=None):
        """Process data and display the plot on the embedded canvas."""
        if file_path is None:
            # Default path if no file is specified
            path = "C:\\Users\\NoahB\\Documents\\HebrewU Bioengineering\\Equipment\\JOBST\\"
            filename = "Medium_Calibration_Test.txt"
            file_path = path + filename

        # Load and process data
        with open(file_path, "r", newline="") as file:
            lines = file.readlines()
        
        data = [line.strip().split("\t") for line in lines]
        df = pd.DataFrame(data)
        df = df.loc[:, :8]  # Select relevant columns for one sensor
        new_header = df.iloc[1]  # Select the third row as header
        df = df[3:]  # Take the data less the new header row
        df.columns = new_header  # Set the new header

        index = []
        for i in range(3, len(df) + 2):
            a = df.loc[i, "counter"]
            if not a.isdigit():
                index.append(i)
                break  # Stop once the first non-digit is found

        df2 = df.loc[0 : index[0] - 1, :]
        df2 = df2.apply(pd.to_numeric)

        # Subtract signals from blanks according to the rules
        glutamate = df2["#1ch1"] - df2["#1ch2"]
        glutamine = df2["#1ch3"] - df2["#1ch1"]
        glucose = df2["#1ch5"] - df2["#1ch4"]
        lactate = df2["#1ch6"] - df2["#1ch4"]

        # Apply gain values to results
        results = pd.DataFrame({
            "Glutamate": glutamate * self.gain_values["Glutamate"],
            "Glutamine": glutamine * self.gain_values["Glutamine"],
            "Glucose": glucose * self.gain_values["Glucose"],
            "Lactate": lactate * self.gain_values["Lactate"],
        })

        # Plot the data on the embedded canvas
        self.figure.clear()
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

        # Update the canvas to show the plot
        self.canvas.draw()

    def load_file(self):
        """Open a file dialog to select a file and load it into the plot."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            self.plot_data(file_path)  # Load the selected file and update the plot

    def save_file(self):
        """Open a file dialog to save the current plot data."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            # Implement saving logic here if necessary, such as saving processed data or the plot
            with open(file_path, "w") as file:
                file.write("Placeholder for saved data or plot")  # Example content


class SettingsDialog(QDialog):
    """Settings window to adjust t_sampling and t_buffer."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Settings")

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
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def accept(self):
        """Update t_sampling and t_buffer when OK is pressed."""
        global t_sampling, t_buffer
        t_sampling = self.sampling_time_spinbox.value()
        t_buffer = self.buffer_time_spinbox.value()
        super().accept()

class AMUZAGUI(QWidget):
    def __init__(self):
        super().__init__()

        # Set up the window
        self.setWindowTitle("AMUZA Controller")
        self.setGeometry(100, 100, 900, 400)

        # Main layout - Horizontal
        self.main_layout = QHBoxLayout(self)

        # Left side layout for commands
        self.command_layout = QVBoxLayout()

        # Placeholder for filename area to keep button alignment
        self.filename_placeholder = QLabel("", self)
        self.filename_placeholder.setFixedHeight(220)
        self.command_layout.addWidget(self.filename_placeholder)

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

    def on_runplate(self):
        """Print the selected wells for RUNPLATE to the console."""
        if selected_wells:
            print("Selected wells for RUNPLATE:", list(selected_wells))
        else:
            print("No wells selected for RUNPLATE.")

    def on_move(self):
        """Print the selected wells for MOVE to the console."""
        if ctrl_selected_wells:
            print("Selected wells for MOVE:", list(ctrl_selected_wells))
        else:
            print("No wells selected for MOVE.")

    def open_settings_dialog(self):
        """Open the settings dialog to adjust t_sampling and t_buffer."""
        dialog = SettingsDialog()
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
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect to AMUZA: {str(e)}")
            connection = None

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
        self.run_command("INSERT")

    def on_eject(self):
        self.run_command("EJECT")

    def run_command(self, command, use_ctrl_selection=False):
        """Execute the given command with the AMUZA system."""
        global connection
        method = []
        if connection is None:
            QMessageBox.critical(self, "Error", "Please connect to AMUZA first!")
            return

        if command == "RUNPLATE":
            connection.AdjustTemp(6)
            if not selected_wells:
                QMessageBox.critical(self, "Error", "No wells selected. Please select wells from the layout.")
                return
            locations = list(selected_wells)
            locations = connection.well_mapping(locations)
            for loc in locations:
                method.append(AMUZA_Master.Sequence([AMUZA_Master.Method([loc], t_sampling)]))
            self.Control_Move(method, [t_sampling])

        elif command == "MOVE":
            connection.AdjustTemp(6)
            wells_to_move = ctrl_selected_wells if use_ctrl_selection else selected_wells
            if not wells_to_move:
                QMessageBox.critical(self, "Error", "No wells selected for MOVE. Please Ctrl+Click wells to select.")
                return
            locations = list(wells_to_move)
            locations = connection.well_mapping(locations)
            for i in range(len(locations)):
                loc = locations[i]
                method.append(AMUZA_Master.Sequence([AMUZA_Master.Method([loc], t_sampling)]))
            self.Control_Move(method, [t_sampling])

        elif command == "EJECT":
            connection.Eject()

        elif command == "INSERT":
            connection.Insert()

    def Control_Move(self, method, duration):
        """Simulate movement of the AMUZA system."""
        for i in range(0, len(method)):
            time.sleep(t_buffer)
            connection.Move(method[i])
            delay = 1
            time.sleep(duration[0] + 9 + delay)

    def resizeEvent(self, event):
        """Lock the aspect ratio of the window."""
        width = event.size().width()
        height = event.size().height()

        aspect_ratio = 9 / 4
        new_height = int(width / aspect_ratio)

        # Resize the window to maintain the aspect ratio
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