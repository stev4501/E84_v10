"""
prod_gui_styling.py using CustomTkinter
"""

import logging
from tkinter import ttk

import customtkinter as ctk
from loguru import logger
from tkloguru import LoggingInterceptHandler, LoguruWidget

from e84_controller import E84Controller
from load_port import LoadPort, LPTSignals
from signal_manager import SignalManager

# Set default appearance mode and color theme
ctk.set_appearance_mode('light')
ctk.set_default_color_theme('blue')  # other options: 'green', 'dark-blue'


class GUIColors:
    """Color scheme for CustomTkinter"""

    BG_MAIN = '#cfcfcf'  # Gray
    BG_PANEL = '#FFFFFF'  # White
    BG_TEXTBOX = '#f5f5f5'  # Light Gray
    SIGNAL_ACTIVE = '#4CAF50'  # Green
    SIGNAL_INACTIVE = '#000000'  # Black
    TEXT_TITLE = '#0078D7'  # Blue
    TEXT_NORMAL = '#000000'  # Black
    TEXT_INFO = '#000000'  # Black
    TEXT_DEBUG = '#0000ff'  # Blue
    TEXT_SUCCESS = '#2E7D32'  # Dark Green
    TEXT_WARNING = '#FFC107'  # Yellow
    TEXT_ERROR = '#D32F2F'  # Dark Red
    BORDER = '#E0E0E0'  # Light Gray
    PRODUCTION = '#4CAF50'  # Green
    EMULATION = '#FFC107'  # Yellow
    SIMULATION = '#2196F3'  # Blue


