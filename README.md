# Sampling Collector

A PyQt5-based application for controlling AMUZA sampling systems and real-time sensor data collection, designed for bioengineering research applications.

## Features

- **AMUZA System Control**: Connect and control AMUZA sampling systems
- **Real-time Data Visualization**: Live plotting of sensor readings with metabolite analysis
- **Well Plate Interface**: Interactive 8x12 well plate selection with drag-and-drop functionality
- **Sensor Calibration**: Built-in calibration system for metabolite sensors
- **Data Logging**: Automatic data logging with customizable file formats
- **Multi-channel Analysis**: Support for glutamate, glutamine, glucose, and lactate detection

## Requirements

- Python 3.8+
- PyQt5 for GUI interface
- Serial connection for sensor communication
- AMUZA hardware system

## Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd sampling_collector_code

# Install dependencies
uv sync

# Install with development dependencies
uv sync --dev
```

### Using pip

```bash
pip install -r requirements.txt
```

## Usage

### Starting the Application

```bash
# Using uv
uv run python Sampling_Collector.py

# Using python directly  
python Sampling_Collector.py
```

### Basic Workflow

1. **Connect to AMUZA**: Click "Connect to AMUZA" to establish system connection
2. **Sensor Setup**: Use "Start DataLogger" to open the sensor plotting window
3. **Well Selection**: 
   - Click and drag to select well ranges for RUNPLATE operations
   - Ctrl+Click individual wells for MOVE operations
4. **Sampling Operations**:
   - Use EJECT/INSERT to control tray positioning
   - RUNPLATE: Sequential sampling of selected well range
   - MOVE: Individual well sampling in specified order
5. **Data Analysis**: Real-time plotting with calibration and gain adjustment

### Sensor Window Features

- **Real-time Plotting**: Live visualization of metabolite concentrations
- **Calibration**: Set expected concentrations and calibrate sensors
- **Data Export**: Save collected data in various formats
- **Gain Adjustment**: Fine-tune metabolite detection sensitivity

## Configuration

### Settings

Access via the Settings button to adjust:
- `t_sampling`: Sampling duration per well (default: 90s)
- `t_buffer`: Buffer time between samples (default: 60s)

### Calibration

1. Open Calibration Settings from the sensor window
2. Set expected concentrations for each metabolite
3. Run calibration fluid through the system
4. Click "Calibrate" when readings stabilize

## File Structure

```
sampling_collector_code/
├── Sampling_Collector.py      # Main application
├── SIX_SERVER_READER.py      # Sensor communication module
├── AMUZA_Master.py           # AMUZA system control
├── pyproject.toml            # Project configuration
├── requirements.txt          # Pip dependencies
└── Sensor_Readings/          # Auto-generated data folder
```

## Data Output

- **Automatic Logging**: Data automatically saved to `Sensor_Readings/` folder
- **Manual Export**: Save specific datasets via File > Save As
- **Format**: Tab-separated values with timestamp and channel data
- **Channels**: 7 channels (#1ch1 through #1ch7) plus time and counter

## Development

### Development Setup

```bash
# Install with dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Format code
uv run black .

# Lint code
uv run flake8 .
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Hardware Requirements

- AMUZA sampling system
- Compatible sensor array
- Serial communication interface
- Windows/Linux/macOS with Python support

## Troubleshooting

### Common Issues

1. **Connection Failed**: Check COM port availability and permissions
2. **No Data Plotting**: Verify sensor connection and file permissions
3. **Well Selection Issues**: Ensure proper mouse interaction in well plate area
4. **Calibration Problems**: Confirm stable sensor readings before calibration

### Support

For technical support or questions, contact:
- **Author**: Noah Bernten
- **Email**: Noah.Bernten@mail.huji.ac.il
- **Institution**: Hebrew University Bioengineering

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

Developed for bioengineering research applications at Hebrew University. 