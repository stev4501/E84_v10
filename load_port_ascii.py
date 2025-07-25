# load_port_ascii.py

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

import serial
from loguru import logger

from signal_manager import SignalManager


class LPTSignals(Enum):
    """
    ASCII interface signals from LPT2200 manual.

    CARRIER_PRESENT: Active when a SMIF-Pod is physically located on the LPT's port plate.
    LATCH_LOCKED: Active when the hold-down latches on the port are extended.
    LPT_READY: Active when LPT is in Home position and Auto Mode is enabled.
    LPT_ERROR: Active when the LPT has encountered an abnormal condition.
    """

    CARRIER_PRESENT = auto()
    LATCH_LOCKED = auto()
    LPT_READY = auto()
    LPT_ERROR = auto()


@dataclass
class PortStatus:
    """Represents the physical state of a specific port"""

    port_id: int
    carrier_present: bool
    latch_locked: bool
    lpt_ready: bool
    error_active: bool

    @property
    def is_ready_for_load(self) -> bool:
        return (
            not self.carrier_present
            and not self.latch_locked
            and not self.error_active
            and self.lpt_ready
        )

    @property
    def is_ready_for_unload(self) -> bool:
        return (
            self.carrier_present
            and not self.latch_locked
            and not self.error_active
            and self.lpt_ready
        )

    def __str__(self) -> str:
        return (
            f'LPT_{self.port_id} | '
            f'Carrier: {"Present" if self.carrier_present else "Not Present"} | '
            f'Latch: {"Locked" if self.latch_locked else "Unlocked"} | '
            f'Error: {"Active" if self.error_active else "None"} | '
            f'LPT Ready: {"Yes" if self.lpt_ready else "No"}'
        )


