import torch
import torch.nn as nn

class AdapterLayer(nn.Module):
    """
    Adapterå±å®ç?
    å°å¶æ·»å å°Transformerå±ä¸­å¯ä»¥å®ç°åæ°é«æå¾®è°
    """
    def __init__(self, input_size, adapter_size):
        super(AdapterLayer, self).__init__()
        # éç»´å¨è¿æ¥å±
        self.down_project = nn.Linear(input_size, adapter_size)
        # æ¿æ´»å½æ?
        self.activation = nn.ReLU()
        # åç»´å¨è¿æ¥å±
        self.up_project = nn.Linear(adapter_size, input_size)
        
        # åå§ååæ?
        self._init_weights()
    
    def _init_weights(self):
        # åå§ådown_projectç¨è¾å°çå?
        nn.init.normal_(self.down_project.weight, std=1e-2)
        nn.init.zeros_(self.down_project.bias)
        
        # åå§åup_projectä¸ºæ¥è¿é¶çå¼ï¼ç¡®ä¿è®­ç»åæå¯¹åå§æ¨¡åå½±åè¾å°?
        nn.init.normal_(self.up_project.weight, std=1e-2)
        nn.init.zeros_(self.up_project.bias)
    
    def forward(self, x):
        # ä¿å­åå§è¾å¥ç¨äºæ®å·®è¿æ¥
        residual = x
        
        # éè¿éç»´å±?
        x = self.down_project(x)
        # æ¿æ´?
        x = self.activation(x)
        # éè¿åç»´å±?
        x = self.up_project(x)
        
        # æ®å·®è¿æ¥
        return residual + x 
