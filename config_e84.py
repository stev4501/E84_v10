"""
e84_config.py - Configuration file for E84 controller system

This file defines all configuration parameters for the E84 controller,
including operating mode, interface selection, and connection details.
"""

# -----------------------------------------------------------------------------
# OPERATING MODE SELECTION
# -----------------------------------------------------------------------------
# Specify which operating mode to use
# Options:
#   "prod" - Production mode: Full hardware operation (default)
#   "em" - Emulation mode: E84 signals use real hardware, LPT signals are simulated
#   "sim" - : All signals are simulated (no hardware)
OPERATING_MODE = 'prod'

# -----------------------------------------------------------------------------
# INTERFACE SELECTION
# -----------------------------------------------------------------------------
# Specify which interface to use for load port communication
# Options: "parallel" or "ascii"
LOAD_PORT_INTERFACE = 'parallel'  # Change to "ascii" for serial communication

# -----------------------------------------------------------------------------
# DIO HARDWARE CONFIGURATION
# -----------------------------------------------------------------------------
# Device names for DIO cards
DIO_E84_DEVICE = 'DIO000'  # E84 signals (always required in production/emulation)
DIO_LPT_DEVICE = 'DIO001'  # LPT signals (only used in parallel mode with production)

# I2C configuration
I2C_BUS = 1  # Typically 1 on Raspberry Pi
I2C_ADDRESS = 0x20  # TCA9535 address

# -----------------------------------------------------------------------------
# Pin mappings for E84 signals
# -----------------------------------------------------------------------------

# Port-0 (inputs)
# Port-0 (inputs)
E84_INPUT_PINS_BOARD = {
    'VALID': 1,  # DI0.7
    'CS_0': 2,  # DI0.6
    'CS_1': 3,  # DI0.5
    'TR_REQ': 4,  # DI0.4
    'BUSY': 5,  # DI0.3
    'COMPT': 6,  # DI0.2
}

# Port-1 (outputs)
E84_OUTPUT_PINS_BOARD = {
    'L_REQ': 1,  # DO1.7
    'U_REQ': 2,  # DO1.6
    'READY': 3,  # DO1.5
    'HO_AVBL': 4,  # DO1.4
    'ES': 5,  # DO1.3
}


# Convert once at import time
from utils import pinmap_board_to_bits  # noqa: E402

E84_INPUT_PINS = pinmap_board_to_bits(E84_INPUT_PINS_BOARD)
E84_OUTPUT_PINS = pinmap_board_to_bits(E84_OUTPUT_PINS_BOARD)


# Combined mappings (for backwards compatibility)
E84_PIN_MAPPINGS = {**E84_OUTPUT_PINS, **E84_INPUT_PINS}

# Pin mappings for LPT signals (only used in parallel mode)
LPT_PIN_MAPPINGS = {
    # Load Port 0 Signals
    'CARRIER_PRESENT_0': 0,
    'LATCH_LOCKED_0': 1,
    'LPT_ERROR_0': 2,
    'LPT_READY_0': 3,
    # Load Port 1 Signals
    'CARRIER_PRESENT_1': 4,
    'LATCH_LOCKED_1': 5,
    'LPT_ERROR_1': 6,
    'LPT_READY_1': 7,
}

# -----------------------------------------------------------------------------
# ASCII SERIAL INTERFACE CONFIGURATION
# -----------------------------------------------------------------------------
# ASCII serial interface configuration (only used in ASCII mode)
ASCII_CONFIG = {
    'serial_port': '/dev/ttyS0',  # Serial port device path
    'baudrate': 9600,  # 9600 baud as per LPT2200 manual
    'bytesize': 8,  # 8 data bits
    'parity': 'N',  # No parity
    'stopbits': 1,  # 1 stop bit
    'timeout': 1.0,  # Read timeout in seconds
    'write_timeout': 1.0,  # Write timeout in seconds
    'command_retries': 3,  # Number of retries for failed commands
}

# -----------------------------------------------------------------------------
# SIMULATION CONFIGURATION
# -----------------------------------------------------------------------------
# Simulation settings (used in simulation and emulation modes)
SIMULATION_CONFIG = {
    'auto_respond': False,  # Auto-respond to commands
    'random_errors': False,  # Randomly introduce errors
    'error_rate': 0.05,  # Error rate (0-1) if random_errors is True
    'response_delay': 0.1,  # Simulated response delay in seconds
    # Default initial states for simulated signals
    'initial_states': {
        'CARRIER_PRESENT_0': False,
        'LATCH_LOCKED_0': False,
        'LPT_ERROR_0': False,
        'LPT_READY_0': True,
        'CARRIER_PRESENT_1': False,
        'LATCH_LOCKED_1': False,
        'LPT_ERROR_1': False,
        'LPT_READY_1': True,
    },
}

