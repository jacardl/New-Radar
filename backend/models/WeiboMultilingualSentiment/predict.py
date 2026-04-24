import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import re

def preprocess_text(text):
    """ç®åçææ¬é¢å¤çï¼éç¨äºå¤è¯­è¨ææ¬"""
    return text

def main():
    print("æ­£å¨å è½½å¤è¯­è¨ææåææ¨¡å...")
    
    # ä½¿ç¨å¤è¯­è¨ææåææ¨¡å
    model_name = "tabularisai/multilingual-sentiment-analysis"
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
        
        # æææ ç­¾æ å°ï¼?çº§åç±»ï¼
        sentiment_map = {
            0: "éå¸¸è´é¢", 1: "è´é¢", 2: "ä¸­æ?, 3: "æ­£é¢", 4: "éå¸¸æ­£é¢"
        }
        
    except Exception as e:
        print(f"æ¨¡åå è½½å¤±è´¥: {e}")
        print("è¯·æ£æ¥ç½ç»è¿æ?)
        return
    
    print("\n============= å¤è¯­è¨ææåæ =============")
    print("æ¯æè¯­è¨: ä¸­æãè±æãè¥¿ç­çæãé¿æä¼¯æãæ¥æãé©æç­22ç§è¯­è¨")
    print("ææç­çº§: éå¸¸è´é¢ãè´é¢ãä¸­æ§ãæ­£é¢ãéå¸¸æ­£é?)
    print("è¾å¥ææ¬è¿è¡åæ (è¾å¥ 'q' éå?:")
    print("è¾å¥ 'demo' æ¥çå¤è¯­è¨ç¤ºä¾")
    
    while True:
        text = input("\nè¯·è¾å¥ææ? ")
        if text.lower() == 'q':
            break
        
        if text.lower() == 'demo':
            show_multilingual_demo(tokenizer, model, device, sentiment_map)
            continue
        
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
            label = sentiment_map[prediction]
            
            print(f"é¢æµç»æ: {label} (ç½®ä¿¡åº? {confidence:.4f})")
            
            # æ¾ç¤ºææç±»å«çæ¦ç
            print("è¯¦ç»æ¦çåå¸:")
            for i, (label_name, prob) in enumerate(zip(sentiment_map.values(), probabilities[0])):
                print(f"  {label_name}: {prob:.4f}")
            
        except Exception as e:
            print(f"é¢æµæ¶åçéè¯? {e}")
            continue

def show_multilingual_demo(tokenizer, model, device, sentiment_map):
    """å±ç¤ºå¤è¯­è¨ææåæç¤ºä¾"""
    print("\n=== å¤è¯­è¨ææåæç¤ºä¾ ===")
    
    demo_texts = [
        # ä¸­æ
        ("ä»å¤©å¤©æ°çå¥½ï¼å¿æç¹å«æ£ï¼?, "ä¸­æ"),
        ("è¿å®¶é¤åçèå³ééå¸¸æ£ï¼", "ä¸­æ"),
        ("æå¡æåº¦å¤ªå·®äºï¼å¾å¤±æ?, "ä¸­æ"),
        
        # è±æ
        ("I absolutely love this product!", "è±æ"),
        ("The customer service was disappointing.", "è±æ"),
        ("The weather is fine, nothing special.", "è±æ"),
        
        # æ¥æ
        ("®ã¬ã¹©ã³ã®æçã¯æ¬å½ã«ç¾å³§ãï¼?, "æ¥æ"),
        ("®«ã®ãµã¼¹ã¯£¾, "æ¥æ"),
        
        # é©æ
        ("ì?ê°ê²ì ì¼ì´í¬ë?ì ë§ ë§ìì´ìï¼?, "é©æ"),
        ("ìë¹ì¤ê° ëë¬´ ë³ë¡ìì´ì, "é©æ"),
        
        # è¥¿ç­çæ
        ("�¡Me encanta c�³mo qued�³ la decoraci�³n!", "è¥¿ç­çæ"),
        ("El servicio fue terrible y muy lento.", "è¥¿ç­çæ"),
    ]
    
    for text, language in demo_texts:
        try:
            inputs = tokenizer(
                text,
                max_length=512,
                padding=True,
                truncation=True,
                return_tensors='pt'
            )
            
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=1)
                prediction = torch.argmax(probabilities, dim=1).item()
            
            confidence = probabilities[0][prediction].item()
            label = sentiment_map[prediction]
            
            print(f"\n{language}: {text}")
            print(f"ç»æ: {label} (ç½®ä¿¡åº? {confidence:.4f})")
            
        except Exception as e:
            print(f"å¤ç {text} æ¶åºé? {e}")
    
    print("\n=== ç¤ºä¾ç»æ ===")
    
    r"""
    æ­£å¨å è½½å¤è¯­è¨ææåææ¨¡å...
ä»æ¬å°å è½½æ¨¡å?..
æ¨¡åå è½½æå! ä½¿ç¨è®¾å¤: cuda

============= å¤è¯­è¨ææåæ =============
æ¯æè¯­è¨: ä¸­æãè±æãè¥¿ç­çæãé¿æä¼¯æãæ¥æãé©æç­22ç§è¯­è¨
ææç­çº§: éå¸¸è´é¢ãè´é¢ãä¸­æ§ãæ­£é¢ãéå¸¸æ­£é?
è¾å¥ææ¬è¿è¡åæ (è¾å¥ 'q' éå?:
è¾å¥ 'demo' æ¥çå¤è¯­è¨ç¤ºä¾

è¯·è¾å¥ææ? æåæ¬¢ä½ 
C:\Users\67093\.conda\envs\pytorch_python11\Lib\site-packages\transformers\models\distilbert\modeling_distilbert.py:401: UserWarning: 1Torch was not compiled with flash attention. (Triggered internally at C:\cb\pytorch_1000000000000\work\aten\src\ATen\native\transformers\cuda\sdp_utils.cpp:263.)
  attn_output = torch.nn.functional.scaled_dot_product_attention(
é¢æµç»æ: æ­£é¢ (ç½®ä¿¡åº? 0.5204)
è¯¦ç»æ¦çåå¸:
  éå¸¸è´é¢: 0.0329
  è´é¢: 0.0263
  ä¸­æ? 0.1987
  æ­£é¢: 0.5204
  éå¸¸æ­£é¢: 0.2216

è¯·è¾å¥ææ?
    """

if __name__ == "__main__":
    main()
