"""
load_port_factory.py

A factory module that creates the appropriate LoadPort instance
based on Python configuration settings.
"""

import importlib.util
import os

from loguru import logger

# Import both LoadPort implementations
from load_port import LoadPort
from load_port_ascii import LoadPortAscii
from signal_manager import SignalManager


class LoadPortFactory:
    """Factory class for creating LoadPort instances."""

    # Define available interface types
    PARALLEL = 'parallel'
    ASCII = 'ascii'

    @staticmethod
    def create_load_port(
        port_id: int,
        signal_manager: SignalManager,
        interface_type: str = None,
        config_file: str = 'config_e84',
        operating_mode: str = 'prod',
        **kwargs,
    ) -> LoadPort | LoadPortAscii:
        """
        Create a LoadPort instance based on specified interface type or config module.

        Args:
                port_id: The ID of the load port
                signal_manager: SignalManager instance
                interface_type: Explicit interface type, overrides config file if provided
                config_file: Path to Python configuration module
                **kwargs: Additional parameters passed to specific LoadPort implementation

        Returns:
                LoadPort or LoadPortAscii instance
        """
        # Load config.py or another module if specified
        config = {}

        if config_file:
            try:
                # Try to import the config module
                if config_file.endswith('.py'):
                    config_file = config_file[:-3]  # Remove .py extension if present

                # First check if it's a module name that can be simply imported
                try:
                    config = importlib.import_module(config_file)
                    logger.info(f'Loaded configuration from module {config_file}')
                except ImportError:
                    # If that fails, try to load it from a file path
                    if os.path.exists(f'{config_file}.py'):
                        spec = importlib.util.spec_from_file_location(
                            config_file, f'{config_file}.py'
                        )
                        config = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(config)
                        logger.info(f'Loaded configuration from file {config_file}.py')
                    else:
                        logger.error(f'Configuration module {config_file}.py not found')
                        config = {}
            except Exception as e:
                logger.error(f'Failed to load configuration from {config_file}: {e}')
                config = {}

        # Get operating mode from config if not explicitly provided

        if operating_mode is None:
            operating_mode = getattr(config, 'OPERATING_MODE', 'prod')

        # Determine interface type, with explicit parameter taking precedence
        if interface_type is None:
            interface_type = getattr(
                config, 'LOAD_PORT_INTERFACE', LoadPortFactory.PARALLEL
            )

        logger.info(
            f'Creating LoadPort (id={port_id}) with interface type: {interface_type} in {operating_mode} mode'
        )

        # If we're in simulation mode, create a simulated load port

        if operating_mode.lower() == 'sim':
            # In simulation mode, we'll use a simulated LoadPort (needs to be implemented)
            # For now, we'll use the regular LoadPort classes since the hardware is simulated externally
            logger.info(
                'Using regular LoadPort in simulation mode (hardware is simulated externally)'
            )

        ##########################################################
        # TODO: MAKE SURE THIS IS WORKING CORRECTLY
        ##########################################################
        # Extract ASCII serial port and baudrate from configuration if in ASCII mode
        ascii_config = getattr(config, 'ASCII_CONFIG', {}) if config else {}
        # serial_port = kwargs.get(
        #     'serial_port', ascii_config.get('serial_port', '/dev/ttyS0')
        # )
        # baudrate = kwargs.get('baudrate', ascii_config.get('baudrate', 9600))

        # Create the appropriate LoadPort instance
        if interface_type.lower() == LoadPortFactory.ASCII:
            # Use serial port parameters from config or defaults
            serial_port = ascii_config.get(
                'serial_port', kwargs.get('serial_port', '/dev/ttyS0')
            )
            baudrate = ascii_config.get('baudrate', kwargs.get('baudrate', 9600))

            # Create a copy of kwargs for ASCII LoadPort, adding ASCII-specific parameters
            ascii_kwargs = kwargs.copy()
            if 'serial_port' not in ascii_kwargs:
                ascii_kwargs['serial_port'] = serial_port
            if 'baudrate' not in ascii_kwargs:
                ascii_kwargs['baudrate'] = baudrate

            logger.info(
                f'Creating ASCII LoadPort with serial_port={serial_port}, baudrate={baudrate}'
            )
            return LoadPortAscii(
                port_id=port_id, signal_manager=signal_manager, **ascii_kwargs
            )

        else:  # Default to parallel port
            # Create a copy of kwargs without ASCII-specific parameters
            parallel_kwargs = {
                k: v for k, v in kwargs.items() if k not in ['serial_port', 'baudrate']
            }

            logger.info('Creating Parallel LoadPort')
            return LoadPort(
                port_id=port_id, signal_manager=signal_manager, **parallel_kwargs
            )
