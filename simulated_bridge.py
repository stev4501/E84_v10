# simulated_bridge.py

# TODO: May be able to delete this file. Using the signal_bridge.py instead, even for simulation mode.
"""
A simulated version of the E84SignalBridge that doesn't depend on hardware drivers.
This is used in simulation mode to avoid loading hardware dependencies.
"""

from loguru import logger

from callback_manager import CallbackManager, SignalType
from signal_manager import SignalManager


class SimulatedE84SignalBridge:
    """
    Simulated bridge between E84 software signals and hardware I/O.

    This class mimics the functionality of E84SignalBridge without requiring
    hardware drivers. It's used in simulation mode.
    """

    # Define which signals are outputs (we write to hardware)
    OUTPUT_SIGNALS = {'L_REQ', 'U_REQ', 'READY', 'HO_AVBL', 'ES'}

    # Define which signals are inputs (we read from hardware)
    INPUT_SIGNALS = {
        'CS_0',
        'CS_1',
        'VALID',
        'TR_REQ',
        'BUSY',
        'COMPT',
        'CARRIER_PRESENT_0',
        'LATCH_LOCKED_0',
        'LPT_ERROR_0',
        'LPT_READY_0',
        'CARRIER_PRESENT_1',
        'LATCH_LOCKED_1',
        'LPT_ERROR_1',
        'LPT_READY_1',
    }

    def __init__(
        self,
        signal_manager: SignalManager,
        callback_manager: CallbackManager,
        hardware_interface,
    ):
        """
        Initialize the simulated E84 signal bridge.

        Args:
            signal_manager: The E84 signal manager
            callback_manager: The E84 callback manager
            hardware_interface: The simulated hardware interface
        """
        self.signal_manager = signal_manager
        self.callback_manager = callback_manager
        self.hardware = hardware_interface

        # Set of signals that have been initialized
        self.initialized_signals: set[str] = set()

        # Register callback for all output signals
        self._register_output_callbacks()

        logger.info('Simulated E84 signal bridge initialized')

    def _register_output_callbacks(self):
        """Register callbacks for all output signals"""
        for signal in self.OUTPUT_SIGNALS:
            try:
                # Try to get the appropriate SignalType enum
                signal_type = SignalType[signal.upper()]

                # Register callback for this signal
                self.callback_manager.register(
                    signal_type=signal_type,
                    callback=lambda signal,
                    new,
                    old,: self._handle_output_signal_change(signal, new, old),
                )
                logger.debug(f'Registered callback for output signal: {signal}')

            except (KeyError, AttributeError) as e:
                logger.warning(f'Could not register callback for {signal}: {e}')

    def _handle_output_signal_change(
        self, signal: str, old_value: bool, new_value: bool
    ):
        """
        Handle changes to output signals and update hardware

        Args:
            signal: The signal that changed
            old_value: Previous signal value
            new_value: New signal value
        """
        if signal in self.OUTPUT_SIGNALS:
            logger.debug(
                f'Output signal {signal} changed from {old_value} to {new_value}'
            )

            # Update the simulated hardware
            self.hardware.set_output_pin(signal, new_value)

    def initialize(self):
        """Initialize the bridge by syncing all signals with hardware"""
        logger.info('Initializing simulated E84 signal bridge')

        # First, read all input signals from hardware and update signal manager
        for signal in self.INPUT_SIGNALS:
            try:
                value = self.hardware.read_input_pin(signal)
                self.signal_manager.set_signal(signal, value)
                logger.debug(f'Initialized input signal {signal} to {value}')
                self.initialized_signals.add(signal)
            except Exception as e:
                logger.error(f'Failed to initialize input signal {signal}: {e}')

        # Now, write all output signals to hardware
        for signal in self.OUTPUT_SIGNALS:
            try:
                value = self.signal_manager.get_signal(signal)
                self.hardware.set_output_pin(signal, value)
                logger.debug(f'Initialized output signal {signal} to {value}')
                self.initialized_signals.add(signal)
            except Exception as e:
                logger.error(f'Failed to initialize output signal {signal}: {e}')

        # Start hardware input monitoring
        self.hardware.start_input_monitoring()
        logger.info(
            f'Simulated E84 signal bridge initialized with {len(self.initialized_signals)} signals'
        )

    def shutdown(self):
        """Shutdown the bridge and stop hardware monitoring"""
        logger.info('Shutting down simulated E84 signal bridge')
        self.hardware.stop_input_monitoring()

        # Set safe output states before shutdown
        safe_outputs = {
            'L_REQ': False,
            'U_REQ': False,
            'READY': False,
            'HO_AVBL': True,
            'ES': True,
        }

        for signal, value in safe_outputs.items():
            try:
                self.hardware.set_output_pin(signal, value)
                logger.debug(f'Set {signal} to safe state: {value}')
            except Exception as e:
                logger.error(f'Failed to set {signal} to safe state: {e}')

        self.hardware.close()
        logger.info('Simulated E84 signal bridge shut down')
