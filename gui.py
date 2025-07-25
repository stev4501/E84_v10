"""
gui.py - Combined GUI implementation for E84 controller

This module provides GUI implementations for all operating modes:
- Production mode: Standard interface with signal visualization
- Emulation mode: Enhanced interface with manual controls
- Simulation mode: Full simulation interface with signal controls
"""

import customtkinter as ctk
from loguru import logger

from e84_controller import E84Controller
from gui_styling import (
    GUIColors,
    LoadPortSignalControls,
    MessageLog,
    SignalControlPanel,
    SignalVisualization,
    SystemStatusVisualization,
)
from signal_manager import SignalManager

# Import simulators if available (may not be needed in production mode)
try:
    from signal_simulators import AgvSimulator, EquipmentSimulator
except ImportError:
    # Create stub classes for production mode if simulators aren't available
    class AgvSimulator:
        def __init__(self, *args, **kwargs):
            pass

        def start_sequence(self, *args, **kwargs):
            pass

        def execute_step(self, *args, **kwargs):
            return True

        def reset_sequence(self):
            pass

    class EquipmentSimulator:
        def __init__(self, *args, **kwargs):
            pass

        def start_sequence(self, *args, **kwargs):
            pass

        def execute_step(self, *args, **kwargs):
            return True

        def reset_sequence(self):
            pass


class E84BaseGui(ctk.CTk):
    """Base GUI class with common functionality for all operating modes."""

    def __init__(
        self,
        signal_manager: SignalManager,
        e84_controller: E84Controller,
        show_message_log,
    ):
        super().__init__()

        # Initialize managers
        self.signal_manager = signal_manager
        self.e84_controller = e84_controller
        self.callback_manager = getattr(e84_controller, 'callback_manager', None)
        self.show_message_log = show_message_log

        # Get operating mode
        self.operating_mode = getattr(e84_controller, 'operating_mode', 'prod')
        self.interface_type = getattr(e84_controller, 'interface_type', 'parallel')

        # Configure main window
        self.title(
            f'E84 Controller GUI - {self.operating_mode.capitalize()} Mode | {self.interface_type.capitalize()} Interface'
        )
        self.geometry('1024x768')
        self.protocol('WM_DELETE_WINDOW', self.cleanup)

        # Create main container frame
        self.main_container = ctk.CTkFrame(
            self,
            fg_color=GUIColors.BG_MAIN,
        )
        self.main_container.grid(row=0, column=0, sticky='nsew')

        # Configure grid weights
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

    def _create_gui_event_log(self):
        """Create the event log panel if enabled."""
        if self.show_message_log:
            self.message_log = MessageLog(self.main_container, title='Event Log')
            self.message_log.setup_logging()
        else:
            # Set up console logging only

            logger.info('GUI message log disabled, logging to console only')

    def _register_callbacks(self) -> None:
        """Register all necessary callbacks for signal updates"""
        # Define all signals to watch
        signals_to_watch = [
            # Active Equipment Signals
            'CS_0',
            'CS_1',
            'VALID',
            'TR_REQ',
            'BUSY',
            'COMPT',
            # Passive Equipment Signals
            'L_REQ',
            'U_REQ',
            'READY',
            'HO_AVBL',
            'ES',
            # LPT 0 signals
            'LPT_READY_0',
            'LPT_ERROR_0',
            'CARRIER_PRESENT_0',
            'LATCH_LOCKED_0',
            # LPT 1 signals
            'LPT_READY_1',
            'LPT_ERROR_1',
            'CARRIER_PRESENT_1',
            'LATCH_LOCKED_1',
        ]

        for signal in signals_to_watch:
            self.signal_manager.add_watcher(signal, self._on_signal_change)

    def _on_signal_change(self, *args, **kwargs) -> None:
        """Handle any signal change by updating relevant GUI components"""
        self.after(5, self._update_gui)

    def _update_gui(self) -> None:
        """Update all GUI components with latest values using signal snapshot"""
        try:
            # Get all signal states in a single call
            signal_states = dict(self.signal_manager.signal_snapshot())

            # Update active signals
            active_signals = ['CS_0', 'CS_1', 'VALID', 'TR_REQ', 'BUSY', 'COMPT']
            if hasattr(self, 'active_signals'):
                for signal in active_signals:
                    if signal in signal_states:
                        self.active_signals.update_signal(signal, signal_states[signal])

            # Update passive signals
            passive_signals = ['L_REQ', 'U_REQ', 'READY', 'HO_AVBL', 'ES']
            if hasattr(self, 'passive_signals'):
                for signal in passive_signals:
                    if signal in signal_states:
                        self.passive_signals.update_signal(
                            signal, signal_states[signal]
                        )

            # Update system status if present
            if hasattr(self, 'system_status'):
                self.system_status.update_status()

        except Exception as e:
            logger.error(f'GUI update error: {str(e)}')

    def cleanup(self) -> None:
        """Cleanup resources before closing"""
        try:
            # Remove all signal watchers
            for signal in self.signal_manager.signal_snapshot():
                signal_name = signal[0]
                try:
                    self.signal_manager.remove_watcher(
                        signal_name, self._on_signal_change
                    )
                except Exception:
                    pass  # Ignore errors if watcher not found

            # Clean up any running threads or resources
            for widget in self.winfo_children():
                widget.destroy()

            self.signal_manager = None
            self.e84_controller = None

        except Exception as e:
            logger.error(f'Cleanup error: {str(e)}')
        finally:
            self.destroy()


