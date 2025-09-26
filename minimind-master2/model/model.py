import torch
import torch.nn as nn
from transformers import PreTrainedModel, PretrainedConfig

class MiniMindConfig(PretrainedConfig):
    def __init__(self, dim=512, n_layers=8, max_seq_len=512, use_moe=False, **kwargs):
        super().__init__(**kwargs)
        self.dim = dim
        self.n_layers = n_layers
        self.max_seq_len = max_seq_len
        self.use_moe = use_moe

class MiniMindLM(PreTrainedModel):
    config_class = MiniMindConfig
    
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        
        # 简化版模型结构
        self.embedding = nn.Embedding(50000, config.dim)  # 假设词表大小为50000
        self.transformer_layers = nn.ModuleList([
            nn.TransformerEncoderLayer(d_model=config.dim, nhead=8)
            for _ in range(config.n_layers)
        ])
        self.output = nn.Linear(config.dim, 50000)  # 输出层
        
    def forward(self, input_ids):
        x = self.embedding(input_ids)
        
        # 应用transformer层
        for layer in self.transformer_layers:
            x = layer(x)
            
        logits = self.output(x)
        return logits
        
    def generate(self, input_ids, max_new_tokens=512, temperature=0.85, top_p=0.85, 
                eos_token_id=None, pad_token_id=None, **kwargs):
        batch_size = input_ids.shape[0]
        generated = input_ids.clone()
        
        for _ in range(max_new_tokens):
            outputs = self(generated)
            next_token_logits = outputs[:, -1, :] / temperature
            
            # 应用top_p采样
            sorted_logits, sorted_indices = torch.sort(next_token_logits, descending=True)
            cumulative_probs = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)
            sorted_indices_to_remove = cumulative_probs > top_p
            sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
            sorted_indices_to_remove[..., 0] = 0
            
            for batch_idx in range(batch_size):
                indices_to_remove = sorted_indices[batch_idx][sorted_indices_to_remove[batch_idx]]
                next_token_logits[batch_idx][indices_to_remove] = float('-inf')
            
            probs = torch.softmax(next_token_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            
            generated = torch.cat([generated, next_token], dim=1)
            
            if eos_token_id is not None and (next_token == eos_token_id).any():
                break
                
        return generated 