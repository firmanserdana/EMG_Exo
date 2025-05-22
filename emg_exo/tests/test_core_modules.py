#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Basic test framework for EMG_Exo package.
"""

import unittest
import numpy as np


class TestEMGAcquisition(unittest.TestCase):
    """Tests for EMG acquisition module."""
    
    def test_emg_system_creation(self):
        """Test that EMG systems can be created."""
        from emg_exo.core.acquisition import create_emg_system
        
        # Test simulation system
        system = create_emg_system("simulation")
        self.assertIsNotNone(system)
        
        # Test system interface
        self.assertTrue(hasattr(system, 'connect'))
        self.assertTrue(hasattr(system, 'disconnect'))
        self.assertTrue(hasattr(system, 'read'))
    
    def test_simulation_data(self):
        """Test that simulated data is valid."""
        from emg_exo.core.acquisition import create_emg_system
        
        # Create simulation system
        system = create_emg_system("simulation")
        system.connect()
        
        # Read data
        data = system.read()
        
        # Verify data properties
        self.assertIsNotNone(data)
        self.assertTrue(isinstance(data, np.ndarray))
        self.assertEqual(data.ndim, 1)  # Expect single-channel or flattened
        
        # Disconnect
        system.disconnect()


class TestEMGProcessing(unittest.TestCase):
    """Tests for EMG processing module."""
    
    def test_processor_creation(self):
        """Test that EMG processor can be created."""
        from emg_exo.core.processing import EMGProcessor
        
        processor = EMGProcessor()
        self.assertIsNotNone(processor)
        
        # Test processor interface
        self.assertTrue(hasattr(processor, 'preprocess'))
        self.assertTrue(hasattr(processor, 'extract_features'))
    
    def test_basic_preprocessing(self):
        """Test basic preprocessing functionality."""
        from emg_exo.core.processing import EMGProcessor
        
        processor = EMGProcessor()
        
        # Create test data
        test_data = np.random.randn(1000)
        
        # Process data
        processed_data = processor.preprocess(test_data)
        
        # Verify processed data
        self.assertIsNotNone(processed_data)
        self.assertTrue(isinstance(processed_data, np.ndarray))
        self.assertEqual(processed_data.shape, test_data.shape)


class TestEMGDecoder(unittest.TestCase):
    """Tests for EMG decoder module."""
    
    def test_decoder_creation(self):
        """Test that EMG decoder can be created."""
        from emg_exo.core.decoder import EMGDecoder
        
        decoder = EMGDecoder()
        self.assertIsNotNone(decoder)
        
        # Test decoder interface
        self.assertTrue(hasattr(decoder, 'classify'))
        self.assertTrue(hasattr(decoder, 'extract_classification_features'))


if __name__ == '__main__':
    unittest.main()
