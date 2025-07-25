# e84_controller.py

from typing import Dict, List, Optional, Tuple

from loguru import logger

from callback_manager import CallbackManager
from load_port import PortStatus
from load_port_factory import LoadPortFactory
from port_states import ErrorTransitionHandler, PortCondition
from signal_manager import SignalManager
from state_machine import E84StateMachine


class E84Controller:
    """
    E84Controller class
    --------------------

    This class is responsible for managing the state machines and signals of the
    two load ports in an E84 system.

    It initializes the load ports, and registers callbacks for handling signal
    changes.

    The main functionality of the class is:

    - Initialization of the load ports
    - Selection of the active load port based on the CS signals
    - Full reset of all load ports to default state
    - Polling cycle for handshake-related signals and state transitions

    The class uses the `logging` and `signals` modules to handle logging and
    signal management.

    It also uses the `transitions` module to handle state transitions.

    The class has several methods to handle different types of signal changes
    and to trigger state transitions.

    The `E84Controller` class is the main entry point to the E84 controller
    functionality.
    """

    def __init__(
        self,
        signal_manager: SignalManager,
        config_file: str = None,
        interface_type: str = None,
        operating_mode: str = 'prod',
        **kwargs,
    ) -> None:
        """
        Initialize the E84Controller.

        Args:
            signal_manager: The SignalManager instance
            config_file: Path to configuration file for load port settings
            interface_type: Optional interface type override (parallel or ascii)
            **kwargs: Additional parameters to pass to LoadPort implementations
        """
        # Store the signal manager
        self.signal_manager = signal_manager
        self.callback_manager = CallbackManager()
        self.error_handler = ErrorTransitionHandler(self, self.signal_manager)

        # Store operating mode
        self.operating_mode = operating_mode
        logger.info(f'E84Controller initializing in {operating_mode} mode')

        # Flags
        self.selected_machine: Optional[E84StateMachine | None] = None
        self.selected_port_index: Optional[int | None] = None
        self.previous_selected_machine: Optional[int | None] = None
        self.port_0_status: List[PortStatus] = []
        self.port_1_status: List[PortStatus] = []

        # Initialize load ports using the factory
        self.lpt_0, self.lpt_1 = self._initialize_load_ports(
            config_file=config_file,
            interface_type=interface_type,
            operating_mode=operating_mode,
            **kwargs,
        )

        # Method binding following transitions library pattern
        self.lpt_0.machine.model.is_globally_unavailable = (
            self.check_global_unavailable.__get__(
                self.lpt_0.machine.model, self.lpt_0.machine.model.__class__
            )
        )

        self.lpt_1.machine.model.is_globally_unavailable = (
            self.check_global_unavailable.__get__(
                self.lpt_1.machine.model, self.lpt_1.machine.model.__class__
            )
        )

        # Initialize signals and register callbacks
        self._initialize_signals()
        self._register_callbacks()

        logger.info(f'E84 Controller initialized in {operating_mode} mode')
        logger.debug(f'{self.signal_manager.signal_snapshot()}')
        logger.warning(f'self.selected_machine: {self.selected_machine}')

    def _initialize_load_ports(
        self, config_file=None, interface_type=None, operating_mode='prod', **kwargs
    ) -> Tuple[E84StateMachine, E84StateMachine]:
        """
        Initialize the load ports using the factory.

        Args:
            config_file: Path to configuration file
            interface_type: Optional interface type override
            **kwargs: Additional parameters to pass to load port implementations

        Returns:
            Tuple of E84StateMachine instances for both load ports
        """
        # Create load ports using the factory
        load_port_0 = LoadPortFactory.create_load_port(
            port_id=0,
            signal_manager=self.signal_manager,
            config_file=config_file,
            interface_type=interface_type,
            operating_mode=operating_mode,
            **kwargs,
        )

        load_port_1 = LoadPortFactory.create_load_port(
            port_id=1,
            signal_manager=self.signal_manager,
            config_file=config_file,
            interface_type=interface_type,
            operating_mode=operating_mode,
            **kwargs,
        )

        lpt_0 = E84StateMachine(
            signal_manager=self.signal_manager,
            load_port=load_port_0,
        )

        lpt_1 = E84StateMachine(
            signal_manager=self.signal_manager,
            load_port=load_port_1,
        )

        self.port_0_status.append(load_port_0.get_port_status_record())
        self.port_1_status.append(load_port_1.get_port_status_record())

        logger.debug(f'Port_0 status: {self.port_0_status}')
        logger.debug(f'Port_1 status: {self.port_1_status}')

        return lpt_0, lpt_1

    # Add helper methods to check the current mode
    def is_production_mode(self):
        """Return True if operating in production mode"""
        return self.operating_mode.lower() == 'production'

    def is_emulation_mode(self):
        """Return True if operating in emulation mode"""
        return self.operating_mode.lower() == 'emulation'

    def is_simulation_mode(self):
        """Return True if operating in simulation mode"""
        return self.operating_mode.lower() == 'simulation'

    def _initialize_signals(self) -> None:
        """Initialize E84 passive signals."""
        self.signal_manager.set_signal('HO_AVBL', True)
        self.signal_manager.set_signal('ES', True)
        self.signal_manager.set_signal('L_REQ', False)
        self.signal_manager.set_signal('U_REQ', False)
        self.signal_manager.set_signal('READY', False)

    def _register_callbacks(self) -> None:
        """Register all necessary callbacks"""
        # Register E84 signal callbacks
        e84_callbacks = {
            'LPT_READY_0': lambda signal, new, old: self._handle_port_signal_change(
                0, signal, new, old
            ),
            'LPT_READY_1': lambda signal, new, old: self._handle_port_signal_change(
                1, signal, new, old
            ),
            'LPT_ERROR_0': lambda signal, new, old,: self._handle_port_signal_change(
                0, signal, new, old
            ),
            'LPT_ERROR_1': lambda signal, new, old: self._handle_port_signal_change(
                1, signal, new, old
            ),
            'CARRIER_PRESENT_0': lambda old, new, port_id=0: self._on_carrier_changed(
                port_id, new
            ),
            'CARRIER_PRESENT_1': lambda old, new, port_id=1: self._on_carrier_changed(
                port_id, new
            ),
            'ES': self._handle_es_change,
            'VALID': self._handle_valid_change,
            'TR_REQ': self.poll_cycle,
            'BUSY': self.poll_cycle,
            'COMPT': self.poll_cycle,
        }

        for signal, callback in e84_callbacks.items():
            if not callable(callback):
                raise ValueError(f'{callback} is not callable')
            self.signal_manager.add_watcher(signal, callback)

    def _on_carrier_changed(self, port_id: int, carrier: bool) -> None:
        """Handle CARRIER_PRESENT signal changes"""
        try:
            if self.selected_machine is None:
                logger.info(
                    f'Carrier changed on port {port_id}, carrier={carrier}, machine state={self.selected_machine.state if self.selected_machine is not None else None}'
                )
                return
            if self.selected_machine.state == 'BUSY':
                self.selected_machine.carrier_detected_event()
        except Exception as e:
            logger.error(f'Error in _on_carrier_changed: {e}')

    def check_global_unavailable(self, event=None) -> bool:
        """
        Check if both ports are in a condition that requires HO_UNAVBL state.
        """
        LPT_ERROR_0 = self.signal_manager.get_signal('LPT_ERROR_0')
        LPT_ERROR_1 = self.signal_manager.get_signal('LPT_ERROR_1')
        LPT_READY_0 = self.signal_manager.get_signal('LPT_READY_0')
        LPT_READY_1 = self.signal_manager.get_signal('LPT_READY_1')

        if (LPT_ERROR_0 or not LPT_READY_0) and (LPT_ERROR_1 or not LPT_READY_1):
            self.signal_manager.set_signal('HO_AVBL', False)
            return True

        else:
            self.signal_manager.set_signal('HO_AVBL', True)
            return False

    def _handle_port_signal_change(
        self, port_id: int, signal_name: str, new_value: bool, old_value: bool
    ) -> None:
        """
        Handle any port signal change
        Error transitions are delegated to ErrorTransitionHandler
        """
        # Only monitor changes during active handshake
        valid = self.signal_manager.get_signal('VALID')
        if valid:
            # For active handshakes, we still need to capture conditions
            old_condition = self._get_old_condition(
                port_id, signal_name, new_value, old_value
            )
            new_condition = self._create_new_condition(
                port_id, old_condition, signal_name, new_value, old_value
            )

            # Log the change for debugging
            logger.debug(
                f'Port {port_id} signal change during handshake: {signal_name} = {new_value}'
            )

            # Only handle signal changes during handshake here
            # All other changes are handled by ErrorTransitionHandler
            self.error_handler.handle_signal_change(
                port_id, old_condition, new_condition
            )

    def _get_old_condition(
        self,
        port_id: int = None,
        signal_name: str = None,
        new_value: bool = None,
        old_value: bool = None,
    ):
        """Get current port condition"""
        # Create a snapshot of all relevant signals
        signal_values = {
            f'LPT_READY_{port_id}': self.signal_manager.get_signal(
                f'LPT_READY_{port_id}'
            ),
            f'LPT_ERROR_{port_id}': self.signal_manager.get_signal(
                f'LPT_ERROR_{port_id}'
            ),
            f'CARRIER_PRESENT_{port_id}': self.signal_manager.get_signal(
                f'CARRIER_PRESENT_{port_id}'
            ),
            'VALID': self.signal_manager.get_signal('VALID'),
            'HO_AVBL': self.signal_manager.get_signal('HO_AVBL'),
            'ES': self.signal_manager.get_signal('ES'),
        }

        if signal_name is not None and old_value is not None:
            signal_values[f'{signal_name}'] = old_value

        # Convert signal values to PortCondition parameters
        port_cond = PortCondition(
            port_id=port_id,
            lpt_ready=signal_values[f'LPT_READY_{port_id}'],
            lpt_error=signal_values[f'LPT_ERROR_{port_id}'],
            carrier_present=signal_values[f'CARRIER_PRESENT_{port_id}'],
            valid=signal_values['VALID'],
            ho_avbl=signal_values['HO_AVBL'],
        )

        if signal_name is not None:
            signal_values[f'{signal_name}_{port_id}'] = old_value

        return port_cond

    def _create_new_condition(
        self,
        port_id: int,
        old_condition: PortCondition,
        signal_name: str,
        new_value: bool,
        old_value: bool,
    ) -> PortCondition:
        """
        Create a new condition based on signal change.
        """
        # Match the exact parameter names from PortCondition class
        lpt_ready = (
            new_value
            if signal_name == f'LPT_READY_{port_id}'
            else old_condition.lpt_ready
        )
        lpt_error = (
            new_value
            if signal_name == f'LPT_ERROR_{port_id}'
            else old_condition.lpt_error
        )
        carrier_present = (
            new_value
            if signal_name == f'CARRIER_PRESENT_{port_id}'
            else old_condition.carrier_present
        )

        return PortCondition(
            port_id=port_id,
            lpt_ready=lpt_ready,
            lpt_error=lpt_error,
            carrier_present=carrier_present,
            valid=self.signal_manager.get_signal('VALID'),
            ho_avbl=self.signal_manager.get_signal('HO_AVBL'),
        )

    # ---------------------------
    # Interrupt Callbacks for Error/Unavailable Conditions
    # ---------------------------

    def _handle_valid_change(
        self, signal_name: str, new_val: bool, old_val: bool
    ) -> None:
        """Handle changes to the VALID signal."""
        logger.debug(f'VALID changed from {old_val} to {new_val}.')

        if new_val:  # VALID turned ON
            logger.debug('VALID is now ON, selecting port and initiating handshake.')
            self.selected_machine = self.select_port()
        if new_val is False:
            self.signal_manager.set_signal('HO_AVBL', True)
        # Note: VALID turned OFF is handled by ErrorTransitionHandler

        self.poll_cycle()

    # def _handle_valid_change(
    #     self, signal_name: str, new_val: bool, old_val: bool
    # ) -> None:
    #     """Handle changes to the VALID signal."""
    #     self.selected_machine = self.select_port()
    #     can_start_handshake = (
    #         self.selected_machine.can_start_handshake()
    #         if self.selected_machine
    #         else False
    #     )

    #     logger.debug(f'VALID changed from {old_val} to {new_val}.')

    #     if new_val is False:
    #         # Just handle the TRANSFER_COMPLETED case here
    #         machine = self.selected_machine if self.selected_machine else None
    #         self.signal_manager.set_signal('HO_AVBL', True)
    #         if machine is not None and machine.state == 'TRANSFER_COMPLETED':
    #             logger.debug(
    #                 'VALID is off and machine is in TRANSFER_COMPLETED; triggering transfer_completed transition.'
    #             )
    #             machine.transfer_completed()
    #             self.selected_machine = None
    #     if new_val is True:
    #         if can_start_handshake is False:
    #             logger.warning(
    #                 f'VALID ON but machine cannot start handshake; returning to IDLE. Selected machine: {self.selected_machine}'
    #             )
    #             self.selected_machine = None
    #         else:
    #             logger.debug(
    #                 'VALID is now ON, selecting port and initiating handshake.'
    #             )
    #     self.poll_cycle()

    def _handle_es_change(self, new_val: bool, old_val: bool) -> None:
        """Handle ES signal changes"""
        pass

    # ---------------------------
    # Load Port Callback Methods
    # ---------------------------

    def select_port(self) -> Optional[E84StateMachine]:
        """
        Selects the appropriate port based on the CS signals.

        Returns:
            Optional[E84StateMachine]: The selected E84StateMachine, or None if no port is selected.
        """
        ho_avbl = self.signal_manager.get_signal('HO_AVBL')
        is_cs_0_active = self.signal_manager.get_signal('CS_0')
        is_cs_1_active = self.signal_manager.get_signal('CS_1')

        if is_cs_0_active and is_cs_1_active:
            self.selected_machine = None
            return None

        if is_cs_0_active:
            self.selected_machine = self.lpt_0

        elif is_cs_1_active:
            self.selected_machine = self.lpt_1

        else:
            self.selected_machine = None

        if self.selected_machine:
            is_ready = self.selected_machine.load_port.is_ho_avbl()
            if is_ready != ho_avbl:
                self.selected_machine.to_HO_UNAVBL()

        return self.selected_machine

    def full_reset(self) -> None:
        """Reset all load ports to default state."""
        # Create a dictionary for quick access to the load ports.
        logger.debug(
            'Resetting all load ports, and Signal Manager signals to default state.'
        )
        lpt_dict: Dict[int, E84StateMachine] = {0: self.lpt_0, 1: self.lpt_1}

        for _, machine in lpt_dict.items():
            machine.load_port.reset()
            machine.reset()

        self.signal_manager.reset_signal_manager()

        # ---------------------------
        # Polling Cycle (Handshake Path)
        # ---------------------------

    def poll_cycle(self, *args, **kwargs) -> None:
        """
        Poll only handshake-related signals and trigger state transitions
        for the active (engaged) state machine.
        This method ignores error/unavailable conditions.
        """
        valid = self.signal_manager.get_signal('VALID')

        if not valid or self.selected_machine is None:
            return

        machine = self.selected_machine
        # Mapping from current handshake state to corresponding action.
        handshake_transitions = {
            'IDLE': lambda m: m.start_handshake(),
            'HANDSHAKE_INITIATED': lambda m: m.tr_req_received()
            if self.signal_manager.get_signal('TR_REQ')
            else None,
            'TR_REQ_ON': lambda m: m.ready_for_transfer()
            if self.signal_manager.get_signal('READY')
            else None,
            'TRANSFER_READY': lambda m: m.busy_on()
            if self.signal_manager.get_signal('BUSY')
            else None,
            'BUSY': lambda m: m.carrier_detected_event()
            if self.selected_machine.validate_carrier_detected()
            else None,
            'CARRIER_DETECTED': lambda m: m.transfer_done()
            if self.signal_manager.get_signal('COMPT')
            else None,
            'TRANSFER_COMPLETED': lambda m: m.validate_valid_off(),
        }

        current_state = machine.state
        action = handshake_transitions.get(current_state)
        if action:
            action(machine)

        previous_state = getattr(self, 'previous_state', None)
        previous_status = getattr(self, 'previous_status', None)
        current_status = machine.load_port.get_port_status()

        if current_state != previous_state or current_status != previous_status:
            logger.debug(
                f'Poll cycle: Port {machine.load_port.port_id} | STATE: {machine.state} | Status: {machine.load_port.get_port_status()}'
            )
            self.previous_state = current_state
            self.previous_status = current_status
