"""
main.py - Main entry point for E84 controller

Supports multiple operating modes:
- Production mode (prod): All signals use real hardware
- Emulation mode (em): E84 signals use real hardware, LPT signals are simulated
- Simulation mode (sim): All signals are simulated (no hardware)

It also supports different interface types:
- Parallel: Uses dual DIO cards for E84 and LPT signals
- ASCII: Uses a single DIO card for E84 signals and serial for LPT
"""

import argparse
import importlib.util
import os
import signal
import sys
import threading
import time

from loguru import logger

# Import E84 controller components
from callback_manager import CallbackManager

# Import hardware interface factory - handles all hardware modes
from hardware_interface import create_hardware_interface
from signal_manager import SignalManager


def setup_logging(log_level='INFO'):
    """Configure logging for the application"""
    logger.remove()  # Remove default handler

    # Add console handler with custom format
    logger.add(
        sys.stdout,
        format='<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>',
        level=log_level,
        colorize=True,
    )

    # Add file handler
    logger.add(
        'e84_controller.log',
        rotation='10 MB',
        retention='1 week',
        compression='zip',
        level='DEBUG',
        format='{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}',
    )


def hardware_monitor_thread(controller, bridge, running_event, polling_interval=0.1):
    """
    Background thread to handle hardware monitoring and polling
    while the GUI runs in the main thread

    Args:
        controller: The E84 controller
        bridge: The E84 signal bridge
        running_event: Event to signal when the thread should stop
        polling_interval: Interval in seconds for polling cycle
    """
    logger.info(
        f'Hardware monitor thread started with polling interval: {polling_interval}s'
    )

    try:
        while running_event.is_set():
            # Poll E84 handshake cycle
            controller.poll_cycle()

            # Sleep to prevent CPU hogging
            time.sleep(polling_interval)

    except Exception as e:
        logger.exception(f'Error in hardware monitor thread: {e}')

    logger.info('Hardware monitor thread stopped')


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='E84 Controller')

    parser.add_argument(
        '--config',
        dest='config_file',
        help='Path to Python configuration module (without .py extension)',
        default='config_e84',
    )

    parser.add_argument(
        '--mode',
        dest='operating_mode',
        choices=['production', 'prod', 'emulation', 'em', 'simulation', 'sim'],
        help='Operating mode (production/prod, emulation/em, or simulation/sim)',
        default=None,
    )

    parser.add_argument(
        '--interface',
        dest='interface_type',
        choices=['parallel', 'ascii'],
        help='Load port interface type (overrides config file)',
        default=None,
    )

    parser.add_argument(
        '--serial-port',
        dest='serial_port',
        help='Serial port for ASCII interface (if used)',
        default=None,
    )

    parser.add_argument(
        '--log-level',
        dest='log_level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level',
        default=None,
    )

    return parser.parse_args()


def load_config_file(module_name):
    """
    Load a Python configuration module either by import or from file.

    Args:
        module_name: Module name or path (without .py extension)

    Returns:
        Module object or None if loading failed
    """
    try:
        # First try importing as a regular module
        try:
            config = importlib.import_module(module_name)
            logger.info(f'Loaded configuration from module {module_name}')
            return config
        except ImportError:
            # If importing fails, try loading from file path
            if os.path.exists(f'{module_name}.py'):
                spec = importlib.util.spec_from_file_location(
                    module_name, f'{module_name}.py'
                )
                config = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config)
                logger.info(f'Loaded configuration from file {module_name}.py')
                return config
            else:
                logger.error(f'Configuration module {module_name}.py not found')
                return None
    except Exception as e:
        logger.error(f'Failed to load configuration from {module_name}: {e}')
        return None


