import torch
from transformers import GPT2ForSequenceClassification, BertTokenizer
from peft import PeftModel
import os
import re

def preprocess_text(text):
    return text

def main():
    # è®¾ç½®è®¾å¤
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"ä½¿ç¨è®¾å¤: {device}")
    
    # æ¨¡ååæéè·¯å¾?
    base_model_path = './models/gpt2-chinese'
    lora_model_path = './best_weibo_sentiment_lora'
    
    print("å è½½æ¨¡ååtokenizer...")
    
    # æ£æ¥LoRAæ¨¡åæ¯å¦å­å¨
    if not os.path.exists(lora_model_path):
        print(f"éè¯¯: æ¾ä¸å°LoRAæ¨¡åè·¯å¾ {lora_model_path}")
        print("è¯·åè¿è¡ train.py è¿è¡è®­ç»")
        return
    
    # å è½½tokenizer
    try:
        tokenizer = BertTokenizer.from_pretrained(base_model_path)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = '[PAD]'
    except Exception as e:
        print(f"å è½½tokenizerå¤±è´¥: {e}")
        print("è¯·ç¡®ä¿models/gpt2-chineseç®å½åå«tokenizeræä»¶")
        return
    
    # å è½½åºç¡æ¨¡å
    try:
        base_model = GPT2ForSequenceClassification.from_pretrained(
            base_model_path, 
            num_labels=2
        )
        base_model.config.pad_token_id = tokenizer.pad_token_id
    except Exception as e:
        print(f"å è½½åºç¡æ¨¡åå¤±è´¥: {e}")
        print("è¯·ç¡®ä¿models/gpt2-chineseç®å½åå«æ¨¡åæä»¶")
        return
    
    # å è½½LoRAæé
    try:
        model = PeftModel.from_pretrained(base_model, lora_model_path)
        model.to(device)
        model.eval()
        print("LoRAæ¨¡åå è½½æå!")
    except Exception as e:
        print(f"å è½½LoRAæéå¤±è´¥: {e}")
        print("è¯·ç¡®ä¿LoRAæéæä»¶å­å¨ä¸æ ¼å¼æ­£ç¡?)
        return
    
    print("\n============= å¾®åææåæ (LoRAç? =============")
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
            
            # å¯¹ææ¬è¿è¡ç¼ç ?
            encoding = tokenizer(
                processed_text,
                max_length=128,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )
            
            # è½¬ç§»å°è®¾å¤?
            input_ids = encoding['input_ids'].to(device)
            attention_mask = encoding['attention_mask'].to(device)
            
            # é¢æµ
            with torch.no_grad():
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
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
