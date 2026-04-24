import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import re

def preprocess_text(text):
    return text

def main():
    print("æ­£å¨å è½½å¾®åææåææ¨¡å...")
    
    # ä½¿ç¨HuggingFaceé¢è®­ç»æ¨¡å?
    model_name = "wsqstar/GISchat-weibo-100k-fine-tuned-bert"
    local_model_path = "./model"
    
    try:
        # æ£æ¥æ¬å°æ¯å¦å·²ææ¨¡å?
        import os
        if os.path.exists(local_model_path):
            print("ä»æ¬å°å è½½æ¨¡å?..")
            tokenizer = AutoTokenizer.from_pretrained(local_model_path)
            model = AutoModelForSequenceClassification.from_pretrained(local_model_path)
        else:
            print("é¦æ¬¡ä½¿ç¨ï¼æ­£å¨ä¸è½½æ¨¡åå°æ¬å°...")
            # ä¸è½½å¹¶ä¿å­å°æ¬å°
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSequenceClassification.from_pretrained(model_name)
            
            # ä¿å­å°æ¬å?
            tokenizer.save_pretrained(local_model_path)
            model.save_pretrained(local_model_path)
            print(f"æ¨¡åå·²ä¿å­å°: {local_model_path}")
        
        # è®¾ç½®è®¾å¤
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model.to(device)
        model.eval()
        print(f"æ¨¡åå è½½æå! ä½¿ç¨è®¾å¤: {device}")
        
    except Exception as e:
        print(f"æ¨¡åå è½½å¤±è´¥: {e}")
        print("è¯·æ£æ¥ç½ç»è¿æ¥æä½¿ç¨pipelineæ¹å¼")
        return
    
    print("\n============= å¾®åææåæ =============")
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
            
            # åè¯ç¼ç 
            inputs = tokenizer(
                processed_text,
                max_length=512,
                padding=True,
                truncation=True,
                return_tensors='pt'
            )
            
            # è½¬ç§»å°è®¾å¤?
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # é¢æµ
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=1)
                prediction = torch.argmax(probabilities, dim=1).item()
            
            # è¾åºç»æ
            confidence = probabilities[0][prediction].item()
            label = "æ­£é¢ææ" if prediction == 1 else "è´é¢ææ"
            
            print(f"é¢æµç»æ: {label} (ç½®ä¿¡åº? {confidence:.4f})")
            
        except Exception as e:
            print(f"é¢æµæ¶åçéè¯? {e}")
            continue

if __name__ == "__main__":
    main()
