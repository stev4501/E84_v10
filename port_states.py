# port_states.py

from dataclasses import dataclass
from enum import Enum, auto

from loguru import logger

from callback_manager import CallbackManager
from signal_manager import SignalManager
from state_machine import E84StateMachine


class PortState(Enum):
    """Core states for availability checking"""

    SELECTED = auto()
    UNSELECTED = auto()
    AVAILABLE = auto()
    ERROR = auto()
    NOT_READY = auto()
    HO_OFF = auto()


@dataclass
class PortCondition:
    """Current condition of a load port"""

    lpt_ready: bool
    lpt_error: bool
    carrier_present: bool
    valid: bool
    ho_avbl: bool
    port_id: int = -1

    @property
    def state(self) -> PortState:
        """Get the current state of the port"""
        if not self.ho_avbl:
            return PortState.HO_OFF
        elif self.lpt_error:
            return PortState.ERROR
        elif not self.lpt_ready:
            return PortState.NOT_READY
        elif self.valid:
            return PortState.SELECTED
        else:
            return PortState.AVAILABLE

    @property
    def is_ready_for_handshake(self) -> bool:
        """Check if port is in a valid state to start a handshake"""
        return self.lpt_ready and not self.lpt_error and self.ho_avbl

    def with_error(self, error_value: bool) -> 'PortCondition':
        """Create a new condition with modified error state"""
        return PortCondition(
            port_id=self.port_id,
            lpt_ready=self.lpt_ready,
            lpt_error=error_value,
            carrier_present=self.carrier_present,
            valid=self.valid,
            ho_avbl=self.ho_avbl,
        )

    def with_ready(self, ready_value: bool) -> 'PortCondition':
        """Create a new condition with modified ready state"""
        return PortCondition(
            port_id=self.port_id,
            lpt_ready=ready_value,
            lpt_error=self.lpt_error,
            carrier_present=self.carrier_present,
            valid=self.valid,
            ho_avbl=self.ho_avbl,
        )

    def with_valid(self, valid_value: bool) -> 'PortCondition':
        """Create a new condition with modified valid state"""
        return PortCondition(
            port_id=self.port_id,
            lpt_ready=self.lpt_ready,
            lpt_error=self.lpt_error,
            carrier_present=self.carrier_present,
            valid=valid_value,
            ho_avbl=self.ho_avbl,
        )

    def with_ho_avbl(self, ho_avbl_value: bool) -> 'PortCondition':
        """Create a new condition with modified ho_avbl state"""
        return PortCondition(
            port_id=self.port_id,
            lpt_ready=self.lpt_ready,
            lpt_error=self.lpt_error,
            carrier_present=self.carrier_present,
            valid=self.valid,
            ho_avbl=ho_avbl_value,
        )

    def __str__(self) -> str:
        """Enhanced string representation for better logging"""
        return (
            f'[Port {self.port_id}]: {self.state.name}: '
            f'Ready: {self.lpt_ready} | '
            f'Error: {self.lpt_error} | '
            f'Carrier: {self.carrier_present} | '
            f'Valid: {self.valid} | '
            f'HO_AVBL: {self.ho_avbl}'
        )


