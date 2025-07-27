import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class LSTMModel(nn.Module):
    def __init__(self, input_dim, hidden_size, num_output, num_layers, drop_prob=0.2):
        super().__init__()
        self.hidden_size = hidden_size
        self.n_layers = num_layers

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

        out,(h,c) = self.lstm(x, (self.h,self.c))

        out = self.fc(out[:, -1])  # use last prediction in the sequence for fc output

        if not stateless_mode:
            self.h = h
            self.c = c 

        return out

    def init_hidden(self, batch_size):
        self.h = torch.zeros(self.n_layers, batch_size, self.hidden_size).to(self.device)
        self.c = torch.zeros(self.n_layers, batch_size, self.hidden_size).to(self.device)