def main():
    """Main function to set up and run the E84 controller with hardware interface and GUI"""
    args = parse_arguments()

    # Load the configuration module
    config = load_config_file(args.config_file)

    # If config couldn't be loaded, generate a default one and try again
    if config is None:
        logger.warning(
            f"Could not load config module '{args.config_file}', generating default..."
        )

        # Try to create a default config file
        # TODO: Implement default config generation if needed
        logger.error('Failed to load default configuration, exiting.')
        sys.exit(1)

    # Set up logging using config (or override from args)
    log_level = (
        args.log_level if args.log_level else getattr(config, 'LOG_LEVEL', 'INFO')
    )
    setup_logging(log_level)

    # Determine which modes to use (command line args override config)
    operating_mode = args.operating_mode or getattr(
        config, 'OPERATING_MODE', 'production'
    )
    interface_type = args.interface_type or getattr(
        config, 'LOAD_PORT_INTERFACE', 'parallel'
    )

    # Normalize operating mode (support short forms)
    if operating_mode.lower() in ['prod']:
        operating_mode = 'production'
    elif operating_mode.lower() in ['emu', 'em']:
        operating_mode = 'emulation'
    elif operating_mode.lower() in ['sim']:
        operating_mode = 'simulation'

    logger.info(
        f'Starting E84 controller in {operating_mode} mode with {interface_type} interface'
    )

    # Create shared components
    signal_manager = SignalManager()
    callback_manager = CallbackManager()

    # Get polling interval from config
    polling_interval = getattr(config, 'POLLING_INTERVAL', 0.1)

    running_event = threading.Event()
    running_event.set()

    hardware = None
    bridge = None
    monitor_thread = None

    try:
        # Create hardware interface using factory, based on operating mode
        hardware = create_hardware_interface(
            operating_mode=operating_mode,
            signal_manager=signal_manager,
            callback_manager=callback_manager,
            config=config,
            polling_interval=polling_interval,
        )

        # Import the bridge module with unified interface
        from signal_bridge import create_bridge

        # Create signal bridge
        bridge = create_bridge(
            signal_manager=signal_manager,
            callback_manager=callback_manager,
            hardware_interface=hardware,
            operating_mode=operating_mode,
        )

        # Import and create the E84 controller
        # All modes can use the same controller implementation
        from e84_controller import E84Controller

        logger.info('Creating E84 controller')
        e84_controller = E84Controller(
            signal_manager=signal_manager,
            config_file=args.config_file,
            interface_type=interface_type,
            operating_mode=operating_mode,
            serial_port=args.serial_port,
        )

        # Initialize the signal bridge (this starts hardware monitoring)
        logger.info('Initializing signal bridge')
        bridge.initialize()

        # Register signal handlers for clean shutdown
        def signal_handler(sig, frame):
            logger.info('Received shutdown signal, cleaning up...')
            running_event.clear()
            if monitor_thread:
                monitor_thread.join(timeout=2.0)
            if bridge:
                bridge.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start hardware monitor thread
        logger.info('Starting hardware monitor thread')
        monitor_thread = threading.Thread(
            target=hardware_monitor_thread,
            args=(e84_controller, bridge, running_event, polling_interval),
            daemon=True,
        )
        monitor_thread.start()

        # Import the GUI factory function
        from gui import create_gui

        show_message_log = getattr(config, 'SHOW_MESSAGE_LOG', 'False').lower() in [
            'yes',
            'y',
            'False',
            False,
            True,
            'True',
            'no',
            'n',
            '1',
        ]

        logger.info(
            f'Starting E84 GUI in {operating_mode} mode (message log: {"enabled" if show_message_log else "disabled"})'
        )

        # Create and run the GUI application in the main thread
        app = create_gui(
            signal_manager=signal_manager,
            e84_controller=e84_controller,
            show_message_log=show_message_log,
        )

        # Add mode indicator to GUI title
        app.title(
            f'E84 Controller GUI - {operating_mode.capitalize()} Mode | {interface_type.capitalize()} Interface'
        )

        # Register GUI cleanup callback
        gui_cleanup = app.cleanup

        def all_cleanup():
            logger.info('GUI cleanup triggered, shutting down hardware interface...')
            running_event.clear()
            if monitor_thread:
                monitor_thread.join(timeout=2.0)
            if bridge:
                bridge.shutdown()
            # Call the original cleanup
            gui_cleanup()

        app.cleanup = all_cleanup

        # Start the GUI event loop
        logger.info(
            f'E84 controller started in {operating_mode} mode with {interface_type} interface'
        )
        app.mainloop()  # This blocks until the GUI is closed

    except Exception as e:
        logger.exception(f'Error in E84 controller: {e}')
        running_event.clear()
        if monitor_thread:
            monitor_thread.join(timeout=2.0)
        if bridge:
            bridge.shutdown()
        sys.exit(1)


if __name__ == '__main__':
    main()