class ErrorTransitionHandler:
    """Handles all signal transitions"""

    def __init__(self, e84_controller, signal_manager: SignalManager):
        self.controller = e84_controller
        self.signal_manager = signal_manager
        self.callback_manager = CallbackManager()
        self._setup_transition_map()
        self.register_callbacks()
        logger.info('Error transition handler initialized')

    def register_callbacks(self):
        """Register callbacks for critical signals"""

        # Handshake completion detection
        self.signal_manager.add_watcher('VALID', self._handle_valid_change)

        # Error conditions for both ports
        self.signal_manager.add_watcher(
            'LPT_ERROR_0',
            lambda signal, new, old: self._handle_error_change(0, new, old),
        )
        self.signal_manager.add_watcher(
            'LPT_ERROR_1',
            lambda signal, new, old: self._handle_error_change(1, new, old),
        )

        # Port readiness changes
        self.signal_manager.add_watcher(
            'LPT_READY_0',
            lambda signal, new, old: self._handle_ready_change(0, new, old),
        )
        self.signal_manager.add_watcher(
            'LPT_READY_1',
            lambda signal, new, old: self._handle_ready_change(1, new, old),
        )

        # Global handoff availability
        self.signal_manager.add_watcher('HO_AVBL', self._handle_ho_avbl_change)

        logger.debug('Error transition handler callbacks registered')

    def _handle_valid_change(self, signal_type, new_value, old_value):
        """
        Handle the end of a handshake and check for any error conditions
        Only triggered when VALID signal goes from True to False
        """
        ho_avbl = self.signal_manager.get_signal('HO_AVBL')
        if old_value and not new_value:  # Only when handshake is ending
            if ho_avbl:
                logger.debug('Handshake completion detected, checking port conditions')
                # Check both ports for errors
                for port_id in [0, 1]:
                    self._check_port_condition_after_handshake(port_id)

    def _handle_error_change(self, port_id: int, new_value: bool, old_value: bool):
        """Handle error condition changes"""
        valid = self.signal_manager.get_signal('VALID')

        if not valid:  # Only handle outside of handshake
            machine = self._get_machine(port_id)
            # Create port conditions for transition
            old_condition = self._get_current_port_condition(port_id).with_error(
                old_value
            )
            # Create new condition with error=new_value
            new_condition = old_condition.with_error(new_value)

            if new_value:  # Error condition turned ON outside of handshake
                if machine.state != 'ERROR_HANDLING':
                    logger.debug(
                        f'Error detected on port {port_id} outside of handshake'
                    )
                    self.handle_signal_change(port_id, old_condition, new_condition)

            else:  # Error condition turned OFF outside of handshake
                if machine.state == 'ERROR_HANDLING':
                    logger.debug(
                        f'Error cleared on port {port_id} outside of handshake'
                    )
                    # Use transition map to handle the change
                    self.handle_signal_change(port_id, old_condition, new_condition)

    def _handle_ready_change(self, port_id, new_value, old_value):
        """Handle port readiness changes"""
        valid = self.signal_manager.get_signal('VALID')

        if not valid:  # Only handle outside of handshake
            logger.debug(
                f'Ready signal changed to {new_value} on port {port_id} outside of handshake'
            )
            # Create port conditions for transition
            old_condition = self._get_current_port_condition(port_id).with_ready(
                old_value
            )
            # Create new condition with lpt_ready updated
            new_condition = old_condition.with_ready(new_value)
            # Use transition map to handle the change
            self.handle_signal_change(port_id, old_condition, new_condition)

    def _handle_ho_avbl_change(self, signal_name, new_value, old_value):
        """Handle HO_AVBL signal changes"""
        valid = self.signal_manager.get_signal('VALID')

        if not valid:  # Only care about changes outside of active handshake
            logger.debug(f'HO_AVBL changed to {new_value} outside of handshake')

            # Check both ports
            for port_id in [0, 1]:
                old_condition = self._get_current_port_condition(port_id).with_ho_avbl(
                    old_value
                )
                new_condition = old_condition.with_ho_avbl(new_value)
                self.handle_signal_change(port_id, old_condition, new_condition)

    def _check_port_condition_after_handshake(self, port_id: int):
        """Check port condition after a handshake and trigger appropriate transitions"""
        machine = self._get_machine(port_id)

        # Get the current port condition
        condition = self._get_current_port_condition(port_id)
        logger.debug(f'Post-handshake LPT check: {condition}')

        # Determine appropriate state based on current conditions
        if not condition.ho_avbl:
            logger.debug(
                f'[Port {port_id}]: HO_AVBL is {condition.ho_avbl} after handshake'
            )

            if condition.lpt_error:
                logger.debug(
                    f'[Port {port_id}]: Error condition detected after handshake'
                )
                machine.to_ERROR_HANDLING()

            elif not condition.lpt_ready:
                logger.debug(f'[Port {port_id}]: Not ready after handshake')
                machine.to_IDLE_UNAVBL()

        else:
            logger.debug(f'[Port {port_id}] No issues detected after handshake')
            machine.to_IDLE()  # Return to IDLE state

    def _get_current_port_condition(self, port_id: int) -> PortCondition:
        """Get the current condition of a port"""

        return PortCondition(
            port_id=port_id,
            lpt_ready=self.signal_manager.get_signal(f'LPT_READY_{port_id}'),
            lpt_error=self.signal_manager.get_signal(f'LPT_ERROR_{port_id}'),
            carrier_present=self.signal_manager.get_signal(
                f'CARRIER_PRESENT_{port_id}'
            ),
            valid=self.signal_manager.get_signal('VALID'),
            ho_avbl=self.signal_manager.get_signal('HO_AVBL'),
        )

    def _setup_transition_map(self):
        """Initialize the transition mapping"""
        self.state_transitions = {
            # ---------------
            # From SELECTED state
            # ---------------
            (PortState.SELECTED, PortState.HO_OFF): self._handle_selected_to_ho_off,
            (PortState.SELECTED, PortState.ERROR): self._handle_selected_to_ho_off,
            (
                PortState.SELECTED,
                PortState.NOT_READY,
            ): self._handle_selected_to_ho_off,
            # (PortState.UNSELECTED, PortState.ERROR): self._handle_unselected_to_recovery,
            # -----------------
            # From HO_OFF state
            # -----------------
            (PortState.HO_OFF, PortState.AVAILABLE): self._handle_ho_off_to_available,
            (PortState.HO_OFF, PortState.ERROR): self._handle_ho_off_to_error,
            (PortState.HO_OFF, PortState.NOT_READY): self._handle_ho_off_to_not_ready,
            # -----------------
            # From ERROR state
            # -----------------
            (PortState.ERROR, PortState.AVAILABLE): self._handle_error_to_available,
            (PortState.ERROR, PortState.NOT_READY): self._handle_error_to_not_ready,
            (PortState.ERROR, PortState.HO_OFF): self._handle_error_to_ho_off,
            # -----------------
            # From NOT_READY state
            # -----------------
            (
                PortState.NOT_READY,
                PortState.AVAILABLE,
            ): self._handle_not_ready_to_available,
            (PortState.NOT_READY, PortState.ERROR): self._handle_not_ready_to_error,
            (PortState.NOT_READY, PortState.HO_OFF): self._handle_not_ready_to_ho_off,
            # -----------------
            # From AVAILABLE state
            # -----------------
            (PortState.AVAILABLE, PortState.ERROR): self._handle_available_to_error,
            (
                PortState.AVAILABLE,
                PortState.NOT_READY,
            ): self._handle_available_to_not_ready,
            (PortState.AVAILABLE, PortState.HO_OFF): self._handle_available_to_ho_off,
        }

    def handle_signal_change(
        self, port_id: int, old_condition: PortCondition, new_condition: PortCondition
    ) -> None:
        """
        Main entry point for handling signal changes
        Will be called both by the controller and by internal signal callbacks
        """
        old_state = old_condition.state
        new_state = new_condition.state

        if old_state == new_state:
            logger.debug(f'State transition: {old_state} -> {new_state}')
            return  # No state transition needed

        transition_handler = self.state_transitions.get((old_state, new_state))

        if transition_handler:
            logger.debug(
                f'[Port {port_id}] State transition: {old_state.name} -> {new_state.name}'
            )
            transition_handler(port_id, old_condition, new_condition)

        else:
            logger.warning(f'Unhandled state transition: {old_state} -> {new_state}')

    def _handle_selected_to_ho_off(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from SELECTED to HO_OFF state"""
        machine = self._get_machine(port_id)
        valid = self.signal_manager.get_signal('VALID')
        ready_and_error_clear = machine.load_port.ready_and_error_clear

        if not valid:  # Only recover if no handshake is active
            if machine.state == 'HO_UNAVBL' and ready_and_error_clear:
                machine.attempt_recovery()
        if valid:
            machine.to_HO_UNAVBL()

    def _handle_unselected_to_recovery(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from UNSELECTED to RECOVERY state"""
        machine = self._get_machine(port_id)
        valid = self.signal_manager.get_signal('VALID')

        if not valid:  # Only recover if no handshake is active
            machine.recover_from_unavailable()

    def _handle_ho_off_to_available(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from HO_OFF to AVAILABLE state"""
        machine = self._get_machine(port_id)
        valid = self.signal_manager.get_signal('VALID')
        ready_and_error_clear = machine.load_port.ready_and_error_clear

        if not valid:  # Only recover if no handshake is active
            if machine.state == 'HO_UNAVBL' and ready_and_error_clear:
                machine.ho_avbl_return_idle()

    def _handle_ho_off_to_error(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from HO_OFF to ERROR state"""
        machine = self._get_machine(port_id)
        error = machine.load_port.get_port_status().error_active

        logger.debug(f'Port {port_id}: Error active = {error}')

        if error and machine.state == 'HO_UNAVBL':
            machine.to_ERROR_HANDLING()

    def _handle_ho_off_to_not_ready(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from HO_OFF to NOT_READY state"""
        machine = self._get_machine(port_id)
        ready = machine.load_port.get_port_status().lpt_ready

        logger.debug(f'Port {port_id}: LPT_READY = {ready}')

        if not ready and machine.state == 'HO_UNAVBL':
            machine.to_IDLE_UNAVBL()

    def _handle_error_to_available(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from ERROR to AVAILABLE state"""
        machine = self._get_machine(port_id)
        valid = self.signal_manager.get_signal('VALID')

        if not valid:  # Only recover if handshake is not active
            if machine.state == 'ERROR_HANDLING':
                machine.attempt_recovery()

    def _handle_error_to_not_ready(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from ERROR to NOT_READY state"""
        machine = self._get_machine(port_id)
        valid = self.signal_manager.get_signal('VALID')

        if not valid:
            if machine.state == 'ERROR_HANDLING':
                machine.to_IDLE_UNAVBL()

    def _handle_error_to_ho_off(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from ERROR to HO_OFF state"""
        machine = self._get_machine(port_id)
        other_machine = self._get_machine(1 - port_id)

        if (
            machine.state == 'ERROR_HANDLING'
            and other_machine.state == 'ERROR_HANDLING'
        ):
            machine.to_HO_UNAVBL()
            other_machine.to_HO_UNAVBL()

    def _handle_not_ready_to_available(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from NOT_READY to AVAILABLE state"""
        machine = self._get_machine(port_id)
        valid = self.signal_manager.get_signal('VALID')

        if not valid:  # Only recover if no handshake is active
            if machine.state == 'IDLE_UNAVBL':
                machine.idle_unavbl_return_idle()
            elif machine.state == 'HO_UNAVBL':
                machine.ho_avbl_return_idle()

    def _handle_not_ready_to_error(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from NOT_READY to ERROR state"""
        machine = self._get_machine(port_id)
        if machine.state == 'IDLE_UNAVBL':
            machine.to_ERROR_HANDLING()

    def _handle_not_ready_to_ho_off(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from NOT_READY to HO_OFF state"""
        machine = self._get_machine(port_id)
        other_machine = self._get_machine(1 - port_id)

        if machine.state == 'IDLE_UNAVBL' and other_machine.state == 'IDLE_UNAVBL':
            machine.to_HO_UNAVBL()
            other_machine.to_HO_UNAVBL()

    def _handle_available_to_error(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from AVAILABLE to ERROR state"""
        machine = self._get_machine(port_id)
        self._get_machine(1 - port_id)
        valid = self.signal_manager.get_signal('VALID')

        if not valid:
            machine.to_ERROR_HANDLING()

    def _handle_available_to_not_ready(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from AVAILABLE to NOT_READY state"""
        machine = self._get_machine(port_id)

        if machine.state != 'IDLE':
            return None
        else:
            machine.to_IDLE_UNAVBL()

    def _handle_available_to_ho_off(
        self, port_id: int, old: PortCondition, new: PortCondition
    ) -> None:
        """Handle transition from AVAILABLE to HO_OFF state"""
        valid = self.signal_manager.get_signal('VALID')
        machine = self._get_machine(port_id)

        if valid and self._is_active_port(port_id):
            # Active handshake - go to HO_UNAVBL
            machine.to_HO_UNAVBL()
        if not valid and machine.load_port.error_active:
            # No active handshake - go to HO_UNAVBL
            machine.to_HO_UNAVBL()

    # -------------------------------------------------------------------------
    #  Methods to handle the end of a handshake and check for any error conditions
    #  Only triggered when VALID signal goes from True to False
    # -------------------------------------------------------------------------

    # ----------------------
    # Helper Methods
    # ----------------------

    def _get_machine(self, port_id: int) -> E84StateMachine:
        """Get state machine for given port ID"""
        return self.controller.lpt_0 if port_id == 0 else self.controller.lpt_1

    def _is_active_port(self, port_id: int) -> bool:
        """Check if this is the currently active port"""
        return (
            self.controller.selected_port_index == port_id
            and self.controller.selected_machine is not None
        )
