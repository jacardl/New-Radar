from transformers.models.gpt2.modeling_gpt2 import GPT2Block

class GPT2BlockWithAdapter(GPT2Block):
    def __init__(self, config):
        super().__init__(config)
        # åè®¾Adapterçå¤§å°ä¸º64
        adapter_size = 64
        self.adapter = AdapterLayer(config.n_embd, adapter_size)

    def forward(
        self,
        hidden_states,
        layer_past=None,
        attention_mask=None,
        head_mask=None,
        use_cache=False,
        output_attentions=False,
    ):
        # è°ç¨åå§çååä¼ æ­æ¹æ³?
        attn_outputs = super().forward(
            hidden_states,
            layer_past=layer_past,
            attention_mask=attention_mask,
            head_mask=head_mask,
            use_cache=use_cache,
            output_attentions=output_attentions,
        )
        # å¾å°Transformerå±çè¾åº
        a = attn_outputs[0]  # è¾åºçç¬¬ä¸é¨åæ¯attentionçç»æ?
        # å°è¾åºéè¿Adapterå±?
        a = self.adapter(a)
        # è¿åä¿®æ¹åçè¾åºï¼å¶ä»è¾åºä¿æä¸åï¼
        outputs = (a,) + attn_outputs[1:]
        return outputs
"""
æ¯ä¸ªGPT2Blockåå«äºä¸ç³»åçèªæ³¨æåï¼Self-Attentionï¼ååé¦ç½ç»ï¼Feed-Forwardï¼å±ï¼è¿äºå±å±åææäºæ¨¡åçåºç¡æ¶æ

"""


