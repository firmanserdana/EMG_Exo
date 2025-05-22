#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This package provides classes for decoding EMG signals into gestures.
"""

from emg_exo.core.decoder.base import BaseEMGDecoder
from emg_exo.core.decoder.decoder import EMGDecoder

__all__ = ['BaseEMGDecoder', 'EMGDecoder']