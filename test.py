from time import sleep
from typing import Dict

from loguru import logger

from e84_controller import E84Controller
from load_port import LPTSignals
from signal_manager import SignalManager
from signal_simulators import AgvSimulator, EquipmentSimulator


class TestE84Controller:
    def __init__(
        self, signal_manager: SignalManager, e84_controller: E84Controller, app
    ):
        self.signal_manager = signal_manager
        self.e84_controller = e84_controller
        self.app = app
        logger.debug('TestE84Controller initialized')
        self.agv_sim = AgvSimulator(
            self.signal_manager, e84_controller=self.e84_controller
        )
        self.equip_sim = EquipmentSimulator(
            self.signal_manager, e84_controller=self.e84_controller
        )

    def test_ready_signal_change(self):
        # Simulate LPT_READY signal change by setting it to False on lpt_0's load_port.
        logger.debug('Testing ready signal change: Setting LPT_READY to False')
        self.e84_controller.lpt_0.load_port.set_signal(LPTSignals.LPT_READY, False)
        sleep(0.1)  # Optional delay for simulation purposes

    def test_ho_avbl_signal_change(self):
        port = 0
        # Step 1: Turn on CS_x signal
        logger.debug(f'Step 1: Turning CS_{port} signal ON')
        self.signal_manager.set_signal(f'CS_{port}', True)
        sleep(0.1)

        # Step 2: Turn on VALID signal
        logger.debug('Step 2: Turning VALID signal ON')
        self.signal_manager.set_signal('VALID', True)
        sleep(0.1)

        # Step 3: Turn on TR_REQ signal
        logger.debug('Step 3: Turning TR_REQ signal ON')
        self.signal_manager.set_signal('TR_REQ', True)
        sleep(0.1)

        # Step 4: Turn HO_AVBL signal OFF
        logger.debug('Step 4: Turning HO_AVBL signal OFF')
        self.signal_manager.set_signal('HO_AVBL', False)
        sleep(0.1)

        # Step 5: Turn on BUSY signal
        logger.debug('Step 5: Turning BUSY signal ON')
        self.signal_manager.set_signal('BUSY', True)
        sleep(0.1)

        # Step 6: Turn off BUSY and TR_REQ signals, then turn on COMPT signal
        logger.debug('Step 6: Turning BUSY and TR_REQ signals OFF, and COMPT signal ON')
        self.signal_manager.set_signal('BUSY', False)
        self.signal_manager.set_signal('TR_REQ', False)
        self.signal_manager.set_signal('COMPT', True)

    def test_happy_path_load(self):
        wait_time = 0.2
        port = 0
        # Step 1: Turn on CS_x signal
        logger.debug(f'Step 1: Turning CS_{port} signal ON')
        self.signal_manager.set_signal(f'CS_{port}', True)
        sleep(wait_time)

        # Step 2: Turn on VALID signal
        logger.debug('Step 2: Turning VALID signal ON')
        self.signal_manager.set_signal('VALID', True)
        sleep(wait_time)

        # Step 3: Turn on TR_REQ signal
        logger.debug('Step 3: Turning TR_REQ signal ON')
        self.signal_manager.set_signal('TR_REQ', True)
        sleep(wait_time)

        # Step 4: Turn on BUSY signal
        logger.debug('Step 4: Turning BUSY signal ON')
        self.signal_manager.set_signal('BUSY', True)
        sleep(wait_time)

        # Step 5: Simulate carrier detection by turning on CARRIER_PRESENT signal
        logger.debug(f'Step 5: Turning CARRIER_PRESENT_{port} signal ON')
        self.signal_manager.set_signal(f'CARRIER_PRESENT_{port}', True)
        sleep(wait_time)

        # Step 6: Turn off BUSY and TR_REQ signals, and turn on COMPT signal
        logger.debug('Step 6: Turning BUSY and TR_REQ signals OFF, and COMPT signal ON')
        self.signal_manager.set_signal('BUSY', False)
        self.signal_manager.set_signal('TR_REQ', False)
        self.signal_manager.set_signal('COMPT', True)
        sleep(wait_time)

        # Step 7: Turn off COMPT, VALID, and CS_x signals to complete the sequence
        logger.debug(
            f'Step 7: Turning off COMPT, VALID, and CS_{port} signals; sequence complete'
        )
        self.signal_manager.set_signal('VALID', False)
        self.signal_manager.set_signal('COMPT', False)
        self.signal_manager.set_signal(f'CS_{port}', False)

    def _start_auto_sequence(self, operation: str = 'LOAD', port_status: Dict = None):
        """Initialize and run automatic sequence."""
        # Initialize both simulators
        self.agv_sim.start_sequence(operation)
        self.equip_sim.start_sequence(operation)
        self.selected_machine = self.e84_controller.selected_machine
        # Start automatic execution
        self._execute_auto_sequence(0)

    def _execute_auto_sequence(self, step):
        """Execute complete sequence automatically."""
        if step < 7:
            success = self._execute_step(step)
            if success:
                # Schedule next step after delay
                self.app.after(100, lambda: self._execute_auto_sequence(step + 1))
            else:
                logger.error(f'Error in auto sequence at step {step}')

    def _execute_step(self, step):
        """Execute a single step in the sequence."""
        try:
            # Execute step in AGV simulator
            agv_success = self.agv_sim.execute_step(step)

            # Execute step in Equipment simulator
            if step == 4:
                equip_success = self.equip_sim.execute_step(step)
            else:
                equip_success = True

            return agv_success and equip_success

        except Exception as e:
            logger.error(f'Error executing step {step}: {str(e)}')
            return False
