"""
hardware_interface.py - Unified hardware interface for E84 controller

This module provides hardware interface implementations for all operating modes:
- Production: Real hardware for both E84 and LPT signals
- Emulation: Real hardware for E84 signals, simulated LPT signals
- Simulation: Simulated hardware for all signals
"""

import random
import threading
import time
from typing import Dict

from loguru import logger

from callback_manager import CallbackManager
from config_e84 import is_ascii_mode
from signal_manager import SignalManager

# Define a cdio global variable as None
# DO NOT import cdio at module level - only import it when explicitly needed
cdio = None


# Only define the real hardware classes if we can import cdio
def _try_import_cdio():
    """Try to import cdio and return success state"""
    global cdio
    try:
        import ctypes  # noqa: F401

        import cdio as cdio_module

        cdio = cdio_module
        return True
    except (ImportError, ModuleNotFoundError, FileNotFoundError) as e:
        logger.warning(f'Could not import cdio module: {e}')
        return False


class HardwareInterfaceBase:
    """
    Abstract base class for hardware interfaces.
    Defines common interface and shared functionality.
    """

    def __init__(
        self,
        signal_manager: SignalManager,
        callback_manager: CallbackManager,
        polling_interval: float = 0.1,
        **kwargs,
    ):
        """
        Initialize base hardware interface.

        Args:
            signal_manager: Signal manager instance
            callback_manager: Callback manager instance
            polling_interval: Interval for polling hardware
            **kwargs: Additional parameters
        """
        self.signal_manager = signal_manager
        self.callback_manager = callback_manager
        self.polling_interval = polling_interval

        # Threading and status flags
        self.input_running = False
        self.polling_thread = None

    def initialize(self):
        """Initialize the hardware interface (to be implemented by derived classes)"""
        raise NotImplementedError('Derived classes must implement this method')

    def start_input_monitoring(self):
        """Start input monitoring (to be implemented by derived classes)"""
        raise NotImplementedError('Derived classes must implement this method')

    def stop_input_monitoring(self):
        """Stop input monitoring (to be implemented by derived classes)"""
        raise NotImplementedError('Derived classes must implement this method')

    def set_output_pin(self, signal: str, value: bool):
        """Set an output pin (to be implemented by derived classes)"""
        raise NotImplementedError('Derived classes must implement this method')

    def read_input_pin(self, signal: str) -> bool:
        """Read an input pin (to be implemented by derived classes)"""
        raise NotImplementedError('Derived classes must implement this method')

    def close(self):
        """Close hardware resources (to be implemented by derived classes)"""
        raise NotImplementedError('Derived classes must implement this method')