class StyledFrame(ctk.CTkFrame):
    """Base styled frame using CustomTkinter."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=GUIColors.BG_PANEL,
            corner_radius=5,
            border_width=1,
            border_color=GUIColors.BORDER,
            **kwargs,
        )


class SystemStatusVisualization(StyledFrame):
    """System status display using CustomTkinter."""

    def __init__(self, parent, signal_manager, e84_controller):
        super().__init__(parent, width=400)

        self.signal_manager = signal_manager
        self.e84_controller = e84_controller

        # Title label
        self.title_label = ctk.CTkLabel(
            self,
            text='State Machine Status',
            font=ctk.CTkFont(size=16, weight='bold'),
            text_color=GUIColors.TEXT_TITLE,
        )
        self.title_label.pack(
            padx=10,
            pady=(10, 5),
            anchor='w',
        )

        # Create ports container
        self.ports_main_frame = ctk.CTkFrame(self, fg_color='transparent', width=380)
        self.ports_main_frame.pack(fill='x', anchor='n', expand=True, padx=20)
        self.ports_main_frame.pack_propagate(False)

        # Configure equal columns with minimum width
        self.ports_main_frame.grid_columnconfigure(
            0, weight=1, minsize=185
        )  # Half of 370
        self.ports_main_frame.grid_columnconfigure(1, weight=1, minsize=185)

        # Create LPT frames
        self.lpt_frames = {}
        self.lpt_state_labels = {}
        self.lpt_status_labels = {}

        for i in range(2):
            self._create_port_frame(i)

    def _create_port_frame(self, port_num):
        """Create a single port frame with CustomTkinter widgets."""
        # Port container frame (includes title and content)
        port_container = ctk.CTkFrame(self.ports_main_frame, fg_color='transparent')
        port_container.grid(row=0, column=port_num, padx=5, pady=5, sticky='nsew')

        # Port title (outside the border frame)
        ctk.CTkLabel(
            port_container,
            text=f'LPT {port_num}',
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color=GUIColors.TEXT_NORMAL,
        ).pack(
            padx=2,
            pady=(0, 1),
            anchor='w',
        )

        # Content frame (with border)
        single_port_frame = ctk.CTkFrame(
            port_container,
            fg_color=GUIColors.BG_PANEL,
            corner_radius=5,
            border_width=1,
            border_color=GUIColors.BORDER,
            width=200,
            # height=180,  # Reduced height since title is now outside
        )
        single_port_frame.pack(fill='both', anchor='center', expand=True)
        single_port_frame.pack_propagate(False)

        # State label
        self.lpt_state_labels[port_num] = ctk.CTkLabel(
            single_port_frame,
            text='IDLE',
            font=ctk.CTkFont(size=16, weight='bold'),
            text_color=GUIColors.TEXT_SUCCESS,
        )
        self.lpt_state_labels[port_num].pack(pady=(15, 2), padx=10, anchor='w')
        # Seperator

        ttk.Separator(single_port_frame, orient='horizontal').pack(
            fill='x', padx=10, pady=8
        )

        # Status indicators
        self.lpt_status_labels[port_num] = {}
        indicators = [
            ('Carrier', 'Not Present', GUIColors.TEXT_WARNING),
            ('Latch', 'Unlocked', GUIColors.TEXT_SUCCESS),
            ('LPT Ready', 'Ready', GUIColors.TEXT_SUCCESS),
            ('Error', 'None', GUIColors.TEXT_SUCCESS),
        ]

        for label, value, color in indicators:
            status_frame = ctk.CTkFrame(single_port_frame, fg_color='transparent')
            status_frame.pack(fill='x', pady=2, padx=10, anchor='center')

            ctk.CTkLabel(
                status_frame, text=f'{label}:', font=ctk.CTkFont(size=14)
            ).pack(side='left', padx=15)

            value_label = ctk.CTkLabel(
                status_frame, text=value, font=ctk.CTkFont(size=14), text_color=color
            )
            value_label.pack(side='right', padx=15)

            self.lpt_status_labels[port_num][label] = value_label

    def update_status(self):
        """Update status displays with CustomTkinter widgets."""
        try:
            for port in [0, 1]:
                lpt = getattr(self.e84_controller, f'lpt_{port}')

                # Update state
                state = lpt.state
                color = self._get_state_color(state)
                self.lpt_state_labels[port].configure(text=state, text_color=color)

                # Update status indicators
                self._update_port_status(port)

        except Exception as e:
            logger.error(f'Error updating system status: {e}')

    def _update_port_status(self, port):
        """Update status indicators for a specific port."""
        try:
            lpt = getattr(self.e84_controller, f'lpt_{port}').load_port

            # Update carrier status
            carrier = lpt.get_signal(LPTSignals.CARRIER_PRESENT)
            self.lpt_status_labels[port]['Carrier'].configure(
                text='Present' if carrier else 'Not Present',
                text_color=GUIColors.TEXT_SUCCESS if carrier else GUIColors.TEXT_NORMAL,
            )

            latch = lpt.get_signal(LPTSignals.LATCH_LOCKED)
            self.lpt_status_labels[port]['Latch'].configure(
                text='Locked' if latch else 'Unlocked',
                text_color=GUIColors.TEXT_SUCCESS if latch else GUIColors.TEXT_WARNING,
            )

            # Update ready status
            ready = lpt.get_signal(LPTSignals.LPT_READY)
            self.lpt_status_labels[port]['LPT Ready'].configure(
                text='Ready' if ready else 'Not Ready',
                text_color=GUIColors.TEXT_SUCCESS if ready else GUIColors.TEXT_WARNING,
            )

            # Update error status
            error = lpt.get_signal(LPTSignals.LPT_ERROR)
            self.lpt_status_labels[port]['Error'].configure(
                text='Error' if error else 'None',
                text_color=GUIColors.TEXT_ERROR if error else GUIColors.TEXT_SUCCESS,
            )

        except Exception as e:
            logger.error(f'Error updating port {port} status: {e}')

    def _get_state_color(self, state):
        """Get appropriate color for state display."""
        state_colors = {
            'ERROR_HANDLING': GUIColors.TEXT_ERROR,
            'IDLE_UNAVBL': GUIColors.TEXT_WARNING,
            'IDLE': GUIColors.TEXT_SUCCESS,
            'HO_UNAVBL': GUIColors.TEXT_ERROR,
            'TIMEOUT': GUIColors.TEXT_ERROR,
        }
        return state_colors.get(state, GUIColors.TEXT_TITLE)


class SignalVisualization(StyledFrame):
    """Signal visualization using CustomTkinter."""

    def __init__(self, parent, signals, title=''):
        super().__init__(parent)

        # Title if provided
        if title:
            ctk.CTkLabel(
                self,
                text=title,
                font=ctk.CTkFont(size=12, weight='bold'),
            ).pack(pady=(10, 5), padx=10, anchor='w')

        # Signal indicators container
        self.signals_frame = ctk.CTkFrame(self, fg_color='transparent')
        self.signals_frame.pack(fill='x', expand=True, padx=10, pady=10)

        # Create signal indicators
        self.signal_indicators = {}
        for i, signal in enumerate(signals):
            self._create_signal_indicator(i, signal)

    def _create_signal_indicator(self, index, signal):
        """Create a single signal indicator."""
        frame = ctk.CTkFrame(self.signals_frame, fg_color='transparent')
        frame.grid(row=0, column=index, padx=10)

        # Signal box (using Canvas for consistent look)
        canvas = ctk.CTkCanvas(
            frame, width=30, height=30, bg=GUIColors.BG_PANEL, highlightthickness=0
        )
        canvas.pack(pady=(5, 5), padx=5)

        # Create signal box
        box = canvas.create_rectangle(
            2, 2, 28, 28, fill=GUIColors.SIGNAL_INACTIVE, outline=GUIColors.BORDER
        )

        # Signal label
        ctk.CTkLabel(frame, text=signal, font=ctk.CTkFont(size=12)).pack()

        self.signal_indicators[signal] = (canvas, box)

    def update_signal(self, signal, state):
        """Update signal indicator state for all signals."""
        if signal in self.signal_indicators:
            canvas, box = self.signal_indicators[signal]
            # For every signal, use active color if state is True, else inactive color
            color = GUIColors.SIGNAL_ACTIVE if state else GUIColors.SIGNAL_INACTIVE
            canvas.itemconfig(box, fill=color)


class MessageLog(StyledFrame):
    """Event log widget using a standard Tk Text widget for colored messages."""

    def __init__(self, parent, title='Event Log'):
        super().__init__(parent)

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=16, weight='bold'),
            text_color=GUIColors.TEXT_TITLE,
        ).pack(pady=(10, 5), padx=10, anchor='w')

        self.log_widget = LoguruWidget(
            self,
            show_scrollbar=False,
            color_mode='level',
            max_lines=1000,
            intercept_logging=True,
            fg_color='transparent',
        )
        self.log_widget.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 15))

    def setup_logging(self):
        """Set up the logger to use the LoguruWidget."""
        self.setup_logger(
            self.log_widget,
        )

    def setup_logger(self, widget, level='INFO'):
        """
        Set up the loguru logger to use the custom widget as a sink.

        If intercept_logging is True: interception standard logging messages = ON

        Args:
            widget (LoguruWidget): The widget to use as a sink for log messages.
        """
        logger.remove()
        logger.add(
            widget.sink,
            level=level,
            backtrace=True,
            diagnose=True,
            filter=lambda r: not self.is_debug(r),
        )

        if widget.intercept_logging:
            logging.getLogger().addHandler(LoggingInterceptHandler(widget))
            if level == 'DEBUG':
                logging.getLogger().setLevel(logging.DEBUG)
            if level == 'INFO':
                logging.getLogger().setLevel(logging.INFO)
            if level == 'WARNING':
                logging.getLogger().setLevel(logging.WARNING)
            if level == 'ERROR':
                logging.getLogger().setLevel(logging.ERROR)
            if level == 'CRITICAL':
                logging.getLogger().setLevel(logging.CRITICAL)
        else:
            logging.getLogger().setLevel(logging.INFO)

        logger.info(
            f'GUI Event Log initialized | Level: {self.log_widget.get_logging_level()}'
        )

    def is_debug(self, record):
        return record['level'].no <= 10


class LoadPortSignalControls(StyledFrame):
    """
    A widget that allows the user to select which port (CS_0 or CS_1) is chosen
    and to toggle carrier_present and latch_locked conditions for each port.

    Layout:
    - Top row: Radio buttons for CS_0 and CS_1 (one must be selected)
    - Below: For each port (0 and 1), checkboxes for Carrier Present and Latch Locked.
    """

    def __init__(
        self,
        parent,
        signal_manager: SignalManager,
        e84_controller: E84Controller,
        load_callback,
        unload_callback,
        next_step_callback,
        **kwargs,
    ):
        super().__init__(parent)
        self.signal_manager = signal_manager
        self.e84_controller = e84_controller

        self.load_callback = load_callback
        self.unload_callback = unload_callback
        self.next_step_callback = None
        self.selected_machine = None
        self.selected_port = None

        self.lpt_signal_vars = {}

        lpt_signals = [
            'CARRIER_PRESENT_0',
            'LATCH_LOCKED_0',
            'LPT_ERROR_0',
            'LPT_READY_0',
            'CARRIER_PRESENT_1',
            'LATCH_LOCKED_1',
            'LPT_ERROR_1',
            'LPT_READY_1',
        ]
        for _i, signal in enumerate(lpt_signals):
            self.lpt_signal_vars[signal] = ctk.BooleanVar(
                value=self.signal_manager.get_signal(signal)
            )

        # Create dictionaries for port-specific variables
        self.carrier_vars = {
            0: self.lpt_signal_vars['CARRIER_PRESENT_0'],
            1: self.lpt_signal_vars['CARRIER_PRESENT_1'],
        }
        self.latch_vars = {
            0: self.lpt_signal_vars['LATCH_LOCKED_0'],
            1: self.lpt_signal_vars['LATCH_LOCKED_1'],
        }
        self.ready_vars = {
            0: self.lpt_signal_vars['LPT_READY_0'],
            1: self.lpt_signal_vars['LPT_READY_1'],
        }

        self.error_vars = {
            0: self.lpt_signal_vars['LPT_ERROR_0'],
            1: self.lpt_signal_vars['LPT_ERROR_1'],
        }
        # self.tool_emo_var = ctk.BooleanVar(value=False)

        # Store buttons for enabling/disabling
        self.load_buttons = {}
        self.unload_buttons = {}
        self.next_step_buttons = {}

        self._create_widgets()
        self._monitor_signals()

    def _create_widgets(self):
        """Create port selection and status widgets."""
        # Main container
        main_frame = ctk.CTkFrame(
            self,
            fg_color=GUIColors.BG_PANEL,
            corner_radius=5,
            border_width=1,
            border_color=GUIColors.BORDER,
        )
        main_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

        # Configure columns to be equal width
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Create frame for each port
        for i in range(0, 2):
            # Create LabelFrame for each port
            port_frame = ctk.CTkLabel(
                main_frame,
                text=f'Port CS_{i}',
                fg_color=GUIColors.BG_PANEL,
                font=ctk.CTkFont(size=12, weight='bold'),
            )
            port_frame.grid(row=0, column=i, sticky=ctk.NSEW, padx=5)

            # Status Frame
            status_frame = ctk.CTkFrame(
                port_frame,
                fg_color=GUIColors.BG_PANEL,
            )
            status_frame.grid(row=1, column=0, pady=(0, 10))

            # Status Indicators with consistent spacing
            indicators = [
                (
                    'Carrier Present',
                    self.carrier_vars[i],
                    lambda p=i: self._on_carrier_change(p),
                ),
                (
                    'Latch Locked',
                    self.latch_vars[i],
                    lambda p=i: self._on_latch_change(p),
                ),
                (
                    'LPT Ready',
                    self.ready_vars[i],
                    lambda p=i: self._on_ready_change(p),
                ),
                (
                    'Load Port Error',
                    self.error_vars[i],
                    lambda p=i: self._on_error_change(p),
                ),
            ]

            for text, var, cmd in indicators:
                ctk.CTkCheckBox(
                    status_frame,
                    text=text,
                    variable=var,
                    command=cmd,
                    onvalue=1,
                    offvalue=0,
                ).pack(anchor=ctk.W, pady=2)

            # Control Buttons Frame
            button_frame = ctk.CTkFrame(port_frame)
            button_frame.grid(row=2, column=0, pady=(0, 5))
            button_frame.columnconfigure(0, weight=1)
            button_frame.columnconfigure(1, weight=1)
            button_frame.columnconfigure(2, weight=1)

            # Load Button
            load_btn = ctk.CTkButton(
                button_frame,
                text='Load',
                command=lambda port=i: self._on_load_press(port),
                width=8,
            )
            load_btn.grid(row=0, column=0, padx=2)
            self.load_buttons[i] = load_btn

            # Unload Button
            unload_btn = ctk.CTkButton(
                button_frame,
                text='Unload',
                command=lambda port=i: self._on_unload_press(port),
                width=8,
            )
            unload_btn.grid(row=0, column=1, padx=2)
            self.unload_buttons[i] = unload_btn

            # Next Step Button
            next_step_btn = ctk.CTkButton(
                button_frame,
                text='Next Step',
                command=lambda port=i: self._on_next_step_press(port),
                width=8.2,
            )
            next_step_btn.grid(row=0, column=2, padx=2)
            self.next_step_buttons[i] = next_step_btn

    def capture_port_status(self, port: int) -> LoadPort | None:
        """Capture the current IO status of the specified port."""
        self.selected_machine = (
            self.e84_controller.lpt_0 if port == 0 else self.e84_controller.lpt_1
        )
        lpt_controller = self.selected_machine
        self.selected_port = lpt_controller.load_port
        if lpt_controller is None:
            raise ValueError(f"No machine selected, {port} can't be queryied")

        return self.selected_port.get_port_status()

    def capture_port_info(self, port: int) -> LoadPort | None:
        """Capture the current IO status of the specified port."""
        self.selected_machine = (
            self.e84_controller.lpt_0 if port == 0 else self.e84_controller.lpt_1
        )
        lpt_controller = self.selected_machine
        self.selected_port = lpt_controller.load_port
        if lpt_controller is None:
            raise ValueError(f"No machine selected, {port} can't be queryied")

        return self.selected_port

    def _on_load_press(self, port: int):
        """Handle load button press."""
        self.capture_port_info(port)
        if not self.selected_port.get_signal(LPTSignals.CARRIER_PRESENT):
            self.load_callback(port)
        logger.info(f'Load button pressed on port {port}')

    def _on_unload_press(self, port: int):
        """Handle unload button press."""
        self.capture_port_info(port)
        if self.selected_port.get_signal(LPTSignals.CARRIER_PRESENT):
            self.unload_callback(port)
        logger.info(f'Unload button pressed on port {port}')

    def _on_next_step_press(self, port: int):
        """Handle next step button press."""
        if self.next_step_callback:
            self.next_step_callback(port)

    def _on_carrier_change(self, port: int):
        """Handle carrier present checkbox changes."""
        try:
            var_value = self.carrier_vars[port].get()
            lpt = (
                self.e84_controller.lpt_0.load_port
                if port == 0
                else self.e84_controller.lpt_1.load_port
            )
            lpt.set_signal(LPTSignals.CARRIER_PRESENT, var_value)

        except Exception as e:
            logger.error(f'Error in carrier change for port {port}: {e}')

        logger.debug(f'GUI: Carrier change for port {port}: {var_value}')

    def _on_latch_change(self, port: int):
        try:
            var_value = self.latch_vars[port].get()
            lpt = (
                self.e84_controller.lpt_0.load_port
                if port == 0
                else self.e84_controller.lpt_1.load_port
            )
            lpt.set_signal(LPTSignals.LATCH_LOCKED, var_value)

        except Exception as e:
            logger.error(f'Error in latch change for port {port}: {e}')

        logger.debug(f'GUI: Latch change for port {port}: {var_value}')

    def _on_ready_change(self, port: int):
        var_value = self.ready_vars[port].get()
        lpt = (
            self.e84_controller.lpt_0.load_port
            if port == 0
            else self.e84_controller.lpt_1.load_port
        )
        lpt.set_signal(LPTSignals.LPT_READY, var_value)

        logger.debug(f'GUI: Ready change for port {port}: {var_value}')

    def _on_error_change(self, port: int):
        """Handle error checkbox changes."""
        var_value = self.error_vars[port].get()
        lpt = (
            self.e84_controller.lpt_0.load_port
            if port == 0
            else self.e84_controller.lpt_1.load_port
        )
        lpt.set_signal(LPTSignals.LPT_ERROR, var_value)

        logger.debug(f'GUI: Error change for port {port}: {var_value}')

    # def _on_tool_emo_change(self):
    # 	"""Handle tool EMO checkbox changes."""
    # 	try:
    # 		value = self.tool_emo_var.get()
    # 		self.signal_manager.set_signal("TOOL_EMO", value)
    # 	except Exception as e:
    # 		logger.error(f"Error updating tool EMO status: {e}")

    def reset(self):
        """Reset all controls to initial state."""
        try:
            # for signal, box in self.signal_indicators.items():
            #     self.canvas.itemconfig(box, fill="gray")
            # Reset all variables and signals
            lpt_0 = self.e84_controller.lpt_0.load_port
            lpt_1 = self.e84_controller.lpt_1.load_port

            for port in [0, 1]:
                self.carrier_vars[port].set(False)
                self.latch_vars[port].set(False)
                self.error_vars[port].set(False)

            lpt_0.set_signal(LPTSignals.CARRIER_PRESENT, False)
            lpt_0.set_signal(LPTSignals.LATCH_LOCKED, False)
            lpt_0.set_signal(LPTSignals.LPT_ERROR, False)

            lpt_1.set_signal(LPTSignals.CARRIER_PRESENT, False)
            lpt_1.set_signal(LPTSignals.LATCH_LOCKED, False)
            lpt_1.set_signal(LPTSignals.LPT_ERROR, False)

            # Reset tool EMO
            # self.tool_emo_var.set(False)
            # self.signal_manager.set_signal("TOOL_EMO", False)

        except Exception as e:
            logger.error(f'Error resetting port status: {str(e)}')

    def is_carrier_present(self, port_index):
        """Return the carrier_present state for the given port index."""
        if 0 <= port_index < self.num_ports:
            return self.carrier_vars[port_index].get()
        return False

    def is_latch_locked(self, port_index):
        """Return the latch_locked state for the given port index."""
        if 0 <= port_index < self.num_ports:
            return self.latch_vars[port_index].get()
        return True

    def _monitor_signals(self):
        """Monitor and update GUI based on signal changes."""
        try:
            # Update carrier present status
            for port in range(0, 2):
                lpt = (
                    self.e84_controller.lpt_0
                    if port == 0
                    else self.e84_controller.lpt_1
                )
                if lpt:
                    # Instead of registering the callbacks directly,
                    # we'll just update the UI based on signal values
                    carrier_signal = f'CARRIER_PRESENT_{port}'
                    carrier_value = self.signal_manager.get_signal(carrier_signal)
                    if carrier_value != self.carrier_vars[port].get():
                        self.carrier_vars[port].set(carrier_value)

                    latch_signal = f'LATCH_LOCKED_{port}'
                    latch_value = self.signal_manager.get_signal(latch_signal)
                    if latch_value != self.latch_vars[port].get():
                        self.latch_vars[port].set(latch_value)

                    ready_signal = f'LPT_READY_{port}'
                    ready_value = self.signal_manager.get_signal(ready_signal)
                    if ready_value != self.ready_vars[port].get():
                        self.ready_vars[port].set(ready_value)

                    error_signal = f'LPT_ERROR_{port}'
                    error_value = self.signal_manager.get_signal(error_signal)
                    if error_value != self.error_vars[port].get():
                        self.error_vars[port].set(error_value)

        except Exception as e:
            logger.error(f'Error monitoring signals: {e}')
        finally:
            # Continue monitoring by scheduling another check
            self.after(100, self._monitor_signals)

    def sync_port_status(self):
        """Sync GUI with current signal states."""

        try:
            for port in range(0, 2):
                self.carrier_vars[port].set(
                    self.signal_manager.get_signal(f'CARRIER_PRESENT_{port}')
                )
                self.latch_vars[port].set(
                    self.signal_manager.get_signal(f'LATCH_LOCKED_{port}')
                )
                self.latch_vars[port].set(
                    self.signal_manager.get_signal(f'LPT_READY_{port}')
                )
                self.error_vars[port].set(
                    self.signal_manager.get_signal(f'LPT_ERROR_{port}')
                )

            # self.tool_emo_var.set(self.signal_manager.get_signal("TOOL_EMO"))

        except Exception as e:
            logger.error(f'Error syncing port status: {e}')

    def update_from_signals(self):
        """Update GUI from current signals."""
        self.sync_port_status()


class SignalControlPanel(StyledFrame):
    """
    A panel for controlling AGV signals manually through the GUI.
    Provides checkboxes for toggling individual signals.
    """

    def __init__(
        self,
        parent,
        title,
        callback,
        signal_manager: SignalManager,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.title = title
        self.callback = callback
        self.signal_manager = signal_manager

        # Create a dictionary to track signal states
        self.signal_vars = {}

        # Create the UI
        self._create_widgets()

    def _create_widgets(self):
        """Create all signal control widgets."""
        # Title label
        ctk.CTkLabel(
            self,
            text=self.title,
            font=ctk.CTkFont(size=16, weight='bold'),
            text_color=GUIColors.TEXT_TITLE,
        ).pack(padx=10, pady=(10, 5), anchor='w')

        # Main container for checkboxes
        control_frame = ctk.CTkFrame(self, fg_color='transparent')
        control_frame.pack(fill='x', padx=10, pady=5)

        # Define signal groups
        agv_signals = ['CS_0', 'CS_1', 'VALID', 'TR_REQ', 'BUSY', 'COMPT']

        # Create checkboxes for AGV signals
        for i, signal in enumerate(agv_signals):
            self.signal_vars[signal] = ctk.BooleanVar(
                value=self.signal_manager.get_signal(signal)
            )

            self.checkbox = ctk.CTkCheckBox(
                control_frame,
                text=signal,
                variable=self.signal_vars[signal],
                onvalue=1,
                offvalue=0,
                command=lambda sig=signal: self._on_checkbox_change(sig),
                height=25,
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=3,
            )

            # Arrange in 2 columns
            row = i // 3
            col = i % 3
            self.checkbox.grid(row=row, column=col, padx=10, pady=5, sticky='w')

        # Configure grid for better spacing
        for i in range(3):
            control_frame.grid_columnconfigure(i, weight=1, minsize=80)

    def _on_checkbox_change(self, signal):
        """Handle checkbox state changes."""
        if signal in self.signal_vars:
            value = self.signal_vars[signal].get()
            self.signal_manager.set_signal(signal, value)
        else:
            logger.warning(f'Unknown signal {signal} in signal checkbox change.')

    def reset_signals(self):
        """Reset all signal checkboxes to their default states."""
        for _signal, var in self.signal_vars.items():
            var.set(False)

    def update_from_signals(self):
        """Update checkboxes based on actual signal states."""
        for signal, var in self.signal_vars.items():
            try:
                var.set(self.signal_manager.get_signal(signal))
            except Exception as e:
                logger.error(f'Error updating signal control for {signal}: {e}')
