#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EMG Acquisition Selection and Management
This module provides a unified interface for selecting between different EMG acquisition systems.
"""

import os
import argparse
import time
import logging

# Import EMG acquisition modules
from emg_acquisition import SessantaquatroEMG
from delsys_trigno_emg import DelsysTrignoEMG
from ini import EMG_CONFIG, TRIGNO_CONFIG, logger

# Supported systems
SUPPORTED_EMG_SYSTEMS = ["sessantaquatro", "delsys_trigno", "simulation"]


def get_emg_system(system_type="sessantaquatro", **kwargs):
    """Factory function to get the appropriate EMG system based on type.
    
    Args:
        system_type (str): Type of EMG system to use
            Options: "sessantaquatro", "delsys_trigno", "simulation"
        **kwargs: Additional keyword arguments for the specific EMG system
    
    Returns:
        object: Initialized EMG acquisition object
    """
    if system_type == "sessantaquatro":
        logger.info("Using Sessantaquatro EMG system")
        return SessantaquatroEMG(
            port=kwargs.get("port", EMG_CONFIG["port"]),
            baudrate=kwargs.get("baudrate", EMG_CONFIG["baudrate"])
        )
    elif system_type == "delsys_trigno":
        logger.info("Using Delsys Trigno EMG system")
        return DelsysTrignoEMG(
            host=kwargs.get("host", TRIGNO_CONFIG["host"]),
            command_port=kwargs.get("command_port", TRIGNO_CONFIG["command_port"]),
            emg_port=kwargs.get("emg_port", TRIGNO_CONFIG["emg_port"]),
            aux_port=kwargs.get("aux_port", TRIGNO_CONFIG["aux_port"])
        )
    elif system_type == "simulation":
        logger.info("Using EMG simulation")
        # Use Sessantaquatro for simulation capability
        emg = SessantaquatroEMG()
        # Flag as simulation mode
        emg.is_connected = True
        return emg
    else:
        raise ValueError(f"Unsupported EMG system type: {system_type}")


def get_system_type_from_args():
    """Parse command line arguments for EMG system type.
    
    Returns:
        str: EMG system type
        dict: Additional arguments for the EMG system
    """
    parser = argparse.ArgumentParser(description="EMG Acquisition System Selection")
    parser.add_argument("--emg-system", choices=SUPPORTED_EMG_SYSTEMS, 
                        default="sessantaquatro", help="EMG acquisition system to use")
    
    # Sessantaquatro arguments
    parser.add_argument("--port", type=str, help="COM port for Sessantaquatro board")
    parser.add_argument("--baudrate", type=int, help="Baudrate for Sessantaquatro board")
    
    # Delsys Trigno arguments
    parser.add_argument("--host", type=str, help="Host IP for Delsys Trigno system")
    parser.add_argument("--command-port", type=int, help="Command port for Trigno system")
    parser.add_argument("--emg-port", type=int, help="EMG data port for Trigno system")
    parser.add_argument("--aux-port", type=int, help="Auxiliary data port for Trigno system")
    
    args = parser.parse_args()
    
    # Extract relevant arguments based on system type
    system_args = {}
    if args.emg_system == "sessantaquatro":
        if args.port:
            system_args["port"] = args.port
        if args.baudrate:
            system_args["baudrate"] = args.baudrate
    elif args.emg_system == "delsys_trigno":
        if args.host:
            system_args["host"] = args.host
        if args.command_port:
            system_args["command_port"] = args.command_port
        if args.emg_port:
            system_args["emg_port"] = args.emg_port
        if args.aux_port:
            system_args["aux_port"] = args.aux_port
    
    return args.emg_system, system_args


if __name__ == "__main__":
    # Simple test script
    system_type, system_args = get_system_type_from_args()
    
    print(f"Testing {system_type} EMG system...")
    try:
        emg = get_emg_system(system_type, **system_args)
        
        # If using simulation, we'll generate simulated data
        if system_type == "simulation":
            print("Generating simulated data...")
            simulated_data = emg.simulate_data(duration=2.0)
            print(f"Simulated data shape: {simulated_data.shape}")
            print(f"Mean: {simulated_data.mean():.2f}, Std: {simulated_data.std():.2f}")
        else:  # Real hardware
            if emg.connect():
                print(f"Connected to {system_type} EMG system")
                
                if emg.configure_board():
                    print("System configured")
                    
                    print("Starting streaming...")
                    if emg.start_streaming():
                        print("Streaming started")
                        
                        print("Acquiring data for 5 seconds...")
                        for i in range(10):
                            data = emg.get_data(blocking=True, timeout=1.0)
                            if data is not None:
                                print(f"Got data chunk: {data.shape}, mean={data.mean():.2f}, std={data.std():.2f}")
                            else:
                                print("No data received")
                        
                        print("Stopping streaming...")
                        emg.stop_streaming()
                        
                emg.disconnect()
                print(f"Disconnected from {system_type} EMG system")
                
    except Exception as e:
        print(f"Error: {str(e)}")