class LoadPortAscii:
    """Manages load port hardware status and operations using ASCII communication protocol"""

    def __init__(
        self,
        port_id: int,
        signal_manager: SignalManager,
        com_port: str = 'COM1',
        baud_rate: int = 9600,
        timeout: float = 1.0,
    ):
        """
        Initialize the LoadPortAscii object.

        Args:
            port_id (int): The ID of the port
            signal_manager (SignalManager): Signal manager for this load port
            com_port (str): Serial port name (default: 'COM1')
            baud_rate (int): Serial communication speed (default: 9600)
            timeout (float): Serial read timeout in seconds (default: 1.0)
        """
        self.port_id = port_id
        self.signal_manager = signal_manager
        self.status_record = []
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.serial_lock = threading.RLock()
        self.last_alarm_code = '0000'

        # Event monitoring thread control
        self.event_monitor_active = False
        self.event_thread = None

        # Initialize serial port
        try:
            self.serial = serial.Serial(
                port=com_port,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout,
            )
            logger.info(
                f'Serial connection established on {com_port} for LPT_{port_id}'
            )
        except Exception as e:
            logger.error(f'Failed to open serial port {com_port}: {e}')
            self.serial = None

        # Initialize internal hardware signal states based on LPT status
        self._signals: dict[LPTSignals, bool] = {
            LPTSignals.CARRIER_PRESENT: False,
            LPTSignals.LATCH_LOCKED: False,
            LPTSignals.LPT_READY: True,
            LPTSignals.LPT_ERROR: False,
        }

        # Update initial state from device
        self._update_port_status()

        # Start event monitoring thread
        self._start_event_monitor()

        # Callback for LPT_READY changes
        self._on_lpt_ready_changed: Callable[[int, bool], None] | None = None
        self._on_carrier_changed: Callable[[int, bool], None] | None = None

    def _send_command(self, command: str) -> str:
        """
        Send a command to the LPT and return the response.
        """
        if not self.serial:
            logger.error(f'LPT_{self.port_id}: Serial connection not available')
            return ''

        with self.serial_lock:
            try:
                # Clear any pending data
                self.serial.reset_input_buffer()

                # Send command with CR+LF
                cmd = f'{command}\r\n'
                logger.debug(f'LPT_{self.port_id} sending: {command}')
                self.serial.write(cmd.encode('ascii'))

                # Read response
                response = ''
                line = self.serial.readline().decode('ascii').strip()
                while line:
                    response += line + '\n'
                    # Check if more data is available
                    if self.serial.in_waiting:
                        line = self.serial.readline().decode('ascii').strip()
                    else:
                        break

                logger.debug(f'LPT_{self.port_id} received: {response.strip()}')
                return response.strip()

            except Exception as e:
                logger.error(f'LPT_{self.port_id} communication error: {e}')
                return ''

    def _parse_status_response(self, response: str) -> dict[str, str]:
        """
        Parse the FSD (status response) message into a dictionary.

        Args:
            response (str): FSD message from LPT

        Returns:
            Dict[str, str]: Dictionary of status fields and values
        """
        status = {}
        if not response.startswith('FSD'):
            return status

        # Remove the FSD part
        fields = response[4:].split()

        for field in fields:
            if '=' in field:
                key, value = field.split('=', 1)
                status[key] = value

        return status

    def _update_port_status(self) -> bool:
        """
        Query the LPT for current status and update internal state.

        Returns:
            bool: True if update was successful, False otherwise
        """
        # Request general status (FC=0)
        response = self._send_command('FSR FC=0')

        if not response:
            logger.error(f'LPT_{self.port_id}: Failed to get status')
            return False

        status = self._parse_status_response(response)

        if not status:
            logger.error(f'LPT_{self.port_id}: Invalid status response: {response}')
            return False

        try:
            # Update internal signals based on status response
            # Note: Converting string values from LPT response to boolean values for internal use
            carrier_present = status.get('PIP', 'TRUE') == 'TRUE'
            latch_locked = status.get('PRTST', 'LOCK') == 'LOCK'
            lpt_ready = status.get('READY', 'FALSE') == 'TRUE'
            error_active = status.get('ALMID', '0000') != '0000'

            # Store alarm code if there is one
            if error_active:
                self.last_alarm_code = status.get('ALMID', '0000')

            # Update internal state
            self._update_signal(LPTSignals.CARRIER_PRESENT, carrier_present)
            self._update_signal(LPTSignals.LATCH_LOCKED, latch_locked)
            self._update_signal(LPTSignals.LPT_READY, lpt_ready)
            self._update_signal(LPTSignals.LPT_ERROR, error_active)

            logger.debug(f'LPT_{self.port_id} status updated: {self.get_port_status()}')
            return True

        except Exception as e:
            logger.error(f'LPT_{self.port_id}: Error updating status: {e}')
            return False

    def _update_signal(self, signal: LPTSignals, new_value: bool) -> None:
        """
        Update internal signal state and notify signal manager.

        Args:
            signal (LPTSignals): Signal to update
            new_value (bool): New value for the signal
        """
        signal_map = {
            LPTSignals.CARRIER_PRESENT: f'CARRIER_PRESENT_{self.port_id}',
            LPTSignals.LATCH_LOCKED: f'LATCH_LOCKED_{self.port_id}',
            LPTSignals.LPT_READY: f'LPT_READY_{self.port_id}',
            LPTSignals.LPT_ERROR: f'LPT_ERROR_{self.port_id}',
        }

        old_value = self._signals[signal]

        if old_value == new_value:
            return

        self._signals[signal] = new_value
        self.signal_manager.set_signal(signal_map[signal], new_value)
        logger.debug(
            f'LPT_{self.port_id}: Signal {signal.name} changed from {old_value} to {new_value}'
        )

    def _event_monitor(self):
        """
        Background thread to monitor LPT events and alarms.
        This continuously reads from the serial port and processes event messages.
        """
        logger.info(f'LPT_{self.port_id}: Event monitor started')

        while self.event_monitor_active:
            try:
                # Non-blocking read with smaller timeout
                with self.serial_lock:
                    self.serial.timeout = 0.1
                    line = (
                        self.serial.readline().decode('ascii', errors='ignore').strip()
                    )
                    self.serial.timeout = self.timeout

                if not line:
                    # No data, sleep briefly to avoid tight loop
                    time.sleep(0.1)
                    continue

                # Process events (AERS) and alarms (ARS)
                if line.startswith('AERS'):
                    self._handle_event(line)
                elif line.startswith('ARS'):
                    self._handle_alarm(line)

                # Update status periodically regardless of events
                if not self.serial_lock.locked():
                    self._update_port_status()

            except Exception as e:
                logger.error(f'LPT_{self.port_id}: Event monitor error: {e}')
                time.sleep(1.0)  # Avoid tight error loop

        logger.info(f'LPT_{self.port_id}: Event monitor stopped')

    def _handle_event(self, event_msg: str):
        """
        Process event messages from the LPT.

        Args:
            event_msg (str): Event message from LPT
        """
        # Extract event code: AERS EVENT_CODE
        parts = event_msg.split()
        if len(parts) < 2:
            logger.warning(f'LPT_{self.port_id}: Invalid event message: {event_msg}')
            return

        event_code = parts[1]
        logger.info(f'LPT_{self.port_id}: Event received: {event_code}')

        # Handle specific events
        if event_code == 'POD_ARRIVED':
            self._update_signal(LPTSignals.CARRIER_PRESENT, True)
        elif event_code == 'POD_REMOVED':
            self._update_signal(LPTSignals.CARRIER_PRESENT, False)
        elif event_code == 'CMPL_LOCK':
            self._update_signal(LPTSignals.LATCH_LOCKED, True)
        elif event_code == 'CMPL_UNLOCK':
            self._update_signal(LPTSignals.LATCH_LOCKED, False)
        elif event_code in ('AUTO_MODE', 'POWER_UP'):
            # Refresh complete status after these events
            self._update_port_status()

    def _handle_alarm(self, alarm_msg: str):
        """
        Process alarm messages from the LPT.

        Args:
            alarm_msg (str): Alarm message from LPT
        """
        # Extract alarm code: ARS XX YY ZZZZZZ
        parts = alarm_msg.split(maxsplit=2)
        if len(parts) < 2:
            logger.warning(f'LPT_{self.port_id}: Invalid alarm message: {alarm_msg}')
            return

        # Format: ARS XXYY ZZZZZZ
        alarm_id = parts[1]
        alarm_text = parts[2] if len(parts) > 2 else ''

        logger.warning(f'LPT_{self.port_id}: Alarm received: {alarm_id} - {alarm_text}')

        # Set error status
        self.last_alarm_code = alarm_id
        self._update_signal(LPTSignals.LPT_ERROR, True)

        # Refresh complete status
        self._update_port_status()

    def _start_event_monitor(self):
        """Start the event monitoring thread"""
        if self.event_thread is None or not self.event_thread.is_alive():
            self.event_monitor_active = True
            self.event_thread = threading.Thread(
                target=self._event_monitor, daemon=True
            )
            self.event_thread.start()
            logger.info(f'LPT_{self.port_id}: Event monitor thread started')

    def _stop_event_monitor(self):
        """Stop the event monitoring thread"""
        self.event_monitor_active = False
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=2.0)
            logger.info(f'LPT_{self.port_id}: Event monitor thread stopped')

    @property
    def unload_ready(self) -> bool:
        """Check if port is ready for unload operation"""
        return self.get_port_status().is_ready_for_unload

    @property
    def load_ready(self) -> bool:
        """Check if port is ready for load operation"""
        return self.get_port_status().is_ready_for_load

    @property
    def ready_and_error_clear(self) -> bool:
        """Check if port is ready and has no errors"""
        return (
            self.get_port_status().lpt_ready and not self.get_port_status().error_active
        )

    def __str__(self) -> str:
        """String representation of the port"""
        return f'LPT_{self.port_id}'

    def get_port_status(self) -> PortStatus:
        """
        Get current state of this port.
        This will query the LPT and update internal state.

        Returns:
            PortStatus: Current status of the port
        """
        # Refresh status from device
        self._update_port_status()

        return PortStatus(
            port_id=self.port_id,
            carrier_present=self.signal_manager.get_signal(
                f'CARRIER_PRESENT_{self.port_id}'
            ),
            latch_locked=self.signal_manager.get_signal(f'LATCH_LOCKED_{self.port_id}'),
            lpt_ready=self.signal_manager.get_signal(f'LPT_READY_{self.port_id}'),
            error_active=self.signal_manager.get_signal(f'LPT_ERROR_{self.port_id}'),
        )

    def get_port_status_record(self) -> list[dict[str, str]]:
        """
        Returns a list of dictionaries containing signal names and their current values.

        Returns:
            List[Dict[str, str]]: Signal status record
        """
        signal_map = {
            'carrier_present': f'CARRIER_PRESENT_{self.port_id}',
            'latch_locked': f'LATCH_LOCKED_{self.port_id}',
            'lpt_ready': f'LPT_READY_{self.port_id}',
            'error_active': f'LPT_ERROR_{self.port_id}',
        }

        signals = [
            {
                'signal': signal_map['carrier_present'],
                'value': self.get_signal(LPTSignals.CARRIER_PRESENT),
            },
            {
                'signal': signal_map['latch_locked'],
                'value': self.get_signal(LPTSignals.LATCH_LOCKED),
            },
            {
                'signal': signal_map['lpt_ready'],
                'value': self.get_signal(LPTSignals.LPT_READY),
            },
            {
                'signal': signal_map['error_active'],
                'value': self.get_signal(LPTSignals.LPT_ERROR),
            },
        ]

        return signals

    def set_signal(self, signal: LPTSignals, new_value: bool) -> None:
        """
        Set a signal value. In ASCII mode, some signals are read-only from the hardware.
        For signals that can be controlled, appropriate commands will be sent.

        Args:
            signal (LPTSignals): Signal to set
            new_value (bool): New value for the signal
        """
        # Most signals are read-only in ASCII mode, but we'll map actions for settable ones
        if signal == LPTSignals.LATCH_LOCKED:
            if new_value:
                # Lock port
                response = self._send_command('HCS LOCK')
                if response.startswith('HCA OK'):
                    self._update_signal(LPTSignals.LATCH_LOCKED, True)
            else:
                # Unlock port
                response = self._send_command('HCS UNLK')
                if response.startswith('HCA OK'):
                    self._update_signal(LPTSignals.LATCH_LOCKED, False)
        elif signal == LPTSignals.LPT_ERROR:
            if not new_value:
                # Clear error by attempting recovery
                self._send_command('HCS RECOVERY')
                self._update_port_status()
        else:
            # Other signals are read-only in ASCII mode
            logger.warning(
                f'LPT_{self.port_id}: Cannot directly set {signal.name} in ASCII mode'
            )

            # Still update internal state for compatibility
            signal_map = {
                LPTSignals.CARRIER_PRESENT: f'CARRIER_PRESENT_{self.port_id}',
                LPTSignals.LATCH_LOCKED: f'LATCH_LOCKED_{self.port_id}',
                LPTSignals.LPT_READY: f'LPT_READY_{self.port_id}',
                LPTSignals.LPT_ERROR: f'LPT_ERROR_{self.port_id}',
            }

            old_value = self._signals[signal]
            if old_value != new_value:
                self._signals[signal] = new_value
                self.signal_manager.set_signal(signal_map[signal], new_value)

    def get_signal(self, signal: LPTSignals) -> bool:
        """
        Get current signal value.

        Args:
            signal (LPTSignals): Signal to get

        Returns:
            bool: Current value of the signal
        """
        signal_map = {
            LPTSignals.CARRIER_PRESENT: f'CARRIER_PRESENT_{self.port_id}',
            LPTSignals.LATCH_LOCKED: f'LATCH_LOCKED_{self.port_id}',
            LPTSignals.LPT_READY: f'LPT_READY_{self.port_id}',
            LPTSignals.LPT_ERROR: f'LPT_ERROR_{self.port_id}',
        }

        return self.signal_manager.get_signal(signal_map[signal])

    def is_ho_avbl(self) -> bool:
        """
        Check if port is available for handoff operations.
        This will check if the port is in proper condition for handshake.

        Returns:
            bool: True if the port is available for handoff, False otherwise
        """
        # Check current status
        status = self.get_port_status()
        return status.lpt_ready and not status.error_active

    def enable_load(self) -> bool:
        """
        Enable LOAD interlock for this port.

        Returns:
            bool: True if successful, False otherwise
        """
        cmd = f'HCS ENABLE LOAD P{self.port_id + 1}'
        response = self._send_command(cmd)
        return response.startswith('HCA OK')

    def enable_unload(self) -> bool:
        """
        Enable UNLOAD interlock for this port.

        Returns:
            bool: True if successful, False otherwise
        """
        cmd = f'HCS ENABLE UNLOAD P{self.port_id + 1}'
        response = self._send_command(cmd)
        return response.startswith('HCA OK')

    def disable_load(self) -> bool:
        """
        Disable LOAD interlock for this port.

        Returns:
            bool: True if successful, False otherwise
        """
        cmd = f'HCS DISABLE LOAD P{self.port_id + 1}'
        response = self._send_command(cmd)
        return response.startswith('HCA OK')

    def disable_unload(self) -> bool:
        """
        Disable UNLOAD interlock for this port.

        Returns:
            bool: True if successful, False otherwise
        """
        cmd = f'HCS DISABLE UNLOAD P{self.port_id + 1}'
        response = self._send_command(cmd)
        return response.startswith('HCA OK')

    def load(self) -> bool:
        """
        Initiate a LOAD operation.

        Returns:
            bool: True if successful, False otherwise
        """
        cmd = f'HCS LOAD P{self.port_id + 1}'
        response = self._send_command(cmd)
        return response.startswith('HCA OK')

    def unload(self) -> bool:
        """
        Initiate an UNLOAD operation.

        Returns:
            bool: True if successful, False otherwise
        """
        cmd = f'HCS UNLOAD P{self.port_id + 1}'
        response = self._send_command(cmd)
        return response.startswith('HCA OK')

    def recovery(self) -> bool:
        """
        Initiate a RECOVERY operation.

        Returns:
            bool: True if successful, False otherwise
        """
        cmd = f'HCS RECOVERY P{self.port_id + 1}'
        response = self._send_command(cmd)
        return response.startswith('HCA OK')

    def lock_port(self) -> bool:
        """
        Lock the port.

        Returns:
            bool: True if successful, False otherwise
        """
        response = self._send_command('HCS LOCK')
        if response.startswith('HCA OK'):
            self._update_signal(LPTSignals.LATCH_LOCKED, True)
            return True
        return False

    def unlock_port(self) -> bool:
        """
        Unlock the port.

        Returns:
            bool: True if successful, False otherwise
        """
        response = self._send_command('HCS UNLK')
        if response.startswith('HCA OK'):
            self._update_signal(LPTSignals.LATCH_LOCKED, False)
            return True
        return False

    def reset(self) -> None:
        """
        Reset port to default state.
        This will stop operations and reset signal states.
        """
        # Unlock port
        self.unlock_port()

        # Reset signals to default state
        self._signals = {
            LPTSignals.CARRIER_PRESENT: False,
            LPTSignals.LATCH_LOCKED: False,
            LPTSignals.LPT_READY: True,
            LPTSignals.LPT_ERROR: False,
        }

        # Update signal manager
        for signal, value in self._signals.items():
            signal_map = {
                LPTSignals.CARRIER_PRESENT: f'CARRIER_PRESENT_{self.port_id}',
                LPTSignals.LATCH_LOCKED: f'LATCH_LOCKED_{self.port_id}',
                LPTSignals.LPT_READY: f'LPT_READY_{self.port_id}',
                LPTSignals.LPT_ERROR: f'LPT_ERROR_{self.port_id}',
            }
            self.signal_manager.set_signal(signal_map[signal], value)

        # Recovery
        self.recovery()

        # Update current status
        self._update_port_status()

        logger.debug(f'Port {self.port_id} reset to default state')

    def close(self):
        """Close the serial connection and stop the event monitor"""
        self._stop_event_monitor()

        if self.serial:
            try:
                self.serial.close()
                logger.info(f'LPT_{self.port_id}: Serial connection closed')
            except Exception as e:
                logger.error(
                    f'LPT_{self.port_id}: Error closing serial connection: {e}'
                )


