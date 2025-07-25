# E84 Controller System

A Python-based implementation of the SEMI E84 standard for AMHS (Automated Material Handling System) interfaces in semiconductor manufacturing equipment. This system provides a robust controller for managing equipment load ports with flexible communication options.

## Features

- **Dual Interface Support**: Choose between parallel port or ASCII serial communication
- **Flexible Configuration**: Configure via JSON files or command-line arguments
- **E84 Compliant**: Full implementation of E84 state machine and handshake protocols
- **Robust Error Handling**: Comprehensive error recovery mechanisms
- **GUI Interface**: Real-time visualization of signals and system state
- **Modular Design**: Easily extensible architecture

## System Requirements

- Python 3.6+
- CONTEC Digital I/O cards (CPI-DIO-0808L) for parallel interface
- RS-232 serial port for ASCII interface
- PySerial package (for ASCII interface)
- CustomTkinter package (for GUI)

## Installation

1. Clone the repository:
```bash
git clone https://bitbucket.itg.ti.com/projects/DM5-DISP/repos/secs/browse/e84_controller/v10
cd e84-controller 
```
2. Install the required dependencies: `pip install -r requirements.txt `
3. Generate a default configuration file: `python load_port_factory.py `

## Configuration
The system can be configured using a JSON configuration file or command-line arguments.

### Configuration File (e84\_config.json)
```json
{
    "load_port_interface": "parallel",  // or "ascii"
    "ascii_config": {
        "serial_port": "/dev/ttyS0",
        "baudrate": 9600
    },
    "parallel_config": {
        // Any parallel port specific settings
    }
} 
```
### Command-Line Arguments
```
Usage: python main.py [OPTIONS]

Options:
  --config FILE       Path to configuration file
  --interface TYPE    Load port interface type (parallel or ascii)
  --serial-port PORT  Serial port for ASCII interface
  --log-level LEVEL   Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) 
```
## Usage
### Basic Usage (Parallel Interface)
This will use the parallel port interface with two DIO cards:

```bash
python main.py 
```
### Using ASCII Interface
For systems where the parallel port is reserved for safety interlocks:

```bash
python main.py --interface ascii --serial-port /dev/ttyS0 
```
### Specifying a Custom Configuration
```bash
python main.py --config custom_config.json 
```
## Architecture
The system consists of several key components:

* **E84Controller**: Main controller that manages the E84 state machine
* **LoadPortFactory**: Creates appropriate LoadPort instances based on configuration
* **DioHardwareInterface**: Handles communication with the DIO cards
* **LoadPort/LoadPortAscii**: Interfaces with the physical load ports
* **SignalManager**: Manages signal states and callbacks
* **E84StateMachine**: Implements the E84 state machine logic
* **ProductionGUI**: Provides visual interface for monitoring and control

### Interface Selection
The system adapts to different hardware configurations:

* **Parallel Interface**: Uses two DIO cards:
   * DIO000: E84 signals (handshake with AMHS)
   * DIO001: Load port signals

* **ASCII Interface**: Uses one DIO card + serial communication:
   * DIO000: E84 signals
   * Serial port: Communication with load ports


## Troubleshooting
### Common Issues
* **"Failed to initialize DIO device"**: Ensure the DIO cards are properly installed and have the correct device names.
* **"Serial port not available"**: Check that the specified serial port exists and has the correct permissions.
* **"Incorrect handshake sequence"**: Verify signal wiring and timing settings.

### Logging
Set the log level for more detailed information:

```bash
python main.py --log-level DEBUG 
```
Log files are automatically rotated and are located at `e84_controller.log`.

## Development
### Adding a New Feature
1. Identify the appropriate module for your feature
2. Implement changes maintaining API compatibility
3. Update tests and documentation
4. Submit a pull request

### Running Tests
```bash
python -m unittest discover tests 
```
