from scipy.signal import butter, lfilter, iirnotch
from scipy.signal.signaltools import lfilter_zi

def butter_bandpass(lowcut, highcut, order, fs):
    nyq = fs / 2
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    zi = lfilter_zi(b, a)

    return b, a, zi

def butter_bandpass_filter(data, b_band, a_band, zi_band):
    y, zi = lfilter(b_band, a_band, data, axis=0, zi=zi_band)

    return y, zi

def notch(notch_freq, Q, fs):
    nyq = fs/2
    freq = notch_freq / nyq
    b, a = iirnotch(freq, Q)
    zi = lfilter_zi(b, a)

    return b, a, zi

def notch_filter(data, b_notch, a_notch, zi_notch):
    y, zi = lfilter(b_notch, a_notch, data, axis=0, zi=zi_notch)
    
    return y, zi