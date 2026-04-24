import torch
import torch.nn as nn
from transformers.models.gpt2.modeling_gpt2 import GPT2Block
from adapter import AdapterLayer

class GPT2BlockWithAdapter(nn.Module):
    """
    å¸¦AdapterçGPT2Blockå±?
    å¨åå§GPT2Blockçåºç¡ä¸æ·»å Adapterå±å®ç°åæ°é«æå¾®è°?
    """
    def __init__(self, config):
        super(GPT2BlockWithAdapter, self).__init__()
        # åå»ºæ åçGPT2Block
        self.original_block = GPT2Block(config)
        
        # æ·»å Adapterå±?
        adapter_size = 64  # Adapterçéèå±å¤§å°
        self.adapter = AdapterLayer(config.hidden_size, adapter_size)
    
    def forward(
        self,
        hidden_states,
        layer_past=None,
        attention_mask=None,
        head_mask=None,
        encoder_hidden_states=None,
        encoder_attention_mask=None,
        use_cache=False,
        output_attentions=False,
        **kwargs  # ä½¿ç¨**kwargsæ¥æ¶ææå¶ä»åæ?
    ):
        # é¦åéè¿åå§çGPT2Blockï¼åªä¼ éå®æ¯æçåæ?
        outputs = self.original_block(
            hidden_states,
            layer_past=layer_past,
            attention_mask=attention_mask,
            head_mask=head_mask,
            encoder_hidden_states=encoder_hidden_states,
            encoder_attention_mask=encoder_attention_mask,
            use_cache=use_cache,
            output_attentions=output_attentions,
        )
        
        # åå§è¾åºä¸­çç¬¬ä¸ä¸ªåç´ æ¯éèç¶æ?
        hidden_states = outputs[0]
        
        # å°éèç¶æéè¿Adapterå±?
        hidden_states = self.adapter(hidden_states)
        
        # æ´æ°è¾åºçéèç¶æ?
        outputs = (hidden_states,) + outputs[1:]
        
        return outputs
    
    def load_state_dict(self, state_dict, strict=True):
        """
        èªå®ä¹å è½½åæ°æ¹æ³ï¼ç¨äºä»åå§GPT2Blockå è½½åæ°
        """
        # å°ææåæ°ä¼ éç»åå§Block
        return self.original_block.load_state_dict(state_dict, strict=strict) 
