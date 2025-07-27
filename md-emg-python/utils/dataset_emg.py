import torch
from torch.utils.data import Dataset

# Define a custom PyTorch Dataset
class DatasetEMG(Dataset):
    def __init__(self, raw_features=None, freq_features=None, labels=None, sequence_length=1, device=None):
        """
        Initializes the DatasetEMG.

        Parameters:
        - raw_features (np.ndarray): Raw signal features (can be rms, mav, raw, etc..) of shape (n_samples, n_channels), None if not used.
        - freq_features (np.ndarray): Scaled frequency features of shape (n_samples, n_channels, n_bands), None if not used.
        - labels (np.ndarray): Grasp labels of shape (n_samples, n_kinematics).
        - sequence_length (int): The length of each sequence.
        - device (torch.device): The device to use for storing tensors.
        """

        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = device
        
        if raw_features is None and freq_features is None:
            raise ValueError("At least one of raw_features or freq_features must be provided.")

        if raw_features is not None and freq_features is not None:
            raw_features = torch.tensor(raw_features, dtype=torch.float32) # Shape: (n_times, n_channels)
            freq_features = torch.tensor(freq_features, dtype=torch.float32) # Shape: (n_times, n_channels, n_bands)
            freq_features = torch.flatten(freq_features, start_dim=1, end_dim=2) # flattening channels and bands together

            self.features = torch.cat((raw_features, freq_features), dim=1) # Shape: (n_times, n_channels + n_channels * n_bands)
        elif raw_features is not None:
            self.features = torch.tensor(raw_features, dtype=torch.float32) # Shape: (n_times, n_channels)
        else:
            self.features = torch.tensor(freq_features, dtype=torch.float32).permute(1,0,2) # Shape: (n_times, n_channels, n_bands)

        # creating the sequence and storing features and labels variable
        if freq_features is not None:
            self.features = self.features.unfold(0, sequence_length, 1) # Shape: (n_times, sequence_length, n_channels, n_bands)
            self.features = self.features.permute(0, 3, 1, 2) # Shape: (n_times, n_bands, sequence_length, n_channels)
        else:
            self.features = self.features.unfold(0, sequence_length, 1) # Shape: (n_times, n_channels, sequence_length)
            
            # handle case of raw features for which the sequence has to be merged
            if self.features.ndim > 3:
                self.features = self.features.permute(0, 3, 1, 2)
                self.features = self.features.reshape(self.features.shape[0], self.features.shape[1]*self.features.shape[2], -1) # Shape: (n_times, sequence_length, n_channels)
            else:
                self.features = self.features.permute(0, 2, 1) # Shape: (n_times, sequence_length, n_channels)
        
        if labels is not None:
            self.labels = torch.tensor(labels)[sequence_length-1:] # Shape: (n_times, n_kinematics, n_samples)
        else:
            self.labels = None

    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        output = {
            'neural_features': self.features[idx]
        }    

        if self.labels is not None:
            output['labels'] = self.labels[idx]

        return output