# For testing purposes
if __name__ == '__main__':
    import sys

    from signal_manager import SignalManager

    # Set up logging
    logger.remove()
    logger.add(sys.stderr, level='INFO')

    # Create a signal manager
    signal_manager = SignalManager()

    # Create a load port
    load_port = LoadPortAscii(
        port_id=0, signal_manager=signal_manager, serial_port='/dev/ttyS0'
    )

    try:
        # Print the initial status
        print(f'Initial status: {load_port.get_port_status()}')

        # Test getting signals
        for signal in LPTSignals:
            print(f'{signal.name}: {load_port.get_signal(signal)}')

        # Test command: lock port
        print('\nTesting lock command...')
        load_port.set_signal(LPTSignals.LATCH_LOCKED, True)
        print(f'Locked: {load_port.get_signal(LPTSignals.LATCH_LOCKED)}')

        # Test command: unlock port
        print('\nTesting unlock command...')
        load_port.set_signal(LPTSignals.LATCH_LOCKED, False)
        print(f'Locked: {load_port.get_signal(LPTSignals.LATCH_LOCKED)}')

        # Test enable/disable commands
        print('\nTesting enable load command...')
        load_port.enable_load()

        print('\nTesting enable unload command...')
        load_port.enable_unload()

        print('\nTesting disable load command...')
        load_port.disable_load()

        print('\nTesting disable unload command...')
        load_port.disable_unload()

        # Test properties
        print(f'\nLoad ready: {load_port.load_ready}')
        print(f'Unload ready: {load_port.unload_ready}')
        print(f'Ready and error clear: {load_port.ready_and_error_clear}')

        # Print the final status
        print(f'\nFinal status: {load_port.get_port_status()}')

    except Exception as e:
        print(f'Test failed: {e}')
    finally:
        # Clean up
        load_port.close()
