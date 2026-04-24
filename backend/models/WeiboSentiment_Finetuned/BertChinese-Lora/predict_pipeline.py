from transformers import pipeline
import re

def preprocess_text(text):
    """ç®åçææ¬é¢å¤ç?""
    text = re.sub(r"\{%.+?%\}", " ", text)           # å»é¤ {%xxx%}
    text = re.sub(r"@.+?( |$)", " ", text)           # å»é¤ @xxx
    text = re.sub(r"+?, " ", text)              # å»é¤ x
    text = re.sub(r"\u200b", " ", text)              # å»é¤ç¹æ®å­ç¬¦
    # å é¤è¡¨æç¬¦å·
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001f900-\U0001f9ff\U0001f018-\U0001f270\U0000231a-\U0000231b\U0000238d-\U0000238d\U000024c2-\U0001f251]+', '', text)
    text = re.sub(r"\s+", " ", text)                 # å¤ä¸ªç©ºæ ¼åå¹¶
    return text.strip()

def main():
    print("æ­£å¨å è½½å¾®åææåææ¨¡å...")
    
    # ä½¿ç¨pipelineæ¹å¼ - æ´ç®å?
    model_name = "wsqstar/GISchat-weibo-100k-fine-tuned-bert"
    local_model_path = "./model"
    
    try:
        # æ£æ¥æ¬å°æ¯å¦å·²ææ¨¡å?
        import os
        if os.path.exists(local_model_path):
            print("ä»æ¬å°å è½½æ¨¡å?..")
            classifier = pipeline(
                "text-classification", 
                model=local_model_path,
                return_all_scores=True
            )
        else:
            print("é¦æ¬¡ä½¿ç¨ï¼æ­£å¨ä¸è½½æ¨¡åå°æ¬å°...")
            # åä¸è½½æ¨¡å?
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSequenceClassification.from_pretrained(model_name)
            
            # ä¿å­å°æ¬å?
            tokenizer.save_pretrained(local_model_path)
            model.save_pretrained(local_model_path)
            print(f"æ¨¡åå·²ä¿å­å°: {local_model_path}")
            
            # ä½¿ç¨æ¬å°æ¨¡ååå»ºpipeline
            classifier = pipeline(
                "text-classification", 
                model=local_model_path,
                return_all_scores=True
            )
        print("æ¨¡åå è½½æå!")
        
    except Exception as e:
        print(f"æ¨¡åå è½½å¤±è´¥: {e}")
        print("è¯·æ£æ¥ç½ç»è¿æ?)
        return
    
    print("\n============= å¾®åææåæ (Pipelineç? =============")
    print("è¾å¥å¾®ååå®¹è¿è¡åæ (è¾å¥ 'q' éå?:")
    
    while True:
        text = input("\nè¯·è¾å¥å¾®ååå®? ")
        if text.lower() == 'q':
            break
        
        if not text.strip():
            print("è¾å¥ä¸è½ä¸ºç©ºï¼è¯·éæ°è¾å¥")
            continue
        
        try:
            # é¢å¤çææ?
            processed_text = preprocess_text(text)
            
            # é¢æµ
            outputs = classifier(processed_text)
            
            # è§£æç»æ
            positive_score = None
            negative_score = None
            
            for output in outputs[0]:
                if output['label'] == 'LABEL_1':  # æ­£é¢
                    positive_score = output['score']
                elif output['label'] == 'LABEL_0':  # è´é¢
                    negative_score = output['score']
            
            # ç¡®å®é¢æµç»æ
            if positive_score > negative_score:
                label = "æ­£é¢ææ"
                confidence = positive_score
            else:
                label = "è´é¢ææ"
                confidence = negative_score
            
            print(f"é¢æµç»æ: {label} (ç½®ä¿¡åº? {confidence:.4f})")
            
        except Exception as e:
            print(f"é¢æµæ¶åçéè¯? {e}")
            continue

if __name__ == "__main__":
    main()
