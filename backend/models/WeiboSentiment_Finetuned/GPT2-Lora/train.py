import os
import random
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    GPT2ForSequenceClassification, 
    BertTokenizer, 
    get_linear_schedule_with_warmup,
    TrainingArguments,
    Trainer
)
from torch.optim import AdamW
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from tqdm import tqdm

# å¯¼å¥PEFTåºä¸­çLoRAç¸å³ç»ä»¶
from peft import LoraConfig, TaskType, get_peft_model

# è®¾ç½®éæºç§å­
def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

set_seed(42)

# å®ä¹å¾®åææåææ°æ®é?
class WeiboSentimentDataset(Dataset):
    def __init__(self, reviews, labels, tokenizer, max_length=128):
        self.reviews = reviews
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def __len__(self):
        return len(self.reviews)
    
    def __getitem__(self, idx):
        review = str(self.reviews[idx])
        label = self.labels[idx]
        
        encoding = self.tokenizer(
            review,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

# è®­ç»å½æ°
def train_model(model, train_dataloader, val_dataloader, optimizer, scheduler, device, epochs=3):
    best_f1 = 0.0
    
    for epoch in range(epochs):
        print(f"======== Epoch {epoch+1} / {epochs} ========")
        model.train()
        total_loss = 0
        
        # è®­ç»å¾ªç¯
        progress_bar = tqdm(train_dataloader, desc="Training", position=0, leave=True)
        for batch in progress_bar:
            # å°æ°æ®ç§»å°GPU
            batch = {k: v.to(device) for k, v in batch.items()}
            
            # æ¸é¶æ¢¯åº¦
            optimizer.zero_grad()
            
            # ååä¼ æ­
            outputs = model(
                input_ids=batch['input_ids'],
                attention_mask=batch['attention_mask'],
                labels=batch['labels']
            )
            
            loss = outputs.loss
            total_loss += loss.item()
            
            # ååä¼ æ­
            loss.backward()
            
            # æ¢¯åº¦è£åªï¼é²æ­¢æ¢¯åº¦çç?
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            
            # åæ°æ´æ°
            optimizer.step()
            scheduler.step()
            
            # æ´æ°è¿åº¦æ?
            progress_bar.set_postfix({"loss": loss.item()})
        
        # è®¡ç®å¹³åè®­ç»æå¤±
        avg_train_loss = total_loss / len(train_dataloader)
        print(f"Average training loss: {avg_train_loss:.4f}")
        
        # è¯ä¼°æ¨¡å
        val_metrics = evaluate_model(model, val_dataloader, device)
        print(f"Validation Loss: {val_metrics['loss']:.4f}")
        print(f"Validation Accuracy: {val_metrics['accuracy']:.4f}")
        print(f"Validation F1 Score: {val_metrics['f1']:.4f}")
        
        # ä¿å­æä½³æ¨¡å?
        if val_metrics['f1'] > best_f1:
            best_f1 = val_metrics['f1']
            # ä¿å­LoRAæé
            model.save_pretrained("./best_weibo_sentiment_lora")
            print("Saved best LoRA model!")

# è¯ä¼°å½æ°
def evaluate_model(model, dataloader, device):
    model.eval()
    total_loss = 0
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Evaluating"):
            batch = {k: v.to(device) for k, v in batch.items()}
            
            outputs = model(
                input_ids=batch['input_ids'],
                attention_mask=batch['attention_mask'],
                labels=batch['labels']
            )
            
            loss = outputs.loss
            total_loss += loss.item()
            
            # è·åé¢æµç»æ
            logits = outputs.logits
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            labels = batch['labels'].cpu().numpy()
            
            all_preds.extend(preds)
            all_labels.extend(labels)
    
    # è®¡ç®è¯ä¼°ææ 
    accuracy = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average='macro')
    avg_loss = total_loss / len(dataloader)
    
    return {
        'loss': avg_loss,
        'accuracy': accuracy,
        'f1': f1
    }