class E84ProductionGui(E84BaseGui):
    """Production GUI with standard visualization features."""

    def __init__(
        self,
        signal_manager: SignalManager,
        e84_controller: E84Controller,
        show_message_log,
    ):
        super().__init__(signal_manager, e84_controller, show_message_log)

        # Create widgets
        self._create_top_panel()
        self._create_gui_event_log()

        # Register signal callbacks
        self._register_callbacks()

        # Layout widgets based on message log status
        self._layout_widgets()

        # Start the GUI update timer
        self._update_gui()

    def _create_top_panel(self):
        """Create the top panel with status and signals."""
        # State Machine Status
        self.system_status = SystemStatusVisualization(
            self.main_container, self.signal_manager, self.e84_controller
        )
        self.system_status.grid(
            row=0, column=0, padx=(5, 5), pady=(10, 10), sticky='nsew'
        )

        # Signal visualizations container
        self.signal_viz_frame = ctk.CTkFrame(
            self.main_container,
            fg_color=GUIColors.BG_PANEL,
            border_width=1,
            border_color=GUIColors.BORDER,
        )
        self.signal_viz_frame.grid(
            row=0, column=1, padx=(5, 10), pady=10, sticky='nsew'
        )

        # Title
        ctk.CTkLabel(
            self.signal_viz_frame,
            text='Signal Visualizations',
            font=ctk.CTkFont(size=16, weight='bold'),
            text_color=GUIColors.TEXT_TITLE,
        ).pack(padx=10, pady=(10, 5), anchor='w')

        # ---------------
        # Active signals
        # ---------------
        ctk.CTkLabel(
            self.signal_viz_frame,
            text='ACTIVE EQ SIGNALS:',
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color=GUIColors.TEXT_NORMAL,
        ).pack(padx=20, pady=(0, 1), anchor='w')

        self.active_signals = SignalVisualization(
            self.signal_viz_frame, ['CS_0', 'CS_1', 'VALID', 'TR_REQ', 'BUSY', 'COMPT']
        )
        self.active_signals.pack(fill='x', padx=20, pady=(0, 10))

        # ---------------
        # Passive signals
        # ---------------
        ctk.CTkLabel(
            self.signal_viz_frame,
            text='PASSIVE EQ SIGNALS:',
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color=GUIColors.TEXT_NORMAL,
        ).pack(pady=(0, 1), padx=20, anchor='w')

        self.passive_signals = SignalVisualization(
            self.signal_viz_frame, ['L_REQ', 'U_REQ', 'READY', 'HO_AVBL', 'ES']
        )
        self.passive_signals.pack(fill='x', padx=20, pady=(0, 10))

    def _layout_widgets(self):
        """Layout widgets in the main window using grid."""
        # Top row: Mode and System Status
        self.system_status.grid(
            row=0, column=0, padx=(5, 5), pady=(10, 10), sticky='nsew'
        )

        # Signal Visualizations (spans both rows)
        self.signal_viz_frame.grid(
            row=0, column=1, padx=(5, 10), pady=10, sticky='nsew'
        )

        # Message log (if enabled)
        if self.show_message_log:
            self.message_log.grid(
                row=1,
                column=0,
                columnspan=2,
                rowspan=2,
                padx=5,
                pady=5,
                sticky='nsew',
            )


