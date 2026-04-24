import torch
from transformers import BertTokenizer
from train import GPT2ClassifierWithAdapter
import re

def preprocess_text(text):
    """ç®åçææ¬é¢å¤ç?""
    return text

def main():
    # è®¾ç½®è®¾å¤
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"ä½¿ç¨è®¾å¤: {device}")
    
    # ä½¿ç¨æ¬å°æ¨¡åè·¯å¾èä¸æ¯å¨çº¿æ¨¡ååç§?
    local_model_path = './models/gpt2-chinese'
    model_path = 'best_weibo_sentiment_model.pth'
    
    print(f"å è½½æ¨¡å: {model_path}")
    # ä»æ¬å°å è½½tokenizer
    tokenizer = BertTokenizer.from_pretrained(local_model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = '[PAD]'
    
    # å è½½æ¨¡åï¼ä½¿ç¨æ¬å°æ¨¡åè·¯å¾?
    model = GPT2ClassifierWithAdapter(local_model_path)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    
    print("\n============= å¾®åææåæ =============")
    print("è¾å¥å¾®ååå®¹è¿è¡åæ (è¾å¥ 'q' éå?:")
    
    while True:
        text = input("\nè¯·è¾å¥å¾®ååå®? ")
        if text.lower() == 'q':
            break
        
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

if __name__ == "__main__":
    main() 
