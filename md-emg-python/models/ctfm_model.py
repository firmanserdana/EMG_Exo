import numpy as np
import math
import torch.nn as nn
import torch.nn.functional as F
import torch

from torch import Tensor 
from einops import rearrange
from einops.layers.torch import Rearrange

# conformer code inspiration and partial reuse from: https://github.com/eeyhsong/EEG-Conformer

class LayerPadding(nn.Module):
    def __init__(self, padding, mode='constant', value=0):
        super(LayerPadding, self).__init__()
        self.padding = padding  # Padding as a tuple (left, right, top, bottom)
        self.mode = mode
        self.value = value

    def forward(self, x):
        return F.pad(x, self.padding, mode=self.mode, value=self.value)

# Convolution module
# using conv to capture local features, instead of position embedding.
class PatchEmbedding(nn.Module):
    def __init__(self, emb_size, time_conv_size, drop_p):
        super().__init__()

        self.shallownet = nn.Sequential(
            Rearrange('b e w h -> b e h w'),
            # convolution over time
            nn.Conv2d(in_channels=1, out_channels=emb_size, kernel_size=(1, time_conv_size), stride=(1, 1)), 
            # add padding to always include the last conv indendently from the input/conv size
            LayerPadding((0, time_conv_size-1, 0, 0), 'constant', value=0), 
            nn.BatchNorm2d(emb_size),
            nn.ELU()
        )

        self.shallownet.add_module('maxpool', nn.MaxPool2d(kernel_size=(1, time_conv_size), stride=(1, time_conv_size)))
        self.shallownet.add_module('dropout', nn.Dropout(drop_p))

        self.projection = nn.Sequential(
            Rearrange('b e (h) (w) -> b (h w) e'),
        )

    def forward(self, x: Tensor) -> Tensor:
        out = self.shallownet(x.float())
        out = self.projection(out)

        return out

class MultiHeadAttention(nn.Module):
    def __init__(self, emb_size, num_heads, dropout):
        super().__init__()
        self.emb_size = emb_size
        self.num_heads = num_heads
        self.keys = nn.Linear(emb_size, emb_size)
        self.queries = nn.Linear(emb_size, emb_size)
        self.values = nn.Linear(emb_size, emb_size)
        self.att_drop = nn.Dropout(dropout)
        self.projection = nn.Linear(emb_size, emb_size)

    def forward(self, x: Tensor, mask: Tensor = None) -> Tensor:
        queries = rearrange(self.queries(x), "b n (h d) -> b h n d", h=self.num_heads)
        keys = rearrange(self.keys(x), "b n (h d) -> b h n d", h=self.num_heads)
        values = rearrange(self.values(x), "b n (h d) -> b h n d", h=self.num_heads)
        energy = torch.einsum('bhqd, bhkd -> bhqk', queries, keys)  
        if mask is not None:
            fill_value = torch.finfo(torch.float32).min
            energy.mask_fill(~mask, fill_value)

        scaling = self.emb_size ** (1 / 2)
        att = F.softmax(energy / scaling, dim=-1)
        att = self.att_drop(att)
        out = torch.einsum('bhal, bhlv -> bhav ', att, values)
        out = rearrange(out, "b h n d -> b n (h d)")
        out = self.projection(out)

        return out

class ResidualAdd(nn.Module):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def forward(self, x, **kwargs):
        res = x
        x = self.fn(x, **kwargs)
        x += res
        return x

class FeedForwardBlock(nn.Sequential):
    def __init__(self, emb_size, expansion, drop_p):
        super().__init__(
            nn.Linear(emb_size, expansion * emb_size),
            nn.GELU(),
            nn.Dropout(drop_p),
            nn.Linear(expansion * emb_size, emb_size),
        )

class GELU(nn.Module):
    def forward(self, input: Tensor) -> Tensor:
        return input*0.5*(1.0+torch.erf(input/math.sqrt(2.0)))

class TransformerEncoderBlock(nn.Sequential):
    def __init__(self,
                 emb_size,
                 num_heads=10,
                 drop_p=0.5,
                 forward_expansion=4,
                 forward_drop_p=0.5):
        super().__init__(
            ResidualAdd(nn.Sequential(
                nn.LayerNorm(emb_size),
                MultiHeadAttention(emb_size, num_heads, drop_p),
                nn.Dropout(drop_p)
            )),
            ResidualAdd(nn.Sequential(
                nn.LayerNorm(emb_size),
                FeedForwardBlock(emb_size, expansion=forward_expansion, drop_p=forward_drop_p),
                nn.Dropout(drop_p)
            )
            ))

class TransformerEncoder(nn.Module):
    def __init__(self, num_layers, emb_size, num_heads, dropout=0.25, use_cls_token=True):
        super().__init__()

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=emb_size, 
            nhead=num_heads,            
            dropout=dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        self.use_cls_token = use_cls_token

        if self.use_cls_token:
            self.cls_token = nn.Parameter(torch.zeros(1, 1, emb_size))

    def forward(self, x):
        if self.use_cls_token:
            # Add CLS token
            batch_size = x.size(0)

            cls_token = self.cls_token.expand(batch_size, -1, -1)  # Expand for batch size
            x = torch.cat((cls_token, x), dim=1)  # Prepend CLS token

        x = self.transformer_encoder(x)
        
        return x


class ClassificationHead(nn.Sequential):
    def __init__(self, in_size, n_classes, use_cls_token=True):
        super().__init__()

        self.use_cls_token = use_cls_token
        
        if self.use_cls_token:
            self.fc = nn.Linear(in_size, n_classes)
        else:
            self.fc = nn.Sequential(
                nn.Linear(in_size, 256),
                nn.ELU(),
                nn.Linear(256, n_classes)
            )

    def forward(self, x):
        if self.use_cls_token:
            x = x[:, 0, :] # take the cls token's output
        else:
            x = x.contiguous().view(x.size(0), -1) # flattening the input

        out = self.fc(x)

        return out

class CTFMModel(nn.Module):
    def __init__(self, 
                 emb_size=40, 
                 num_layers=6, 
                 num_heads=10, 
                 time_conv_size=5, 
                 n_out=4, 
                 seq_length=20, 
                 num_channels=16,
                 use_cls_token=False,
                 dropout=0.25):
        super(CTFMModel, self).__init__()
               
        self.patch_embedding = PatchEmbedding(emb_size=emb_size, time_conv_size=time_conv_size, drop_p=dropout)
        self.tf_encoder = TransformerEncoder(num_layers=num_layers, emb_size=emb_size, num_heads=num_heads, use_cls_token=use_cls_token)

        if use_cls_token:
            self.tf_out_size = emb_size
        else:
            self.tf_out_size = self.calculate_tf_output_size(
                sequence_length=seq_length, time_conv_size=time_conv_size,
                num_channels=num_channels, emb_size=emb_size
            )

        self.fc_classification = ClassificationHead(in_size=self.tf_out_size, n_classes=n_out, use_cls_token=use_cls_token)
    
    def forward(self, x):
        x = x.unsqueeze(1)

        out = self.patch_embedding(x)
        out = self.tf_encoder(out)
        out = self.fc_classification(out)

        return out

    def calculate_tf_output_size(self, sequence_length, time_conv_size, num_channels, emb_size):
        return int(np.floor(sequence_length/time_conv_size) * num_channels * emb_size)