# -----------------------------------------------------------------------------
# GLOBAL SYSTEM CONFIGURATION
# -----------------------------------------------------------------------------
# Polling interval for hardware monitoring (seconds)
POLLING_INTERVAL = 0.1

# GUI Configuration
SHOW_MESSAGE_LOG = 'False'  # Options: "yes", "y", "no", "n" - Controls whether to show message log in GUI


# Logging settings
LOG_LEVEL = 'DEBUG'  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = 'e84_controller.log'  # Log file path
LOG_ROTATION = '10 MB'  # Rotate logs when they reach this size
LOG_RETENTION = '1 week'  # How long to keep old logs

# Timeout values for state machine (seconds)
TIMEOUTS = {
    'TP1': 2.0,  # TR_REQ signal timeout
    'TP2': 2.0,  # BUSY signal timeout
    'TP3': 60.0,  # Carrier detection timeout
    'TP4': 60.0,  # BUSY signal OFF timeout
    'TP5': 2.0,  # VALID signal OFF timeout
}


# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def get_config():
    """
    Get the complete configuration as a dictionary.
    """
    return {
        'operating_mode': OPERATING_MODE,
        'load_port_interface': LOAD_PORT_INTERFACE,
        'dio_config': {
            'e84_device_name': DIO_E84_DEVICE,
            'lpt_device_name': DIO_LPT_DEVICE,
            'e84_pin_mappings': E84_PIN_MAPPINGS,
            'lpt_pin_mappings': LPT_PIN_MAPPINGS,
            'i2c_bus': I2C_BUS,
            'i2c_address': I2C_ADDRESS,
        },
        'ascii_config': ASCII_CONFIG,
        'simulation_config': SIMULATION_CONFIG,
        'logging': {
            'level': LOG_LEVEL,
            'file': LOG_FILE,
            'rotation': LOG_ROTATION,
            'retention': LOG_RETENTION,
            'show_message_log': SHOW_MESSAGE_LOG,
        },
        'timeouts': TIMEOUTS,
        'polling_interval': POLLING_INTERVAL,
    }


print(f'{get_config()}')


def is_ascii_mode():
    """Helper to check if we're in ASCII mode"""
    return LOAD_PORT_INTERFACE.lower() == 'ascii'


def is_parallel_mode():
    """Helper to check if we're in parallel mode"""
    return LOAD_PORT_INTERFACE.lower() == 'parallel'


def is_production_mode():
    """Helper to check if we're in production mode"""
    return OPERATING_MODE.lower() == 'production'


def is_emulation_mode():
    """Helper to check if we're in emulation mode"""
    return OPERATING_MODE.lower() == 'emulation'


def is_simulation_mode():
    """Helper to check if we're in simulation mode"""
    return OPERATING_MODE.lower() == 'simulation'


# When run directly, print the current configuration
if __name__ == '__main__':
    import json
    import sys

    # Print config in a readable format
    print('E84 Controller Configuration:')
    print('-' * 80)
    print(f'Operating Mode: {OPERATING_MODE}')
    print(f'Interface Type: {LOAD_PORT_INTERFACE}')

    if is_ascii_mode():
        print(f'ASCII Serial Port: {ASCII_CONFIG["serial_port"]}')
        print(f'ASCII Baudrate: {ASCII_CONFIG["baudrate"]}')

    print(f'E84 DIO Device: {DIO_E84_DEVICE}')

    if is_parallel_mode() and is_production_mode():
        print(f'LPT DIO Device: {DIO_LPT_DEVICE}')

    if is_simulation_mode():
        print('All signals will be simulated (no hardware used)')
    elif is_emulation_mode():
        print('E84 signals use real hardware, LPT signals are simulated')

    print(f'Log Level: {LOG_LEVEL}')
    print('-' * 80)

    # If an argument is provided, export to JSON format
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
        with open(output_file, 'w') as f:
            json.dump(get_config(), f, indent=4)
        print(f'Configuration exported to {output_file}')