class SimulatedDioHardwareInterface(HardwareInterfaceBase):
    """
    Simulated hardware interface for testing.

    This class provides a complete simulation of the hardware interface
    for use in simulation mode, where no real hardware is available.
    """

    def __init__(
        self,
        signal_manager: SignalManager,
        callback_manager: CallbackManager,
        simulation_config: Dict = None,
        polling_interval: float = 0.1,
        **kwargs,
    ):
        """
        Initialize the simulated hardware interface.

        Args:
            signal_manager: The signal manager instance
            callback_manager: The callback manager instance
            simulation_config: Configuration for the simulation
            polling_interval: Interval for polling simulated hardware inputs
            **kwargs: Additional parameters (ignored)
        """
        super().__init__(signal_manager, callback_manager, polling_interval, **kwargs)
        self.simulation_config = simulation_config or {}

        # Get simulation parameters
        self.auto_respond = self.simulation_config.get('auto_respond', True)
        self.random_errors = self.simulation_config.get('random_errors', False)
        self.error_rate = self.simulation_config.get('error_rate', 0.05)
        self.response_delay = self.simulation_config.get('response_delay', 0.1)

        # Initialize simulated signal states
        initial_states = self.simulation_config.get('initial_states', {})
        self.simulated_signals: dict[str, bool] = {
            # E84 signals
            'CS_0': False,
            'CS_1': False,
            'VALID': False,
            'TR_REQ': False,
            'BUSY': False,
            'COMPT': False,
            'L_REQ': False,
            'U_REQ': False,
            'READY': False,
            'HO_AVBL': True,
            'ES': True,
            # LPT signals
            'CARRIER_PRESENT_0': False,
            'LATCH_LOCKED_0': False,
            'LPT_ERROR_0': False,
            'LPT_READY_0': True,
            'CARRIER_PRESENT_1': False,
            'LATCH_LOCKED_1': False,
            'LPT_ERROR_1': False,
            'LPT_READY_1': True,
        }

        # Override with any provided initial states
        for signal, value in initial_states.items():
            if signal in self.simulated_signals:
                self.simulated_signals[signal] = value

        logger.info('Simulated DIO hardware interface initialized')

    def initialize(self):
        """Initialize the simulated hardware."""
        logger.info('Initializing simulated hardware')

        # Update signal manager with initial signal states
        for signal, value in self.simulated_signals.items():
            self.signal_manager.set_signal(signal, value)

        logger.info('Simulated hardware initialized')

    def start_input_monitoring(self):
        """Start monitoring simulated inputs."""
        if self.input_running:
            logger.warning('Simulated input monitoring is already running')
            return

        self.input_running = True
        self.polling_thread = threading.Thread(
            target=self._input_polling_loop, daemon=True
        )
        self.polling_thread.start()
        logger.info('Started simulated DIO input monitoring')

    def stop_input_monitoring(self):
        """Stop monitoring simulated inputs."""
        self.input_running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=1.0)
        logger.info('Stopped simulated DIO input monitoring')

    def _input_polling_loop(self):
        """Background thread that simulates hardware monitoring."""
        logger.debug('Simulated input polling thread started')

        try:
            while self.input_running:
                # Simulate random input changes if auto_respond is enabled
                if self.auto_respond:
                    self._simulate_auto_responses()

                # Sleep for the polling interval
                time.sleep(self.polling_interval)

        except Exception as e:
            logger.error(f'Exception in simulated input polling thread: {e}')
            self.input_running = False

    def _simulate_auto_responses(self):
        """
        Automatically simulate realistic responses to output signals.
        This provides a simple state machine simulation.
        """
        # Example: If L_REQ is set, eventually simulate VALID and TR_REQ
        if self.simulated_signals.get('L_REQ', False) and random.random() < 0.1:
            # Simulate AGV responding to load request
            if not self.simulated_signals.get('VALID', False):
                self._set_simulated_signal('VALID', True)
                self._set_simulated_signal('CS_0', True)  # Select port 0

            elif not self.simulated_signals.get('TR_REQ', False):
                self._set_simulated_signal('TR_REQ', True)

        # Example: If READY is set, eventually simulate BUSY
        if (
            self.simulated_signals.get('READY', False)
            and self.simulated_signals.get('TR_REQ', False)
            and not self.simulated_signals.get('BUSY', False)
            and random.random() < 0.1
        ):
            self._set_simulated_signal('BUSY', True)

        # Example: If BUSY is set, eventually simulate COMPT
        if self.simulated_signals.get('BUSY', False) and random.random() < 0.05:
            self._set_simulated_signal('COMPT', True)
            self._set_simulated_signal('BUSY', False)

        # Example: If COMPT is set and signals are turning off
        if (
            self.simulated_signals.get('COMPT', False)
            and not self.simulated_signals.get('READY', False)
            and not self.simulated_signals.get('TR_REQ', False)
            and random.random() < 0.1
        ):
            # Reset signals for next cycle
            self._set_simulated_signal('COMPT', False)
            self._set_simulated_signal('VALID', False)
            self._set_simulated_signal('CS_0', False)
            self._set_simulated_signal('CS_1', False)

        # Randomly introduce errors if enabled
        if self.random_errors and random.random() < self.error_rate:
            # Example: Randomly toggle an LPT error signal
            port = random.randint(0, 1)
            self._set_simulated_signal(
                f'LPT_ERROR_{port}',
                not self.simulated_signals.get(f'LPT_ERROR_{port}', False),
            )

    def _set_simulated_signal(self, signal: str, value: bool):
        """Update a simulated signal and the signal manager."""
        if signal in self.simulated_signals and self.simulated_signals[signal] != value:
            self.simulated_signals[signal] = value

            # Introduce artificial delay to simulate hardware response time
            if self.response_delay > 0:
                time.sleep(self.response_delay)

            # Update signal manager
            old_value = self.signal_manager.get_signal(signal)
            self.signal_manager.set_signal(signal, value)

            # Log the change
            logger.debug(
                f'Simulated signal {signal} changed from {old_value} to {value}'
            )

            # Try to trigger callbacks
            try:
                from callback_manager import SignalType

                signal_type = SignalType[signal]
                self.callback_manager.notify(signal_type, old_value, value)
            except (KeyError, AttributeError):
                logger.error(f'Signal type not defined in SignalType enum {signal}')

    def set_output_pin(self, signal: str, value: bool):
        """
        Simulate setting an output pin.

        Args:
            signal: The signal name
            value: The signal value (True/False)

        Returns:
            True if successful, False otherwise
        """
        if signal in self.simulated_signals:
            self._set_simulated_signal(signal, value)
            logger.debug(f'Simulated output {signal} set to {value}')
            return True
        else:
            logger.error(f'Unknown simulated signal: {signal}')
            return False

    def read_input_pin(self, signal: str) -> bool:
        """
        Simulate reading an input pin.

        Args:
            signal: The signal name

        Returns:
            Simulated pin state (True/False)
        """
        if signal in self.simulated_signals:
            # Introduce artificial delay to simulate hardware response time
            if self.response_delay > 0:
                time.sleep(self.response_delay * 0.5)  # Use shorter delay for reads

            return self.simulated_signals.get(signal, False)
        else:
            logger.error(f'Unknown simulated signal: {signal}')
            return False

    def close(self):
        """Close the simulated hardware interface."""
        self.stop_input_monitoring()
        logger.info('Simulated DIO hardware interface closed')