def main():
    # è®¾ç½®æ¨¡åæ¬å°ä¿å­è·¯å¾
    model_name = 'uer/gpt2-chinese-cluecorpussmall'
    local_model_path = './models/gpt2-chinese'
    
    # ç¡®ä¿ç®å½å­å¨
    os.makedirs(local_model_path, exist_ok=True)
    os.makedirs('./best_weibo_sentiment_lora', exist_ok=True)
    
    # å è½½æ°æ®é?
    print("å è½½å¾®åæææ°æ®é?..")
    df = pd.read_csv('dataset/weibo_senti_100k.csv')
    
    # åå²æ°æ®é?
    train_df, val_df = train_test_split(df, test_size=0.1, random_state=42, stratify=df['label'])
    
    # å è½½tokenizer
    print("å è½½é¢è®­ç»æ¨¡ååtokenizer...")
    
    # æ£æ¥æ¬å°æ¯å¦å·²ææ¨¡å?
    if os.path.exists(os.path.join(local_model_path, 'config.json')):
        print(f"ä»æ¬å°è·¯å¾å è½½tokenizer: {local_model_path}")
        tokenizer = BertTokenizer.from_pretrained(local_model_path)
    else:
        print(f"ä»Hugging Faceä¸è½½tokenizerå? {local_model_path}")
        tokenizer = BertTokenizer.from_pretrained(model_name, cache_dir=local_model_path)
        # ä¿å­tokenizerå°æ¬å?
        tokenizer.save_pretrained(local_model_path)
    
    # è®¾ç½®padding token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = '[PAD]'
    
    # è®°å½pad_tokençID
    pad_token_id = tokenizer.pad_token_id
    
    # åå»ºæ°æ®é?
    train_dataset = WeiboSentimentDataset(
        train_df['review'].values,
        train_df['label'].values,
        tokenizer
    )
    
    val_dataset = WeiboSentimentDataset(
        val_df['review'].values,
        val_df['label'].values,
        tokenizer
    )
    
    # åå»ºæ°æ®å è½½å?
    train_dataloader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_dataloader = DataLoader(val_dataset, batch_size=16)
    
    # è®¾ç½®è®¾å¤
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"ä½¿ç¨è®¾å¤: {device}")
    
    # å è½½é¢è®­ç»çGPT2æ¨¡å
    print("å è½½GPT2æ¨¡å...")
    if (os.path.exists(os.path.join(local_model_path, 'pytorch_model.bin')) or 
        os.path.exists(os.path.join(local_model_path, 'model.safetensors'))):
        print(f"ä»æ¬å°è·¯å¾å è½½æ¨¡åæé? {local_model_path}")
        model = GPT2ForSequenceClassification.from_pretrained(local_model_path, num_labels=2)
    else:
        print(f"ä»Hugging Faceä¸è½½æ¨¡åæéå? {local_model_path}")
        # ç´æ¥ä»Hugging Faceä¸è½½å¹¶ä¿å­å®æ´æ¨¡å?
        model = GPT2ForSequenceClassification.from_pretrained(model_name, num_labels=2)
        model.save_pretrained(local_model_path)
    
    # ç¡®ä¿æ¨¡åä½¿ç¨ä¸tokenizerç¸åçpad_token_id
    model.config.pad_token_id = pad_token_id
    
    # éç½®LoRAåæ°
    print("éç½®LoRAåæ°...")
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,  # åºååç±»ä»»å¡
        target_modules=["c_attn", "c_proj"],  # GPT2çæ³¨æåæå½±å±?
        inference_mode=False,  # è®­ç»æ¨¡å¼
        r=8,  # LoRAç§©ï¼æ§å¶å¯è®­ç»åæ°æ°é?
        lora_alpha=32,  # LoRA alphaåæ°ï¼ç¼©æ¾å å­?
        lora_dropout=0.1,  # LoRA Dropout
    )
    
    # å°æ¨¡åè½¬æ¢ä¸ºPEFTæ ¼å¼çLoRAæ¨¡å
    print("åå»ºLoRAæ¨¡å...")
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()  # æå°å¯è®­ç»åæ°æ°éåå æ¯
    
    model.to(device)
    
    # è®¾ç½®ä¼åå¨åå­¦ä¹ çè°åº¦å¨
    print("è®¾ç½®ä¼åå?..")
    optimizer = AdamW(
        model.parameters(),  # PEFTä¼èªå¨å¤çåæ°ç­é?
        lr=5e-4,  # LoRAéå¸¸ä½¿ç¨è¾é«çå­¦ä¹ ç
        eps=1e-8
    )
    
    # è®¾ç½®æ»è®­ç»æ­¥æ°åwarmupæ­¥æ°
    total_steps = len(train_dataloader) * 3  # 3ä¸ªepoch
    warmup_steps = int(total_steps * 0.1)  # 10%çwarmup
    
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps
    )
    
    # è®­ç»æ¨¡å
    print("å¼å§è®­ç»?..")
    train_model(
        model=model,
        train_dataloader=train_dataloader,
        val_dataloader=val_dataloader,
        optimizer=optimizer,
        scheduler=scheduler,
        device=device,
        epochs=3
    )
    
    print("è®­ç»å®æ!")
    print("LoRAæéå·²ä¿å­å°: ./best_weibo_sentiment_lora/")

if __name__ == "__main__":
    main()
