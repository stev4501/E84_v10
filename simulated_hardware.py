"""
simulated_hardware.py

This module provides simulated hardware interfaces for testing purposes.
It includes a SimulatedDioHardwareInterface that mimics the DioHardwareInterface
and an EmulationDioHardwareInterface that uses real hardware for E84 signals
but simulates LPT signals.

IMPORTANT: This version avoids importing the DIO hardware interface in
simulation mode to prevent dependency on hardware drivers.
"""

import random
import threading
import time
from typing import Dict

from loguru import logger

from callback_manager import CallbackManager, SignalType
from config_e84 import get_config
from signal_manager import SignalManager

config = get_config()


class SimulatedDioHardwareInterface:
    """
    Simulated hardware interface for testing.

    This class provides a complete simulation of the DioHardwareInterface
    for use in simulation mode, where no real hardware is available.
    """

    def __init__(
        self,
        signal_manager: SignalManager,
        callback_manager: CallbackManager,
        simulation_config: Dict = None,
        polling_interval: float = 0.1,
        **kwargs,  # Ignore other parameters
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
        self.signal_manager = signal_manager
        self.callback_manager = callback_manager
        self.simulation_config = simulation_config or {}

        # Get simulation parameters
        self.auto_respond = self.simulation_config.get('auto_respond', True)
        self.random_errors = self.simulation_config.get('random_errors', False)
        self.error_rate = self.simulation_config.get('error_rate', 0.05)
        self.response_delay = self.simulation_config.get('response_delay', 0.1)

        # Initialize simulated signal states
        initial_states = self.simulation_config.get('initial_states', {})
        self.simulated_signals = {
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

        # Threading and status flags
        self.input_running = False
        self.polling_thread = None
        self.polling_interval = polling_interval

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
                signal_type = SignalType[signal]
                self.callback_manager.notify(signal_type, old_value, value)
            except (KeyError, AttributeError):
                pass  # Signal type not defined in SignalType enum

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


# Only import the real DioHardwareInterface for emulation mode
# The import is inside the function to avoid loading the hardware drivers
# when only simulation mode is needed


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

    if operating_mode.lower() in ['simulation', 'sim']:
        # Simulation mode: All signals simulated
        logger.info('Creating simulated hardware interface (all signals simulated)')
        return SimulatedDioHardwareInterface(
            signal_manager=signal_manager,
            callback_manager=callback_manager,
            simulation_config=simulation_config,
            **kwargs,
        )
    else:  # emulation or production mode requires real hardware
        # Import the real hardware interface only when needed
        try:
            from hardware_interface import DioHardwareInterface
        except ImportError as e:
            logger.error(f'Failed to import DioHardwareInterface: {e}')
            logger.error(
                "Hardware drivers may not be installed. Use 'simulation' mode if you don't have hardware drivers."
            )
            raise

        if operating_mode.lower() in ['emulation', 'emu']:
            # Emulation mode: E84 signals real, LPT signals simulated
            # Import the EmulationDioHardwareInterface class and instantiate it
            logger.info(
                'Creating emulation hardware interface (E84 signals real, LPT signals simulated)'
            )

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
                    e84_pin_mappings: dict[str, int],
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
                    self.random_errors = self.simulation_config.get(
                        'random_errors', False
                    )
                    self.error_rate = self.simulation_config.get('error_rate', 0.05)
                    self.response_delay = self.simulation_config.get(
                        'response_delay', 0.1
                    )

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
                    # Initialize real hardware
                    super().initialize()

                    # Initialize simulated LPT signals in signal manager
                    for signal, value in self.simulated_lpt_signals.items():
                        self.signal_manager.set_signal(signal, value)

                    # Start LPT simulation thread
                    self._start_lpt_simulation()

                    logger.info(
                        'Emulation hardware and simulated LPT signals initialized'
                    )

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
                        if (
                            l_req
                            and ready
                            and not carrier_present
                            and random.random() < 0.05
                        ):
                            self._set_simulated_lpt_signal(
                                f'CARRIER_PRESENT_{port}', True
                            )

                        # During unload operation, eventually clear carrier present
                        if (
                            u_req
                            and ready
                            and carrier_present
                            and random.random() < 0.05
                        ):
                            self._set_simulated_lpt_signal(
                                f'CARRIER_PRESENT_{port}', False
                            )

                    # Randomly introduce errors if enabled
                    if self.random_errors and random.random() < self.error_rate:
                        port = random.randint(0, 1)
                        self._set_simulated_lpt_signal(
                            f'LPT_ERROR_{port}',
                            not self.simulated_lpt_signals.get(
                                f'LPT_ERROR_{port}', False
                            ),
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
                    if signal == 'VALID':
                        result = super().read_input_pin(signal)
                        logger.debug(
                            f'Emulation mode: LPT signal VALID read as {result}'
                        )
                        return result

                    # Safely check if this is an LPT signal
                    if (
                        hasattr(self, 'simulated_lpt_signals')
                        and signal in self.simulated_lpt_signals
                    ):
                        # Return simulated signal value
                        if self.response_delay > 0:
                            time.sleep(
                                self.response_delay * 0.5
                            )  # Use shorter delay for reads
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
