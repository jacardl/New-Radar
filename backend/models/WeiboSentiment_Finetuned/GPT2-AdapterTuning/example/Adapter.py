import torch
import torch.nn as nn

class AdapterLayer(nn.Module):
    def __init__(self, input_size, adapter_size):
        super(AdapterLayer, self).__init__()
        # ç¬¬ä¸ä¸ªå¨è¿æ¥å±éç»?
        self.down_project = nn.Linear(input_size, adapter_size)
        # ReLUæ¿æ´»å½æ?
        self.relu = nn.ReLU()
        # ç¬¬äºä¸ªå¨è¿æ¥å±åç»?
        self.up_project = nn.Linear(adapter_size, input_size)

    def forward(self, x):
        # éè¿Adapterå±çååä¼ æ­
        down_projected = self.down_project(x)
        relu = self.relu(down_projected)
        up_projected = self.up_project(x)
        # å°Adapterçè¾åºä¸è¾å¥ç¸å ï¼æ®å·®è¿æ¥ï¼
        return x + up_projected
