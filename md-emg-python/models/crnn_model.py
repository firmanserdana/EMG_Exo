import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from einops.layers.torch import Rearrange

class LayerPadding(nn.Module):
    def __init__(self, padding, mode='constant', value=0):
        super(LayerPadding, self).__init__()
        self.padding = padding  # Padding as a tuple (left, right, top, bottom)
        self.mode = mode
        self.value = value

    def forward(self, x):
        return F.pad(x, self.padding, mode=self.mode, value=self.value)

class CRNNModel(nn.Module):
    def __init__(self, input_dim, time_conv_size, time_stride, num_time_filters, hidden_size, num_layers, num_output, drop_prob=0.2):
        super().__init__()
        self.hidden_size = hidden_size
        self.n_layers = num_layers

        self.time_conv = nn.Sequential(
            Rearrange('b e w h -> b e h w'),
            # convolution over time
            nn.Conv2d(
                in_channels=1, 
                out_channels=num_time_filters, 
                kernel_size=(1, time_conv_size), 
                stride=(1, time_stride)
            ), 
            # add padding to always include the last conv indendently from the input/conv size
            # LayerPadding((0, time_conv_size-1, 0, 0), 'constant', value=0), 
            nn.BatchNorm2d(num_time_filters),
            nn.ELU(),
            Rearrange('b (h) c (w) -> b (h w) c')
        )

        self.lstm = nn.LSTM(input_dim, hidden_size, num_layers, batch_first=True, dropout=drop_prob) # batch_first=True means input shape (batch_size, seq_len, features)
        self.fc = nn.Linear(hidden_size, num_output)

        self.h, self.c = None, None

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def forward(self, x, stateless_mode=True):
        """
        x:                  Neural data tensor of shape (batch_size, sequence_length, num_channels)
        predictions:        If true, it stores the hidden states and cell states for each timestep in the sequence.
        return_all_steps:   If true, returns velocities from all timesteps in the sequence. If false, only returns the
                            last step in the sequence.
        """

        if stateless_mode or self.h is None:
            self.init_hidden(batch_size=x.shape[0]) 

        time_conv = self.time_conv(x.unsqueeze(1))  # add channel dimension for conv layer, shape (batch_size, 1, sequence_length, num_channels)

        out,(h,c) = self.lstm(time_conv, (self.h,self.c))

        out = self.fc(out[:, -1])  # use last prediction in the sequence for fc output

        if not stateless_mode:
            self.h = h
            self.c = c 

        return out

    def init_hidden(self, batch_size):
        self.h = torch.zeros(self.n_layers, batch_size, self.hidden_size).to(self.device)
        self.c = torch.zeros(self.n_layers, batch_size, self.hidden_size).to(self.device)