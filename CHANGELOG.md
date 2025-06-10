# Changelog

All notable changes to the Sampling Collector project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-XX

### Added
- Initial release of Sampling Collector application
- PyQt5-based GUI for AMUZA system control
- Real-time sensor data plotting and visualization
- Interactive 8x12 well plate selection interface
- Drag-and-drop well selection for RUNPLATE operations
- Ctrl+Click well selection for MOVE operations
- Automatic data logging to timestamped files
- Sensor calibration system for metabolite detection
- Support for glutamate, glutamine, glucose, and lactate analysis
- Configurable sampling and buffer times
- Mock data mode for testing without hardware
- File export functionality for collected data
- Connection management for serial communication
- Temperature adjustment capabilities
- EJECT/INSERT tray control functions

### Features
- Multi-channel sensor data processing
- Real-time gain adjustment
- Calibration settings dialog
- Navigation toolbar for plot interaction
- Automatic sensor readings folder creation
- Process stop functionality
- Connection status indicators
- Instruction panels for user guidance

### Technical
- Python 3.8+ compatibility
- PyQt5 GUI framework
- Matplotlib for data visualization
- Pandas for data manipulation
- NumPy for numerical operations
- Serial communication support
- Threading for non-blocking operations
- Signal-slot architecture for UI updates

## [Unreleased]

### Planned
- Additional metabolite support
- Enhanced data export formats
- Improved error handling
- Performance optimizations
- Extended hardware compatibility 