import torch
import torch.nn as nn
import torch.nn.functional as F

class PositionalEncoding(nn.Module):
    def __init__(self, embed_dim, max_len=5000):
        super(PositionalEncoding, self).__init__()
        encoding = torch.zeros(max_len, embed_dim)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, embed_dim, 2).float() * -(torch.log(torch.tensor(10000.0)) / embed_dim))

        encoding[:, 0::2] = torch.sin(position * div_term)
        encoding[:, 1::2] = torch.cos(position * div_term)
        encoding = encoding.unsqueeze(0)  # Add batch dimension

        self.register_buffer('encoding', encoding)

    def forward(self, x):
        seq_len = x.size(1)
        return x + self.encoding[:, :seq_len, :].to(x.device)

class AttentionPooling(nn.Module):
    def __init__(self, hidden_dim):
        super(AttentionPooling, self).__init__()
        self.attention = nn.Linear(hidden_dim, 1)

    def forward(self, hidden_states):
        # hidden_states shape: (batch_size, seq_length, hidden_dim)
        weights = self.attention(hidden_states)  # shape: (batch_size, seq_length, 1)
        weights = torch.softmax(weights, dim=1)
        pooled = (hidden_states * weights).sum(dim=1)
        return pooled

class TFMModel(nn.Module):
    def __init__(self, input_dim, embed_dim, num_heads, num_layers, num_classes, max_len, use_cls_token=True, dropout=0.25):
        super(TFMModel, self).__init__()
        self.embed_dim = embed_dim
        self.use_cls_token = use_cls_token

        # Input embedding layer
        self.embedding = nn.Linear(input_dim, embed_dim)

        # Positional encoding
        self.positional_encoding = PositionalEncoding(embed_dim, max_len)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim, 
            nhead=num_heads,            
            dropout=dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        if self.use_cls_token:
            self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))

        # Classification head
        if self.use_cls_token:
            self.fc = nn.Linear(embed_dim, num_classes)
        else:
            self.attention_pooling = AttentionPooling(embed_dim)
            self.fc = nn.Linear(embed_dim, num_classes)

    def forward(self, x):
        batch_size = x.size(0)

        # Embed input
        x = self.embedding(x)

        # Add positional encoding
        x = self.positional_encoding(x)

        if self.use_cls_token:
            # Add CLS token
            cls_token = self.cls_token.expand(batch_size, -1, -1)  # Expand for batch size
            x = torch.cat((cls_token, x), dim=1)  # Prepend CLS token

        # Pass through transformer
        tokens = self.transformer_encoder(x)

        if self.use_cls_token:
            # Extract CLS token representation
            out_tokens = tokens[:, 0, :]  # Take the CLS token's output
        else:
            out_tokens = self.attention_pooling(x)

        # Classification
        output = self.fc(out_tokens)
        
        return output