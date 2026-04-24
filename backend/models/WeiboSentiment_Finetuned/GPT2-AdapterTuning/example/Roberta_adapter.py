from transformers.models.roberta.modeling_roberta import RobertaLayer

class RobertaLayerWithAdapter(RobertaLayer):
    def __init__(self, config):
        super().__init__(config)
        # åè®¾Adapterçå¤§å°ä¸º64
        adapter_size = 64
        self.adapter = AdapterLayer(config.hidden_size, adapter_size)

    def forward(self, hidden_states, attention_mask=None, head_mask=None, encoder_hidden_states=None, encoder_attention_mask=None, past_key_value=None, output_attentions=False):
        # è°ç¨åå§çååä¼ æ­æ¹æ³?
        self_outputs = super().forward(hidden_states, attention_mask, head_mask, encoder_hidden_states, encoder_attention_mask, past_key_value, output_attentions)
        # å¾å°Transformerå±çè¾åº
        sequence_output = self_outputs[0]
        # å°è¾åºéè¿Adapterå±?
        sequence_output = self.adapter(sequence_output)
        # è¿åä¿®æ¹åçè¾åºï¼å¶ä»è¾åºä¿æä¸åï¼
        return (sequence_output,) + self_outputs[1:]

"""
RoBERTaçæ¯ä¸ªRobertaLayeråå«ä¸ä¸ªèªæ³¨æåï¼self-attentionï¼æºå¶åä¸ä¸ªåé¦ç½ç»ï¼è¿äºå±å±åææäºRoBERTaçåºç¡æ¶æ
"""