class E84SimulationGui(E84BaseGui):
    """Simulation GUI with controls for manual signal manipulation."""

    def __init__(
        self,
        signal_manager: SignalManager,
        e84_controller: E84Controller,
        show_message_log,
    ):
        super().__init__(signal_manager, e84_controller, show_message_log)

        # Initialize simulators for simulation/emulation modes
        self.agv_sim = AgvSimulator(self.signal_manager, self.e84_controller)
        self.equip_sim = EquipmentSimulator(
            self.signal_manager,
            self.e84_controller,
            self.callback_manager,
            {},  # Empty pin mappings for simulation
            simulation_config={},
        )

        # Create widgets
        self._create_widgets()

        # Set up logging
        self._create_gui_event_log()

        # Layout widgets based on message log status
        self._layout_widgets()

        if not self.show_message_log:
            logger.debug('Simulation GUI initialized with message log disabled')

    def _create_widgets(self):
        """Create all simulation GUI widgets."""

        # Register callbacks and start updates
        self._register_callbacks()

        # --------------------------------------------
        # System Status Visualization
        # ---------------------------------------------
        self.system_status = SystemStatusVisualization(
            self.main_container, self.signal_manager, self.e84_controller
        )

        # ----------------------------------------
        # Signal Visualization Frame (ON/OFF boxes)
        # ----------------------------------------
        self.signal_viz_frame = ctk.CTkFrame(
            self.main_container, fg_color=GUIColors.BG_PANEL, corner_radius=5
        )

        ctk.CTkLabel(
            self.signal_viz_frame,
            text='Signal Visualizations',
            font=ctk.CTkFont(size=16, weight='bold'),
            text_color=GUIColors.TEXT_TITLE,
        ).pack(pady=(10, 5), padx=10, anchor='w')

        # Active signals (AGV)
        ctk.CTkLabel(
            self.signal_viz_frame,
            text='Active Equipment Signals:',
            font=ctk.CTkFont(size=12),
        ).pack(anchor='w', padx=10, pady=(5, 0))

        self.active_signals = SignalVisualization(
            self.signal_viz_frame,
            ['CS_0', 'CS_1', 'VALID', 'TR_REQ', 'BUSY', 'COMPT'],
        )
        self.active_signals.pack(fill='x', padx=10, pady=(0, 15))

        # Passive signals (Equipment)
        ctk.CTkLabel(
            self.signal_viz_frame,
            text='Passive Equipment Signals:',
            font=ctk.CTkFont(size=12),
        ).pack(anchor='w', padx=10)

        self.passive_signals = SignalVisualization(
            self.signal_viz_frame,
            ['L_REQ', 'U_REQ', 'READY', 'HO_AVBL', 'ES'],
        )
        self.passive_signals.pack(fill='x', padx=10, pady=(0, 10))

        # --------------------------------------------
        # Port Status/Control Panel for CS0 and CS1
        # ---------------------------------------------
        self.port_control = LoadPortSignalControls(
            self.main_container,
            self.signal_manager,
            self.e84_controller,
            load_callback=self._handle_load,
            unload_callback=self._handle_unload,
            next_step_callback=self._execute_step,
        )

        # -----------------------------------------
        # AGV Signals Manual Control
        # ----------------------------------------
        self.agv_controls = SignalControlPanel(
            self.main_container,
            title='AGV Control',
            callback=self._on_signal_change,
            signal_manager=self.signal_manager,
        )

        # -----------------------------------------
        # Message log (created only if enabled)
        # -----------------------------------------
        if self.show_message_log:
            self.message_log = MessageLog(self.main_container, title='Event Log')

        # ---------------------
        # Reset button
        # ---------------------
        self.reset_button = ctk.CTkButton(
            self.main_container,
            text='Reset System',
            command=self.reset_system,
        )

        self._update_signal_visualizations()

    def _layout_widgets(self):
        """Layout widgets in the main window using grid based on whether message log is enabled."""
        # Layout adjusts based on whether message log is displayed
        if self.show_message_log:
            # Top row: System Status and Signal Viz
            self.system_status.grid(
                row=0, column=0, padx=(5, 5), pady=(10, 10), sticky='nsew'
            )
            self.signal_viz_frame.grid(
                row=0, column=1, padx=(5, 10), pady=10, sticky='nsew'
            )

            # Middle row: Message log
            self.message_log.grid(
                row=1, column=0, columnspan=2, rowspan=1, padx=5, pady=5, sticky='nsew'
            )

            # Bottom row: Controls
            self.port_control.grid(row=2, column=0, sticky='nsew', padx=5, pady=5)
            self.agv_controls.grid(row=2, column=1, sticky='nsew', padx=5, pady=5)

            # Reset Button
            self.reset_button.grid(row=3, column=0, sticky='w', padx=10, pady=10)
        else:
            # Without message log: Adjust grid to use the extra space
            self.system_status.grid(
                row=0, column=0, padx=(5, 5), pady=(10, 10), sticky='nsew'
            )
            self.signal_viz_frame.grid(
                row=0, column=1, padx=(5, 10), pady=10, sticky='nsew'
            )

            # Control panels in row 1
            self.port_control.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
            self.agv_controls.grid(row=1, column=1, sticky='nsew', padx=5, pady=5)

            # Reset Button
            self.reset_button.grid(row=2, column=0, sticky='w', padx=10, pady=10)

    def _handle_load(self, port_id):
        """Handle load request with port state."""
        logger.info(f'Automatic load initiated for Port: CS_{port_id}')
        self._start_auto_sequence('load', port_id)

    def _handle_unload(self, port_id):
        """Handle unload request with port state."""
        logger.info(f'Automatic unload initiated for Port: CS_{port_id}')
        self._start_auto_sequence('unload', port_id)

    def _start_auto_sequence(self, operation, port_id):
        """Initialize and run automatic sequence."""
        # Initialize both simulators
        self.agv_sim.start_sequence(operation, port_id)
        self.equip_sim.start_sequence(operation, port_id)
        self.selected_machine = self.e84_controller.selected_machine
        # Start automatic execution
        self._execute_auto_sequence(0, port_id)

    def _execute_auto_sequence(self, step, port):
        """Execute complete sequence automatically."""
        if step < 7:
            success = self._execute_step(step, port)
            if success:
                # Schedule next step after delay
                self.after(500, lambda: self._execute_auto_sequence(step + 1, port))
            else:
                logger.info(f'Error in auto sequence at step {step}')
        else:
            self.e84_controller.poll_cycle()

    def _execute_step(self, step, port):
        """Execute a single step in the sequence."""
        self.e84_controller.poll_cycle()
        try:
            # Execute step in AGV simulator
            agv_success = self.agv_sim.execute_step(step, port)

            # Execute step in Equipment simulator
            if step == 4:
                equip_success = self.equip_sim.execute_step(step, port)
            else:
                equip_success = True

            return agv_success and equip_success

        except Exception as e:
            logger.error(f'Error executing step {step}: {str(e)}')
            return False

    def _update_signal_visualizations(self):
        """Update signal visualizations based on current signal states."""
        try:
            # Update active equipment signals
            for signal in ['CS_0', 'CS_1', 'VALID', 'TR_REQ', 'BUSY', 'COMPT']:
                state = self.signal_manager.get_signal(signal)
                self.active_signals.update_signal(signal, state)

            # Update passive equipment signals
            for signal in ['L_REQ', 'U_REQ', 'READY', 'HO_AVBL', 'ES']:
                state = self.signal_manager.get_signal(signal)
                self.passive_signals.update_signal(signal, state)

            # Update system status
            self.system_status.update_status()

        except Exception as e:
            logger.error(f'Error update_signal_visualizations: {str(e)}')

        # Schedule next update
        self.after(100, self._update_signal_visualizations)

    def reset_system(self) -> None:
        """Reset system to initial state."""
        try:
            # Reset all signals first
            self.signal_manager.reset_signal_manager()

            # Reset E84 controller
            self.e84_controller.full_reset()

            # Reset simulators
            self.agv_sim.reset_sequence()
            self.equip_sim.reset_sequence()

            # Reset GUI elements
            self.agv_controls.reset_signals()
            self.system_status.update_status()
            self.port_control.reset()

            # Log reset
            logger.debug('System reset complete - returned to IDLE state')

            # Update visualizations
            self._update_signal_visualizations()

        except Exception as e:
            logger.error(f'Error during system reset: {str(e)}')


# Factory function to create the appropriate GUI based on operating mode
def create_gui(signal_manager, e84_controller, show_message_log):
    """Factory function to create the appropriate GUI based on operating mode."""
    operating_mode = getattr(e84_controller, 'operating_mode', 'production').lower()

    if operating_mode in ['simulation', 'sim', 'emulation', 'em']:
        return E84SimulationGui(signal_manager, e84_controller, show_message_log)
    else:
        return E84ProductionGui(signal_manager, e84_controller, show_message_log)


# For direct execution (testing)
if __name__ == '__main__':
    from e84_controller import E84Controller
    from signal_manager import SignalManager

    # Initialize managers
    signal_manager = SignalManager()
    e84_controller = E84Controller(signal_manager=signal_manager)

    # Create and run the appropriate GUI
    app = create_gui(signal_manager, e84_controller)
    app.mainloop()
