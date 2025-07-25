# state_machine.py


import datetime
from dataclasses import dataclass, field
from typing import Any, List

from loguru import logger
from transitions import EventData, Machine
from transitions.extensions.states import Tags, Timeout, add_state_features

from config_states_transitions import STATES, TRANSITIONS
from constants import TIMEOUTS
from load_port import LoadPort, PortStatus
from signal_manager import SignalManager


@dataclass
class StateTransitionRecord:
    timestamp: datetime
    port_id: str
    old_state: str
    new_state: str
    trigger: str
    signal_snapshot: List[tuple[str, bool]] = field(default_factory=list)


@add_state_features(Tags, Timeout)
class E84BaseMachine(Machine):
    """Enhanced state machine with added state tags and timeout feature. Initialized below in E84Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    pass


class E84StateMachine:
    def __init__(
        self,
        signal_manager: SignalManager,
        load_port: LoadPort,
    ):
        self.signal_manager: SignalManager = signal_manager
        self.load_port: LoadPort = load_port

        self._operation_type: str | None = None
        self._error_active: bool = self.load_port.get_port_status().error_active
        self.error_context: dict[str, Any] | None = None
        self.transition_records: list[StateTransitionRecord] = []

        try:
            self.machine: Machine = E84BaseMachine(
                model=self,
                states=STATES,
                transitions=TRANSITIONS,
                initial='IDLE',
                send_event=True,
                after_state_change='log_state_transition',
                ignore_invalid_triggers=False,
            )
            logger.info(f'State machine initialized for Port {load_port.port_id}')

        except Exception as e:
            logger.error(f'Failed to initialize State Machine: {e}')

    def __str__(self) -> str:
        return f'State Machine for Port {self.load_port.port_id}'

    def log_state_transition(self, event: EventData):
        """Log state transition events."""
        port_status: PortStatus = self.load_port.get_port_status()
        record: StateTransitionRecord = self.record_transition_context(event)

        logger.debug(f'Operation: {self._operation_type} | {port_status}')

        if event:
            msg = f"[Port {self.load_port.port_id}] State change: {record.old_state} -> {record.new_state}, [Trigger]: '{record.trigger}'"

            logger.info(msg)
            logger.debug(f'Signal snapshot: {record.signal_snapshot}')

        else:
            logger.info('State transition occurred without event data')

    def record_transition_context(self, event: EventData):
        record = StateTransitionRecord(
            timestamp=datetime.datetime.now(),
            port_id=f'lpt_{self.load_port.port_id}',
            old_state=event.transition.source,
            new_state=event.transition.dest,
            trigger=event.event.name,
            signal_snapshot=self.signal_manager.signal_snapshot(),
        )
        self.transition_records.append(record)

        return record

    # def trigger_with_logging(self, trigger_name):
    #     """Custom trigger method to log failed triggers with traceback info using loguru."""
    #     trigger = trigger_name

    #     try:
    #         if not self.machine._get_trigger(self, trigger):
    #             # Get caller's information
    #             frame = inspect.currentframe().f_back
    #             filename = frame.f_code.co_filename
    #             line_number = frame.f_lineno
    #             function_name = frame.f_code.co_name

    #             # Capture traceback details
    #             tb_details = traceback.format_exc()  # Gets full traceback if an error occurs

    #             # Loguru log with structured metadata and full traceback
    #             logger.warning(
    #                 "❌ Trigger '{trigger}' failed at {file}, line {line} in function '{func}'.\nTraceback:\n{trace}",
    #                 trigger=trigger_name,
    #                 file=filename,
    #                 line=line_number,
    #                 func=function_name,
    #                 trace=tb_details if "NoneType: None" not in tb_details else "No exception, just condition failure.",
    #             )
    #     except Exception as e:
    #         # Log unexpected errors that might occur
    #         logger.exception("🔥 Unexpected error while processing trigger '{}':", trigger_name)
    #         logger.exception(e)

    # --------------------------------------------------------------------------
    # Helper Methods for Unavailable/Error Transitions
    # --------------------------------------------------------------------------

    def set_unavailable(self):
        """
        Transition to an unavailable state if not already in one.
        This is used by interrupt callbacks when the port becomes unavailable.
        """
        ready = self.signal_manager.get_signal(f'LPT_READY_{self.load_port.port_id}')
        error = self.signal_manager.get_signal(f'LPT_ERROR_{self.load_port.port_id}')

        if (
            self.state not in ['HO_UNAVBL', 'IDLE_UNAVBL']
            and not self.load_port.ready_and_error_clear
        ):
            if ready:
                self.to_IDLE_UNAVBL()
                logger.info(
                    f'[Port {self.load_port.port_id}] set to unavailable (state: {self.state}).'
                )
            if error:
                self.to_ERROR_HANDLING()
                logger.info(
                    f'[Port {self.load_port.port_id}] set to error (state: {self.state}).'
                )

    def recover_from_unavailable(self):
        """
        Recover from an unavailable state back to IDLE.
        This can be called when the hardware signals indicate the port is ready again.
        """
        port_status = self.load_port.get_port_status()

        if self.state == 'HO_UNAVBL':
            if port_status.lpt_ready is True and port_status.error_active is True:
                self.to_ERROR_HANDLING()
            elif self.load_port.ready_and_error_clear:
                self.ho_avbl_return_idle()
            elif not port_status.lpt_ready:
                self.to_IDLE_UNAVBL()
            logger.info(
                f'[Port {self.load_port.port_id}] recovered from HO_UNAVBL state.'
            )

        if self.state == 'IDLE_UNAVBL':
            self.idle_unavbl_return_idle()
            logger.info(
                f'[Port {self.load_port.port_id}] recovered from IDLE_UNAVBL state to IDLE.'
            )

    def recover_from_error(self):
        port_status = self.load_port.get_port_status()

        if self.state == 'HO_UNAVBL':
            if port_status.lpt_ready is True and port_status.error_active is True:
                self.to_ERROR_HANDLING()
                logger.info(
                    f'[Port {self.load_port.port_id}] recovered from ERROR_HANDLING state.'
                )
            if port_status.lpt_ready is False and port_status.error_active is False:
                self.to_IDLE_UNAVBL()
                logger.info(
                    f'[Port {self.load_port.port_id}] recovered from ERROR_HANDLING state to IDLE_UNAVBL.'
                )
        if self.state == 'ERROR_HANDLING':
            if port_status.lpt_ready is True and port_status.error_active is False:
                self.attempt_recovery()
                logger.info(
                    f'[Port {self.load_port.port_id}] recovered from ERROR_HANDLING state to IDLE.'
                )

            if port_status.lpt_ready is False and port_status.error_active is False:
                self.to_IDLE_UNAVBL()
                logger.info(
                    f'[Port {self.load_port.port_id}] recovered from ERROR_HANDLING state to IDLE_UNAVBL.'
                )

    def try_ready_trigger(self):
        """
        Attempts to trigger the ready_for_transfer method of the selected_machine if it is in the "TR_REQ_ON" state.
        """
        if self.state == 'TR_REQ_ON':
            self.ready_for_transfer()

    ##################################################
    #    Condition Methods:
    #    Return True if the transition should proceed; otherwise False.
    ##################################################

    def can_start_handshake(self, event=None) -> bool:
        """Validate if conditions are correct to start the handshake."""

        port_status = self.load_port.get_port_status()
        # if any other AGV signals are True except for valid and CS_0 or CS_1 then return false
        # else return True
        agv_signals = ['CS_0', 'CS_1', 'VALID', 'TR_REQ', 'BUSY', 'COMPT']
        agv_signal_values = [
            self.signal_manager.get_signal(signal) for signal in agv_signals
        ]
        extra_signals_on = any(
            signal_value and signal_name not in ['CS_0', 'CS_1', 'VALID']
            for signal_value, signal_name in zip(agv_signal_values, agv_signals)
        )

        try:
            logger.info(port_status)
            if extra_signals_on:
                return False
            else:
                return self.load_port.is_ho_avbl()
        except Exception as e:
            logger.error(e)

    def validate_tr_req(self, event=None) -> bool:
        cs0: bool = self.signal_manager.get_signal('CS_0')
        cs1 = self.signal_manager.get_signal('CS_1')
        cs_valid = cs0 or cs1
        valid: bool = self.signal_manager.get_signal('VALID')
        tr_req: bool = self.signal_manager.get_signal('TR_REQ')

        return cs_valid and valid and tr_req

    def validate_ready(self, event=None) -> bool:
        """Validate lpt is ready for transfer before turnin on READY signal."""
        return self.load_port.ready_and_error_clear

    def validate_busy_conditions(self, event=None) -> bool:
        """Validate if conditions are correct to enter BUSY state."""
        cs0: bool = self.signal_manager.get_signal('CS_0')
        cs1 = self.signal_manager.get_signal('CS_1')
        cs_valid = cs0 or cs1
        valid: bool = self.signal_manager.get_signal('VALID')
        tr_req: bool = self.signal_manager.get_signal('TR_REQ')
        busy: bool = self.signal_manager.get_signal('BUSY')

        return cs_valid and valid and tr_req and busy

    def validate_carrier_detected(self, event=None) -> bool:
        op_type = self._operation_type
        carrier = self.signal_manager.get_signal(
            f'CARRIER_PRESENT_{self.load_port.port_id}'
        )

        if op_type is None:
            return False
        elif op_type == 'UNLOAD':
            return not carrier
        elif self._operation_type == 'LOAD':
            return carrier
        return False

    def transfer_complete(self, event=None) -> bool:
        busy: bool = self.signal_manager.get_signal('BUSY')
        tr_req: bool = self.signal_manager.get_signal('TR_REQ')
        compt: bool = self.signal_manager.get_signal('COMPT')

        return compt and not busy and not tr_req

    def validate_valid_off(self, event=None) -> bool:
        valid: bool = self.signal_manager.get_signal('VALID')

        return not valid

    ##################################################
    #    On Enter Callback Methods
    ##################################################

    def _on_enter_idle(self, event=None):
        self._operation_type = None
        self.transition_records = []

        self.signal_manager.set_signal('U_REQ', False)
        self.signal_manager.set_signal('L_REQ', False)
        self.signal_manager.set_signal('READY', False)

        logger.info(f'[Port {self.load_port.port_id}] to state: IDLE')

    def _on_enter_handshake_initiated(self, event=None):
        port_status: dict[str, bool] = self.load_port.get_port_status()

        logger.debug(port_status)
        logger.info(f'[PORT {self.load_port.port_id}] to state: HANDSHAKE_INITIATED')

        if self.load_port.load_ready:
            self.signal_manager.set_signal('L_REQ', True)
            self.signal_manager.set_signal('U_REQ', False)
            self._operation_type = 'LOAD'

        elif self.load_port.unload_ready:
            self.signal_manager.set_signal('U_REQ', True)
            self.signal_manager.set_signal('L_REQ', False)
            self._operation_type = 'UNLOAD'

    def _on_enter_tr_req(self, event=None):
        self.ready_for_transfer()
        logger.info(f'[PORT {self.load_port.port_id}] to state: TR_REQ_ON')

    def _on_enter_transfer_ready(self, event=None):
        self.signal_manager.set_signal('READY', True)
        logger.info('READY = ON')
        logger.info(f'[PORT {self.load_port.port_id}] to state: TRANSFER_READY')

    def _on_enter_busy(self, event=None):
        logger.info(f'[PORT {self.load_port.port_id}] to state: BUSY')

    def _on_enter_carrier_detected(self, event=None):
        """Handle entry to transfer_CARRIER state."""
        port_status: PortStatus = self.load_port.get_port_status()
        carrier_present: bool = port_status.carrier_present
        latch: bool = port_status.latch_locked
        error: bool = port_status.error_active

        logger.info(f'[PORT {self.load_port.port_id}] to state: CARRIER_DETECTED')

        logger.debug(
            f'Validating if READY for XFER: Port: CS_{self.load_port.port_id}, Carrier: {carrier_present}, Latch Locked: {latch}, Error: {error}'
        )

    def _on_enter_transfer_complete(self, event=None):
        """Handle entry to transfer_COMPLETE state."""
        self.signal_manager.set_signal('READY', False)

        logger.info('READY = OFF')
        logger.info(f'[PORT {self.load_port.port_id}] to state: TRANSFER_COMPLETE')

    ##################################################
    # Timeout Handlers
    ##################################################

    def _handle_timeout(self, event=None):
        if self.state == 'HANDSHAKE_INITIATED':
            logger.error(
                f'TP1 Timeout – TR_REQ signal did not turn ON within specified time. (TP1 = {TIMEOUTS.TP1.value}s)'
            )
        if self.state == 'TRANSFER_READY':
            logger.error(
                f'TP2 Timeout – BUSY signal did not turn ON within specified time. (TP3 = {TIMEOUTS.TP2.value}s)'
            )
        if self.state == 'BUSY':
            logger.error(
                f'TP3 Timeout – Carrier not detected/removed within specified time. (TP3 = {TIMEOUTS.TP3.value}s)'
            )
        if self.state == 'CARRIER_DETECTED':
            logger.error(
                f'TP4 Timeout – BUSY signal did not turn OFF within specified time. (TP4 = {TIMEOUTS.TP4.value}s)'
            )
        if self.state == 'TRANSFER_COMPLETE':
            logger.error(
                f'TP5 Timeout – VALID signal did not turn OFF within specified time. (TP5 = {TIMEOUTS.TP5.value}s)'
            )
        self.to_TIMEOUT()

    def _handle_tr_req_timeout(self, event=None):
        """Handle TR_REQ timeout"""
        logger.error(
            f'TP1 Timeout – TR_REQ signal did not turn ON within specified time. (TP1 = {TIMEOUTS.TP1.value}s)'
        )
        self.to_ERROR_HANDLING()

    def _handle_busy_timeout(self, event=None):
        """Handle BUSY timeout"""
        logger.error(
            f'TP2 Timeout – BUSY signal did not turn ON within specified time. (TP2 = {TIMEOUTS.TP2.value}s)'
        )
        self.to_ERROR_HANDLING()

    def _handle_transfer_timeout(self, event=None):
        """Handle transfer timeout"""
        logger.error(
            f'TP3 Timeout – Carrier not detected/removed within specified time. (TP3 = {TIMEOUTS.TP3.value}s)'
        )
        self.to_ERROR_HANDLING()

    def _handle_carrier_timeout(self, event=None):
        """Handle carrier detection timeout"""
        logger.error(
            f'TP4 Timeout – BUSY signal did not turn OFF within specified time. (TP4 = {TIMEOUTS.TP4.value}s)'
        )
        self.to_ERROR_HANDLING()

    def _handle_valid_off_timeout(self, event=None):
        """Handle carrier detection timeout"""
        logger.error(
            f'TP5 Timeout – VALID signal did not turn OFF within specified time. (TP5 = {TIMEOUTS.TP5.value}s)'
        )
        self.to_ERROR_HANDLING()

    ##################################################
    #   UNAVBL & ERROR STATE LOGIC
    ##################################################

    # ------------------------------
    #   Condition Methods
    # ------------------------------
    def should_transition_idle_unavbl(self, event=None) -> bool:
        """
        If in state IDLE, and LPT is not ready:
        then transition to IDLE -> IDLE_UNAVBL.
        """
        lpt_ready = self.signal_manager.get_signal(
            f'LPT_READY_{self.load_port.port_id}'
        )

        return not lpt_ready

    def can_auto_recover(self, event=None) -> bool:
        """
        Determine if the state machine can automatically recover from
        a HO_UNAVBL or IDLE_UNAVBL state.
        """
        ready = self.signal_manager.get_signal(f'LPT_READY_{self.load_port.port_id}')
        error = self.signal_manager.get_signal(f'LPT_ERROR_{self.load_port.port_id}')
        valid = self.signal_manager.get_signal('VALID')

        if self._operation_type is None:
            if self.state in ['HO_UNAVBL', 'IDLE_UNAVBL']:
                return ready and not error
            if self.state == 'ERROR_HANDLING':
                return not error and ready
            if self.state == 'HO_UNAVBL':
                return ready and not valid and not error
        else:
            if self.state in ['HO_UNAVBL', 'IDLE_UNAVBL']:
                return ready and not valid
            if self.state == 'ERROR_HANDLING':
                return not error and ready and not valid

    def can_return_to_idle(self, event=None) -> bool:
        lpt_ready = self.signal_manager.get_signal(
            f'LPT_READY_{self.load_port.port_id}'
        )
        lpt_error = self.signal_manager.get_signal(
            f'LPT_ERROR_{self.load_port.port_id}'
        )

        return lpt_ready and not lpt_error

    # ------------------------------
    #   On Enter Callback Methods
    # ------------------------------
    def _on_enter_idle_unavbl(self, event=None):
        self.signal_manager.set_signal('U_REQ', False)
        self.signal_manager.set_signal('L_REQ', False)
        self.signal_manager.set_signal('READY', False)
        logger.warning(f'[PORT {self.load_port.port_id}] to state: IDLE_UNAVBL')

    def _on_enter_ho_unavbl(self, event=None):
        "Enters state when HO_AVBL signal is False."
        self.signal_manager.set_signal('HO_AVBL', False)

        logger.error(
            f'LPT_{self.load_port.port_id} to state: HO_UNAVBL | Handoff exception occured.'
        )

    def _on_enter_error_handling(self, event=None):
        """
        Turns off signals.

        This function is called when the state machine enters the ERROR_HANDLING state.
        It sets the READY, L_REQ, and U_REQ signals to False.
        """
        self.signal_manager.set_signal('READY', False)
        self.signal_manager.set_signal('L_REQ', False)
        self.signal_manager.set_signal('U_REQ', False)
        logger.warning(
            f'LOAD-PORT ERROR: [PORT {self.load_port.port_id}] | Current Operation: {self._operation_type}'
        )

    def _on_enter_timeout(self, event=None):
        self.signal_manager.set_signal('READY', False)
        self.signal_manager.set_signal('L_REQ', False)
        self.signal_manager.set_signal('U_REQ', False)
        # self.signal_manager.set_signal('HO_AVBL', False)
        logger.error(
            f'TIMEOUT ERROR: [PORT {self.load_port.port_id}] | Current Operation: {self._operation_type}'
        )

    def _on_enter_reset(self, event=None):
        self.signal_manager.reset_passive_signals()
        logger.info(f'[Port {self.load_port.port_id}] reset to IDLE')

    # ------------------------------
    #   Helper Methods
    # ------------------------------

    def handle_error(
        self,
        error_code: str | None = None,
        message: str | None = None,
        context: dict[str, Any] | None = None,
        event: str | None = None,
    ):
        """
        Handles the error by calling the `handle_error` method of the `error_handler` object.

        Args:
            error_code (Optional[str]): The error code.
            message (Optional[str]): The error message.
            context (Optional[Dict[str, Any]]): The error context.
        """
        if not self.error_handler:
            raise RuntimeError('Error handler not available.')
        if not self.load_port:
            raise RuntimeError('Load port not available.')

        self.error_handler.handle_error(
            error_code,
            self.load_port.port_id,
            self.state,
        )

        if self.state and self.state != 'ERROR_HANDLING':
            self.to_ERROR_HANDLING()
