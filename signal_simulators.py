# signal_simulators.py

"""
This module provides simulators for the E84 interface, including the AGV and equipment sides.
It allows simulation of signal states and behavior, enabling testing and validation of the
E84 protocol without physical hardware.

Classes:
- OperationError: Custom exception for invalid operations in the simulators.
- AgvSimulator: Simulates the AGV side of the E84 interface.
- EquipmentSimulator: Simulates the equipment side of the E84 interface (load port and process tool).

Dependencies:
- signal_manager: Manages signal states.
- logging: Provides logging functionality for simulation activities.

"""

from typing import Dict
from loguru import logger

from callback_manager import CallbackManager
from load_port import LPTSignals


class OperationError(Exception):
    """
    Raised when an invalid operation is attempted within the simulation.

    Example:
            raise OperationError("Invalid signal transition detected.")
    """

    pass


class AgvSimulator:
    """Simulates signals for the AGV side of the E84 interface."""

    def __init__(self, signal_manager, e84_controller):
        self.signal_manager = signal_manager
        self.e84_controller = e84_controller

        # Initialize sequence tracking
        self.current_step = 0
        self.current_operation = None
        self.selected_port = self.e84_controller.selected_port_index

    def start_sequence(self, operation: str = 'load', port: int = 0):
        """Initialize a new sequence."""
        self.current_operation = operation
        self.current_step = 0
        logger.info(f'Starting {operation} sequence for port {port}')

    def execute_step(self, step: int, port) -> bool:
        """
        Execute a specific step in the sequence.
        Returns True if step was executed successfully.
        """

        try:
            if step == 0:
                # Step 1: Turn on CS_x signal
                logger.debug(f'Step 1: CS_{port} signal ON')
                self.signal_manager.set_signal(f'CS_{port}', True)

            elif step == 1:
                # Step 1: Turn on valid signal
                logger.debug('Step 2: VALID signal ON')
                self.signal_manager.set_signal('VALID', True)

            elif step == 2:
                # Step 2: Turn on tr_req signal
                logger.debug('Step 3: TR_REQ signal ON')
                self.signal_manager.set_signal('TR_REQ', True)

            elif step == 3:
                # Step 3: Turn on busy signal
                logger.debug('Step 4: BUSY signal ON')
                self.signal_manager.set_signal('BUSY', True)

            elif step == 5:
                # Step 5: Turn off busy and tr_req signal, turn on compt
                logger.debug('Step 5: BUSY, and TR_REQ signal OFF, COMPT signal ON')
                self.signal_manager.set_signal('BUSY', False)
                self.signal_manager.set_signal('TR_REQ', False)
                self.signal_manager.set_signal('COMPT', True)

            elif step == 6:
                # Step 6 Turn off compt, valid, and cs signal
                logger.debug(
                    f'Step 6: COMPT, VALID, and CS_{port} signal OFF, sequence complete'
                )
                self.signal_manager.set_signal('VALID', False)
                self.signal_manager.set_signal('COMPT', False)
                self.signal_manager.set_signal(f'CS_{port}', False)
            elif step == 7:
                # Reset sequence tracking
                self.current_operation = None
                self.port_status = None

            return True

        except Exception as e:
            logger.error(f'Error executing step {step}: {str(e)}')
            return False

    def reset_sequence(self):
        """Reset all sequence-related variables and signals."""
        try:
            # Reset all AGV signals
            signals = ['CS_0', 'CS_1', 'VALID', 'TR_REQ', 'BUSY', 'COMPT']
            for signal in signals:
                self.signal_manager.set_signal(signal, False)

            # Reset sequence tracking
            self.current_step = 0
            self.current_operation = None
            self.port_status = None

            logger.debug('AGV sequence reset complete')

        except Exception as e:
            logger.error(f'Error resetting sequence: {str(e)}')


class EquipmentSimulator:
    """
    Simulates signals for the load port and/or tool.
    Pod present & latch locked. (TODO: Simulate errors)
    """

    def __init__(
        self,
        signal_manager,
        e84_controller,
        callback_manager: CallbackManager,
        e84_pin_mappings: Dict[str, int],
        simulation_config: Dict = None,
        polling_interval: float = 0.1,
        **kwargs,  # Ignore LPT-related parameters
    ):
        self.signal_manager = signal_manager
        self.e84_controller = e84_controller
        self.selected_machine = None
        self.current_operation = None
        self.port_status = None

    def execute_step(self, step: int, port) -> bool:
        """Execute equipment-specific actions for a given step."""

        try:
            # Equipment only acts on step 4 - carrier present signal change
            if step == 4:
                # Get the load port based on port_id
                machine = (
                    self.e84_controller.lpt_0
                    if port == 0
                    else self.e84_controller.lpt_1
                )
                load_port = machine.load_port

                lpt_signal_names = [
                    f'CARRIER_PRESENT_{port}',
                    f'LATCH_LOCKED_{port}',
                    f'LPT_READY_{port}',
                    f'LPT_ERROR_{port}',
                ]
                lpt_signals = {
                    signal_name: self.signal_manager.get_signal(signal_name)
                    for signal_name in lpt_signal_names
                }

                # Toggle carrier present based on operation
                current_state = lpt_signals[f'CARRIER_PRESENT_{port}']
                new_state = not current_state
                load_port.set_signal(LPTSignals.CARRIER_PRESENT, new_state)
                # self.signal_manager.set_signal(f"CARRIER_PRESENT_{port}", new_state)
                logger.debug(
                    f'Step {step}: Changed CARRIER_PRESENT on LPT_{port} to {new_state}'
                )
                return True

            return (
                True  # Return true for other steps where equipment doesn't need to act
            )

        except Exception as e:
            logger.error(f'Error executing equipment step {step}: {str(e)}')
            return False

    def start_sequence(self, operation: str = 'LOAD', port_status: Dict = None):
        """Initialize equipment for a new sequence."""
        self.current_operation = operation
        self.port_status = port_status
        logger.debug(f'Equipment prepared for {operation} sequence')

    def reset_sequence(self):
        """Reset equipment sequence state."""
        self.current_operation = None
        self.port_status = None
        logger.debug('Equipment sequence reset')

    def tool_emo_signal_change(self):
        """Toggle tool EMO signal"""
        current_state = self.signal_manager.get_signal('EMO')
        # Change tool EMO signal
        new_state = not current_state
        self.signal_manager.set_signal('EMO', new_state)

    def lpt_error_signal_change(self):
        """Toggle tool LPT_ERROR signal"""
        port = self.port_status.port
        current_state = self.signal_manager.get_signal(f'LPT_ERROR_{port}')
        # Change LPT_ERROR signal
        new_state = not current_state
        port.set_signal(LPTSignals.LPT_ERROR, new_state)