class DioHardwareInterface(HardwareInterfaceBase):
    """
    Hardware interface for CONTEC Digital I/O cards CPI-DIO-0808L

    This class provides an interface between the E84 controller software and
    the physical I/O pins on the DIO cards. It handles:

    1. Initializing the DIO hardware (one or two cards)
    2. Setting up input pin event callbacks
    3. Mapping E84 signals to physical I/O pins
    4. Reading input and setting output pins
    """

    def __init__(
        self,
        signal_manager: SignalManager,
        callback_manager: CallbackManager,
        e84_device_name: str,
        e84_pin_mappings: dict[str, int],
        lpt_device_name: str | None = None,
        lpt_pin_mappings: Dict[str, int] | None = None,
        polling_interval: float = 0.1,
        config: Dict = None,
        **kwargs,
    ):
        """
        Initialize the hardware interface with one or two DIO cards

        Args:
            signal_manager: The E84 signal manager
            callback_manager: The E84 callback manager
            e84_device_name: The name of the DIO device for E84 signals
            e84_pin_mappings: Pin mappings for E84 signals from config
            lpt_device_name: The name of the DIO device for Load Port signals (optional in ASCII mode)
            lpt_pin_mappings: Pin mappings for Load Port signals from config (optional in ASCII mode)
            polling_interval: Interval for polling hardware inputs (seconds)
            **kwargs: Additional parameters
        """
        # Check if cdio is available
        if not _try_import_cdio():
            raise ImportError(
                'Cannot initialize real hardware interface: cdio module not available'
            )

        import ctypes

        super().__init__(signal_manager, callback_manager, polling_interval, **kwargs)

        # Device information
        self.e84_device_name = e84_device_name
        self.lpt_device_name = lpt_device_name  # Can be None in ASCII mode

        # Flag to track if we're using dual cards or single card
        self.dual_card_mode = lpt_device_name is not None

        # Pin mappings from config
        self.e84_pin_mappings = e84_pin_mappings
        self.lpt_pin_mappings = lpt_pin_mappings if self.dual_card_mode else {}

        # Combined pin mappings for easier lookup (only E84 signals in ASCII mode)
        self.pin_mappings = {**self.e84_pin_mappings}
        if self.dual_card_mode:
            self.pin_mappings.update(self.lpt_pin_mappings)

        # Create device ID containers
        self.e84_dio_id = ctypes.c_short()
        self.lpt_dio_id = ctypes.c_short() if self.dual_card_mode else None

        # Error handling
        self.err_str = ctypes.create_string_buffer(256)

        # Initialize the hardware
        self._initialize_hardware()

    def _initialize_hardware(self):
        """Initialize one or two DIO hardware devices based on mode"""
        import ctypes

        logger.info(f'Initializing E84 DIO hardware: {self.e84_device_name}')
        if self.dual_card_mode:
            logger.info(f'Initializing LPT DIO hardware: {self.lpt_device_name}')
        else:
            logger.info(
                'Running in ASCII mode - LPT signals will be handled via serial interface'
            )

        # Initialize the E84 DIO device
        ret = cdio.DioInit(self.e84_device_name.encode(), ctypes.byref(self.e84_dio_id))
        if ret != cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(ret, self.err_str)
            error_msg = f'Failed to initialize E84 DIO device: {self.err_str.value.decode("utf-8")}'
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Initialize the LPT DIO device (only in dual card mode)
        if self.dual_card_mode:
            ret = cdio.DioInit(
                self.lpt_device_name.encode(), ctypes.byref(self.lpt_dio_id)
            )
            if ret != cdio.DIO_ERR_SUCCESS:
                cdio.DioGetErrorString(ret, self.err_str)
                error_msg = f'Failed to initialize LPT DIO device: {self.err_str.value.decode("utf-8")}'
                logger.error(error_msg)

                # Clean up the first device before raising the exception
                cdio.DioExit(self.e84_dio_id)
                raise RuntimeError(error_msg)

        # Get E84 device information
        e84_in_port_num = ctypes.c_short()
        e84_out_port_num = ctypes.c_short()
        ret = cdio.DioGetMaxPorts(
            self.e84_dio_id,
            ctypes.byref(e84_in_port_num),
            ctypes.byref(e84_out_port_num),
        )

        if ret != cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(ret, self.err_str)
            error_msg = f'Failed to get E84 DIO port information: {self.err_str.value.decode("utf-8")}'
            logger.error(error_msg)

            # Clean up before raising the exception
            cdio.DioExit(self.e84_dio_id)
            if self.dual_card_mode and self.lpt_dio_id is not None:
                cdio.DioExit(self.lpt_dio_id)
            raise RuntimeError(error_msg)

        self.e84_max_input_bits = e84_in_port_num.value * 8
        self.e84_max_output_bits = e84_out_port_num.value * 8

        # Get LPT device information (only in dual card mode)
        if self.dual_card_mode:
            lpt_in_port_num = ctypes.c_short()
            lpt_out_port_num = ctypes.c_short()
            ret = cdio.DioGetMaxPorts(
                self.lpt_dio_id,
                ctypes.byref(lpt_in_port_num),
                ctypes.byref(lpt_out_port_num),
            )

            if ret != cdio.DIO_ERR_SUCCESS:
                cdio.DioGetErrorString(ret, self.err_str)
                error_msg = f'Failed to get LPT DIO port information: {self.err_str.value.decode("utf-8")}'
                logger.error(error_msg)

                # Clean up before raising the exception
                cdio.DioExit(self.e84_dio_id)
                cdio.DioExit(self.lpt_dio_id)
                raise RuntimeError(error_msg)

            self.lpt_max_input_bits = lpt_in_port_num.value * 8
            self.lpt_max_output_bits = lpt_out_port_num.value * 8

            logger.info(
                f'E84 DIO device has {self.e84_max_input_bits} input bits and {self.e84_max_output_bits} output bits'
            )
            logger.info(
                f'LPT DIO device has {self.lpt_max_input_bits} input bits and {self.lpt_max_output_bits} output bits'
            )
        else:
            # In ASCII mode, only log E84 DIO info
            logger.info(
                f'E84 DIO device has {self.e84_max_input_bits} input bits and {self.e84_max_output_bits} output bits'
            )

        # Initialize all outputs to their default states
        self._initialize_outputs()

    def _initialize_outputs(self):
        """Initialize all output pins to their default states"""
        # Default outputs based on E84 specification
        default_outputs = {
            'L_REQ': False,
            'U_REQ': False,
            'READY': False,
            'HO_AVBL': True,  # Default to True per E84 spec
            'ES': True,  # Default to True (not in E-Stop)
        }

        # Set initial output pin states
        for signal, default_value in default_outputs.items():
            if signal in self.e84_pin_mappings:
                self.set_output_pin(signal, default_value)

    def initialize(self):
        """Initialize the hardware interface - hardware already initialized in __init__"""
        # All initialization work is already done in _initialize_hardware called from __init__
        logger.info('DIO hardware interface already initialized')

    def start_input_monitoring(self):
        """
        Start monitoring input pins on DIO card(s)

        This will start a background thread that continuously reads the state of the
        input pins and updates the E84 signal manager accordingly.
        """
        if self.input_running:
            logger.warning('Input monitoring is already running')
            return

        self.input_running = True
        self.polling_thread = threading.Thread(
            target=self._input_polling_loop, daemon=True
        )
        self.polling_thread.start()
        logger.info('Started DIO input monitoring')

    def stop_input_monitoring(self):
        """Stop monitoring input pins"""
        self.input_running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=1.0)
        logger.info('Stopped DIO input monitoring')

    def _input_polling_loop(self):
        """Background thread that polls input pins and updates signals"""
        logger.debug('Input polling thread started')
        import ctypes

        # Get all E84 input signal names for polling
        e84_input_signals = ['CS_0', 'CS_1', 'VALID', 'TR_REQ', 'BUSY', 'COMPT']

        # Get all LPT input signal names for polling (only in dual card mode)
        lpt_input_signals = []
        if self.dual_card_mode:
            lpt_input_signals = [
                'CARRIER_PRESENT_0',
                'LATCH_LOCKED_0',
                'LPT_ERROR_0',
                'LPT_READY_0',
                'CARRIER_PRESENT_1',
                'LATCH_LOCKED_1',
                'LPT_ERROR_1',
                'LPT_READY_1',
            ]

        # Create a buffer for reading
        io_data = ctypes.c_ubyte()

        # Track previous states to detect changes
        previous_states = {
            signal: None for signal in e84_input_signals + lpt_input_signals
        }

        try:
            while self.input_running:
                # Poll E84 input signals
                for signal in e84_input_signals:
                    if signal in self.e84_pin_mappings:
                        bit_no = self.e84_pin_mappings[signal]

                        # Read the input bit from E84 card
                        ret = cdio.DioInpBit(
                            self.e84_dio_id,
                            ctypes.c_short(bit_no),
                            ctypes.byref(io_data),
                        )
                        if ret != cdio.DIO_ERR_SUCCESS:
                            logger.error(
                                f'Failed to read E84 input bit {bit_no} ({signal})'
                            )
                            continue

                        # Convert to boolean
                        new_value = bool(io_data.value)

                        # If state changed, update the signal manager
                        if previous_states[signal] != new_value:
                            logger.debug(
                                f'E84 input signal {signal} changed from {previous_states[signal]} to {new_value}'
                            )

                            # Update signal manager
                            old_value = self.signal_manager.get_signal(signal)
                            self.signal_manager.set_signal(signal, new_value)

                            # Try to trigger the corresponding callback
                            try:
                                from callback_manager import SignalType

                                signal_type = SignalType[signal]
                                self.callback_manager.notify(
                                    signal_type, new_value, old_value
                                )
                            except (KeyError, AttributeError):
                                pass  # Signal type not defined in SignalType enum

                            previous_states[signal] = new_value

                # Poll LPT input signals (only in dual card mode)
                if self.dual_card_mode:
                    for signal in lpt_input_signals:
                        if signal in self.lpt_pin_mappings:
                            bit_no = self.lpt_pin_mappings[signal]

                            # Read the input bit from LPT card
                            ret = cdio.DioInpBit(
                                self.lpt_dio_id,
                                ctypes.c_short(bit_no),
                                ctypes.byref(io_data),
                            )
                            if ret != cdio.DIO_ERR_SUCCESS:
                                logger.error(
                                    f'Failed to read LPT input bit {bit_no} ({signal})'
                                )
                                continue

                            # Convert to boolean
                            new_value = bool(io_data.value)

                            # If state changed, update the signal manager
                            if previous_states[signal] != new_value:
                                logger.debug(
                                    f'LPT input signal {signal} changed from {previous_states[signal]} to {new_value}'
                                )

                                # Update signal manager
                                old_value = self.signal_manager.get_signal(signal)
                                self.signal_manager.set_signal(signal, new_value)

                                # Try to trigger the corresponding callback
                                try:
                                    from callback_manager import SignalType

                                    signal_type = SignalType[signal]
                                    self.callback_manager.notify(
                                        signal_type, new_value, old_value
                                    )
                                except (KeyError, AttributeError):
                                    pass  # Signal type not defined in SignalType enum

                                previous_states[signal] = new_value

                # Sleep for the polling interval
                time.sleep(self.polling_interval)

        except Exception as e:
            logger.error(f'Exception in input polling thread: {e}')
            self.input_running = False

    def set_output_pin(self, signal: str, value: bool):
        """
        Set an output pin to a specific value

        Args:
            signal: Signal name (e.g., 'L_REQ', 'READY')
            value: Pin value (True/False)
        """
        import ctypes

        # ── Determine which card we’re talking to ──────────────────────────
        if signal in self.e84_pin_mappings:
            dio_id = self.e84_dio_id
            pin = self.e84_pin_mappings[signal]
            card = 'E84'
            # Port-1 lines are wired to this card → add 8 to reach bit-index 8-15
            pin += 8  # 0-5  →  8-13
        elif self.dual_card_mode and signal in self.lpt_pin_mappings:
            dio_id = self.lpt_dio_id
            pin = self.lpt_pin_mappings[signal]
            card = 'LPT'
        else:
            logger.error(f'Unknown or unsupported output signal: {signal}')
            return False

        if is_ascii_mode():
            # In ASCII mode, if it's an LPT signal, log that it's being handled via ASCII
            if signal in [
                'CARRIER_PRESENT_0',
                'LATCH_LOCKED_0',
                'LPT_ERROR_0',
                'LPT_READY_0',
                'CARRIER_PRESENT_1',
                'LATCH_LOCKED_1',
                'LPT_ERROR_1',
                'LPT_READY_1',
            ]:
                logger.debug(
                    f'Signal {signal} is handled through ASCII interface in this mode'
                )
                return True

        else:
            logger.error(f'Unknown or unsupported output signal: {signal}')
            return False

        # ── Drive the bit via Contec’s API-DIO(LNX) ───────────────────────
        data = ctypes.c_ubyte(1 if value else 0)
        ret = cdio.DioOutBit(dio_id, ctypes.c_short(pin), data)
        if ret != cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(ret, self.err_str)
            logger.error(
                f'[{card}] failed DioOutBit(bit={pin}) → {self.err_str.value.decode()}'
            )
            return False

        logger.debug(f'[{card}] {signal} (bit {pin}) set to {value}')
        return True

    def read_input_pin(self, signal: str) -> bool:
        """
        Read the current state of an input pin

        Args:
            signal: Signal name (e.g., 'CS_0', 'VALID')

        Returns:
            Current pin state (True/False)
        """
        import ctypes

        # Determine which card to use based on the signal
        if signal in self.e84_pin_mappings:
            dio_id = self.e84_dio_id
            pin = self.e84_pin_mappings[signal]
            card_name = 'E84'
        elif self.dual_card_mode and signal in self.lpt_pin_mappings:
            dio_id = self.lpt_dio_id
            pin = self.lpt_pin_mappings[signal]
            card_name = 'LPT'
        else:
            # In ASCII mode, if it's an LPT signal, log that it's being handled via ASCII
            if signal in [
                'CARRIER_PRESENT_0',
                'LATCH_LOCKED_0',
                'LPT_ERROR_0',
                'LPT_READY_0',
                'CARRIER_PRESENT_1',
                'LATCH_LOCKED_1',
                'LPT_ERROR_1',
                'LPT_READY_1',
            ]:
                logger.debug(
                    f'Signal {signal} is handled through ASCII interface in this mode'
                )
                # Return default values for LPT signals in ASCII mode
                # These will be overridden by the LoadPortAscii instance
                default_values = {
                    'CARRIER_PRESENT_0': False,
                    'CARRIER_PRESENT_1': False,
                    'LATCH_LOCKED_0': False,
                    'LATCH_LOCKED_1': False,
                    'LPT_ERROR_0': False,
                    'LPT_ERROR_1': False,
                    'LPT_READY_0': True,
                    'LPT_READY_1': True,
                }
                return default_values.get(signal, False)
            logger.error(f'Unknown signal: {signal}')
            return False

        io_data = ctypes.c_ubyte()

        ret = cdio.DioInpBit(dio_id, ctypes.c_short(pin), ctypes.byref(io_data))
        if ret != cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(ret, self.err_str)
            logger.error(
                f'Failed to read {card_name} input bit {pin} ({signal}): {self.err_str.value.decode("utf-8")}'
            )
            return False

        return bool(io_data.value)

    def close(self):
        """Close DIO device connections"""
        self.stop_input_monitoring()

        # Close E84 DIO device
        ret = cdio.DioExit(self.e84_dio_id)
        if ret != cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(ret, self.err_str)
            logger.error(
                f'Failed to close E84 DIO device: {self.err_str.value.decode("utf-8")}'
            )
        else:
            logger.info('E84 DIO device closed successfully')

        # Close LPT DIO device (only in dual card mode)
        if self.dual_card_mode and self.lpt_dio_id is not None:
            ret = cdio.DioExit(self.lpt_dio_id)
            if ret != cdio.DIO_ERR_SUCCESS:
                cdio.DioGetErrorString(ret, self.err_str)
                logger.error(
                    f'Failed to close LPT DIO device: {self.err_str.value.decode("utf-8")}'
                )
            else:
                logger.info('LPT DIO device closed successfully')


