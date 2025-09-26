from transformers import PretrainedConfig

class LMConfig(PretrainedConfig):
    def __init__(self, dim=512, n_layers=8, max_seq_len=512, use_moe=False, **kwargs):
        super().__init__(**kwargs)
        self.dim = dim
        self.n_layers = n_layers
        self.max_seq_len = max_seq_len
        self.use_moe = use_moe 