class EmulationDioHardwareInterface(DioHardwareInterface):
    """
    Hardware interface for emulation mode.

    This class extends the real DioHardwareInterface but overrides methods
    to simulate LPT signals while using real hardware for E84 signals.
    """

    def __init__(
        self,
        signal_manager: SignalManager,
        callback_manager: CallbackManager,
        e84_device_name: str,
        e84_pin_mappings: Dict[str, int],
        simulation_config: Dict = None,
        polling_interval: float = 0.1,
        **kwargs,  # Ignore LPT-related parameters
    ):
        """
        Initialize the emulation hardware interface.

        Args:
            signal_manager: The signal manager instance
            callback_manager: The callback manager instance
            e84_device_name: The name of the DIO device for E84 signals
            e84_pin_mappings: Pin mappings for E84 signals
            simulation_config: Configuration for simulating LPT signals
            polling_interval: Interval for polling hardware inputs
            **kwargs: Additional parameters (ignored)
        """
        # Get simulation parameters
        self.simulation_config = simulation_config or {}
        self.auto_respond = self.simulation_config.get('auto_respond', True)
        self.random_errors = self.simulation_config.get('random_errors', False)
        self.error_rate = self.simulation_config.get('error_rate', 0.05)
        self.response_delay = self.simulation_config.get('response_delay', 0.1)

        # Initialize simulated LPT signals
        initial_states = self.simulation_config.get('initial_states', {})
        self.simulated_lpt_signals = {
            'CARRIER_PRESENT_0': False,
            'LATCH_LOCKED_0': False,
            'LPT_ERROR_0': False,
            'LPT_READY_0': True,
            'CARRIER_PRESENT_1': False,
            'LATCH_LOCKED_1': False,
            'LPT_ERROR_1': False,
            'LPT_READY_1': True,
        }

        # Override with any provided initial states
        for signal, value in initial_states.items():
            if signal in self.simulated_lpt_signals:
                self.simulated_lpt_signals[signal] = value

        # Add thread for simulating LPT signals
        self.lpt_simulation_running = False
        self.lpt_simulation_thread = None

        # Initialize with just the E84 device (no LPT device)
        super().__init__(
            signal_manager=signal_manager,
            callback_manager=callback_manager,
            e84_device_name=e84_device_name,
            e84_pin_mappings=e84_pin_mappings,
            polling_interval=polling_interval,
        )

        logger.info('Emulation DIO hardware interface initialized')

    def initialize(self):
        """Initialize the hardware and simulated LPT signals."""
        # Call parent class to initialize hardware
        super().initialize()

        # Initialize simulated LPT signals in signal manager
        for signal, value in self.simulated_lpt_signals.items():
            self.signal_manager.set_signal(signal, value)

        # Start LPT simulation thread
        self._start_lpt_simulation()

        logger.info('Emulation hardware and simulated LPT signals initialized')

    def _start_lpt_simulation(self):
        """Start the LPT simulation thread."""
        if self.lpt_simulation_running:
            logger.warning('LPT simulation thread is already running')
            return

        self.lpt_simulation_running = True
        self.lpt_simulation_thread = threading.Thread(
            target=self._lpt_simulation_loop, daemon=True
        )
        self.lpt_simulation_thread.start()
        logger.info('Started LPT signal simulation thread')

    def _stop_lpt_simulation(self):
        """Stop the LPT simulation thread."""
        self.lpt_simulation_running = False
        if self.lpt_simulation_thread:
            self.lpt_simulation_thread.join(timeout=1.0)
        logger.info('Stopped LPT signal simulation thread')

    def _lpt_simulation_loop(self):
        """Background thread that simulates LPT signals."""
        logger.debug('LPT simulation thread started')

        try:
            while self.lpt_simulation_running:
                # Simulate LPT signal responses based on E84 signals
                if self.auto_respond:
                    self._simulate_lpt_responses()

                # Sleep for the polling interval
                time.sleep(self.polling_interval)

        except Exception as e:
            logger.error(f'Exception in LPT simulation thread: {e}')
            self.lpt_simulation_running = False

    def _simulate_lpt_responses(self):
        """
        Simulate realistic LPT responses to E84 signals.
        This provides a simple state machine simulation for the LPT.
        """
        # Get current E84 signal states
        l_req = self.signal_manager.get_signal('L_REQ')
        u_req = self.signal_manager.get_signal('U_REQ')
        ready = self.signal_manager.get_signal('READY')

        # Simulate carrier presence changes based on load/unload requests
        for port in [0, 1]:
            carrier_present = self.simulated_lpt_signals.get(
                f'CARRIER_PRESENT_{port}', False
            )

            # During load operation, eventually set carrier present
            if l_req and ready and not carrier_present and random.random() < 0.05:
                self._set_simulated_lpt_signal(f'CARRIER_PRESENT_{port}', True)

            # During unload operation, eventually clear carrier present
            if u_req and ready and carrier_present and random.random() < 0.05:
                self._set_simulated_lpt_signal(f'CARRIER_PRESENT_{port}', False)

        # Randomly introduce errors if enabled
        if self.random_errors and random.random() < self.error_rate:
            port = random.randint(0, 1)
            self._set_simulated_lpt_signal(
                f'LPT_ERROR_{port}',
                not self.simulated_lpt_signals.get(f'LPT_ERROR_{port}', False),
            )

    def _set_simulated_lpt_signal(self, signal: str, value: bool):
        """Update a simulated LPT signal and the signal manager."""
        if (
            signal in self.simulated_lpt_signals
            and self.simulated_lpt_signals[signal] != value
        ):
            self.simulated_lpt_signals[signal] = value

            # Introduce artificial delay to simulate hardware response time
            if self.response_delay > 0:
                time.sleep(self.response_delay)

            # Update signal manager
            old_value = self.signal_manager.get_signal(signal)
            self.signal_manager.set_signal(signal, value)

            # Log the change
            logger.debug(
                f'Emulation mode: LPT signal {signal} changed from {old_value} to {value}'
            )

            # Try to trigger callbacks
            try:
                from callback_manager import SignalType

                signal_type = SignalType[signal]
                self.callback_manager.notify(signal_type, old_value, value)
            except (KeyError, AttributeError):
                pass  # Signal type not defined in SignalType enum

    def set_output_pin(self, signal: str, value: bool):
        """
        Override to handle LPT signals differently.

        Args:
            signal: Signal name
            value: Signal value (True/False)

        Returns:
            True if successful, False otherwise
        """
        # Safely check if this is an LPT signal
        if (
            hasattr(self, 'simulated_lpt_signals')
            and signal in self.simulated_lpt_signals
        ):
            # Simulate setting the LPT signal
            self._set_simulated_lpt_signal(signal, value)
            return True
        else:
            # Use real hardware for E84 signals
            return super().set_output_pin(signal, value)

    def read_input_pin(self, signal: str) -> bool:
        """
        Override to handle LPT signals differently.

        Args:
            signal: Signal name

        Returns:
            Signal value (True/False)
        """
        # Safely check if this is an LPT signal
        if (
            hasattr(self, 'simulated_lpt_signals')
            and signal in self.simulated_lpt_signals
        ):
            # Return simulated signal value
            if self.response_delay > 0:
                time.sleep(self.response_delay * 0.5)  # Use shorter delay for reads
            return self.simulated_lpt_signals.get(signal, False)
        else:
            # Use real hardware for E84 signals
            return super().read_input_pin(signal)

    def close(self):
        """Close the emulation hardware interface."""
        # Stop LPT simulation
        self._stop_lpt_simulation()

        # Close real hardware
        super().close()

        logger.info('Emulation DIO hardware interface closed')


# Factory function to create the appropriate hardware interface
def create_hardware_interface(
    operating_mode: str,
    signal_manager: SignalManager,
    callback_manager: CallbackManager,
    config,
    **kwargs,
):
    """
    Factory function to create the appropriate hardware interface based on mode.

    Args:
        operating_mode: The operating mode ("production", "emulation", or "simulation")
        signal_manager: The signal manager instance
        callback_manager: The callback manager instance
        config: The configuration module
        **kwargs: Additional parameters

    Returns:
        A hardware interface instance
    """
    # Get common configuration values
    # Check if polling_interval is already in kwargs before getting from config
    if 'polling_interval' not in kwargs:
        kwargs['polling_interval'] = getattr(config, 'POLLING_INTERVAL', 0.1)

    simulation_config = getattr(config, 'SIMULATION_CONFIG', {})

    # Always use simulated interface for simulation mode
    if operating_mode.lower() in ['simulation', 'sim']:
        logger.info('Creating simulated hardware interface (all signals simulated)')
        return SimulatedDioHardwareInterface(
            signal_manager=signal_manager,
            callback_manager=callback_manager,
            simulation_config=simulation_config,
            **kwargs,
        )

    # For emulation and production modes, check if cdio is available
    if not _try_import_cdio():
        logger.warning('cdio module not available - falling back to simulation mode')
        return SimulatedDioHardwareInterface(
            signal_manager=signal_manager,
            callback_manager=callback_manager,
            simulation_config=simulation_config,
            **kwargs,
        )

    # If cdio is available, create the appropriate real hardware interface
    if operating_mode.lower() in ['emulation', 'emu']:
        logger.info(
            'Creating emulation hardware interface (E84 signals real, LPT signals simulated)'
        )
        return EmulationDioHardwareInterface(
            signal_manager=signal_manager,
            callback_manager=callback_manager,
            e84_device_name=getattr(config, 'DIO_E84_DEVICE', 'DIO000'),
            e84_pin_mappings=getattr(config, 'E84_PIN_MAPPINGS', {}),
            simulation_config=simulation_config,
            **kwargs,
        )
    else:  # production mode
        # Production mode: All signals real
        interface_type = getattr(config, 'LOAD_PORT_INTERFACE', 'parallel')
        e84_device_name = getattr(config, 'DIO_E84_DEVICE', 'DIO000')
        e84_pin_mappings = getattr(config, 'E84_PIN_MAPPINGS', {})

        if interface_type == 'ascii':
            # ASCII interface: Only E84 DIO card
            logger.info(
                'Creating production hardware interface with ASCII communication'
            )
            return DioHardwareInterface(
                signal_manager=signal_manager,
                callback_manager=callback_manager,
                e84_device_name=e84_device_name,
                e84_pin_mappings=e84_pin_mappings,
                **kwargs,
            )
        else:
            # Parallel interface: Both DIO cards
            lpt_device_name = getattr(config, 'DIO_LPT_DEVICE', 'DIO001')
            lpt_pin_mappings = getattr(config, 'LPT_PIN_MAPPINGS', {})

            logger.info(
                'Creating production hardware interface with parallel communication'
            )
            return DioHardwareInterface(
                signal_manager=signal_manager,
                callback_manager=callback_manager,
                e84_device_name=e84_device_name,
                lpt_device_name=lpt_device_name,
                e84_pin_mappings=e84_pin_mappings,
                lpt_pin_mappings=lpt_pin_mappings,
                **kwargs,
            )
