# -*- coding: utf-8 -*-
"""
BERTææåææ¨¡åè®­ç»èæ¬
"""
import argparse
import os
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer, BertModel
from sklearn.metrics import accuracy_score, f1_score, classification_report, roc_auc_score
from typing import List, Tuple
import warnings
import requests
from pathlib import Path

from base_model import BaseModel
from utils import load_corpus_bert

# å¿½ç¥transformersçè­¦å?
warnings.filterwarnings("ignore")
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


class BertDataset(Dataset):
    """BERTæ°æ®é?""
    
    def __init__(self, data: List[Tuple[str, int]]):
        self.data = [item[0] for item in data]
        self.labels = [item[1] for item in data]
    
    def __getitem__(self, index):
        return self.data[index], self.labels[index]
    
    def __len__(self):
        return len(self.labels)


class BertClassifier(nn.Module):
    """BERTåç±»å¨ç½ç»?""
    
    def __init__(self, input_size):
        super(BertClassifier, self).__init__()
        self.fc = nn.Linear(input_size, 1)
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        out = self.fc(x)
        out = self.sigmoid(out)
        return out


class BertModel_Custom(BaseModel):
    """BERTææåææ¨¡å"""
    
    def __init__(self, model_path: str = "./model/chinese_wwm_pytorch"):
        super().__init__("BERT")
        self.model_path = model_path
        self.tokenizer = None
        self.bert = None
        self.classifier = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
    def _download_bert_model(self):
        """èªå¨ä¸è½½BERTé¢è®­ç»æ¨¡å?""
        print(f"BERTæ¨¡åä¸å­å¨ï¼æ­£å¨ä¸è½½ä¸­æBERTé¢è®­ç»æ¨¡å?..")
        print("ä¸è½½æ¥æº: bert-base-chinese (Hugging Face)")
        
        try:
            # åå»ºæ¨¡åç®å½
            os.makedirs(self.model_path, exist_ok=True)
            
            # ä½¿ç¨Hugging Faceçä¸­æBERTæ¨¡å
            model_name = "bert-base-chinese"
            print(f"æ­£å¨ä»Hugging Faceä¸è½½ {model_name}...")
            
            # ä¸è½½tokenizer
            print("ä¸è½½åè¯å?..")
            tokenizer = BertTokenizer.from_pretrained(model_name)
            tokenizer.save_pretrained(self.model_path)
            
            # ä¸è½½æ¨¡å
            print("ä¸è½½BERTæ¨¡å...")
            bert_model = BertModel.from_pretrained(model_name)
            bert_model.save_pretrained(self.model_path)
            
            print(f"â?BERTæ¨¡åä¸è½½å®æï¼ä¿å­å¨: {self.model_path}")
            return True
            
        except Exception as e:
            print(f"â?BERTæ¨¡åä¸è½½å¤±è´¥: {e}")
            print("\nð¡ æ¨å¯ä»¥æå¨ä¸è½½BERTæ¨¡å:")
            print("1. è®¿é® https://huggingface.co/bert-base-chinese")
            print("2. æä½¿ç¨åå·¥å¤§ä¸­æBERT: https://github.com/ymcui/Chinese-BERT-wwm")
            print(f"3. å°æ¨¡åæä»¶è§£åå°: {self.model_path}")
            return False
    
    def _load_bert(self):
        """å è½½BERTæ¨¡åååè¯å¨"""
        print(f"å è½½BERTæ¨¡å: {self.model_path}")
        
        # å¦ææ¨¡åä¸å­å¨ï¼å°è¯èªå¨ä¸è½½
        if not os.path.exists(self.model_path) or not any(os.scandir(self.model_path)):
            print("BERTæ¨¡åä¸å­å¨ï¼å°è¯èªå¨ä¸è½½...")
            if not self._download_bert_model():
                raise FileNotFoundError(f"BERTæ¨¡åä¸è½½å¤±è´¥ï¼è¯·æå¨ä¸è½½å? {self.model_path}")
        
        try:
            self.tokenizer = BertTokenizer.from_pretrained(self.model_path)
            self.bert = BertModel.from_pretrained(self.model_path).to(self.device)
            
            # å»ç»BERTåæ°
            for param in self.bert.parameters():
                param.requires_grad = False
                
            print("â?BERTæ¨¡åå è½½å®æ")
            
        except Exception as e:
            print(f"â?BERTæ¨¡åå è½½å¤±è´¥: {e}")
            print("å°è¯ä½¿ç¨å¨çº¿æ¨¡å...")
            
            # å¦ææ¬å°å è½½å¤±è´¥ï¼å°è¯ç´æ¥ä½¿ç¨å¨çº¿æ¨¡å?
            try:
                model_name = "bert-base-chinese"
                self.tokenizer = BertTokenizer.from_pretrained(model_name)
                self.bert = BertModel.from_pretrained(model_name).to(self.device)
                
                # å»ç»BERTåæ°
                for param in self.bert.parameters():
                    param.requires_grad = False
                    
                print("â?å¨çº¿BERTæ¨¡åå è½½å®æ")
                
            except Exception as e2:
                print(f"â?å¨çº¿æ¨¡åä¹å è½½å¤±è´? {e2}")
                raise FileNotFoundError(f"æ æ³å è½½BERTæ¨¡åï¼è¯·æ£æ¥ç½ç»è¿æ¥ææå¨ä¸è½½æ¨¡åå? {self.model_path}")
    
    def train(self, train_data: List[Tuple[str, int]], **kwargs) -> None:
        """è®­ç»BERTæ¨¡å"""
        print(f"å¼å§è®­ç»?{self.model_name} æ¨¡å...")
        
        # å è½½BERT
        self._load_bert()
        
        # è¶åæ?
        learning_rate = kwargs.get('learning_rate', 1e-3)
        num_epochs = kwargs.get('num_epochs', 10)
        batch_size = kwargs.get('batch_size', 100)
        input_size = kwargs.get('input_size', 768)
        decay_rate = kwargs.get('decay_rate', 0.9)
        
        print(f"BERTè¶åæ? lr={learning_rate}, epochs={num_epochs}, "
              f"batch_size={batch_size}, input_size={input_size}")
        
        # åå»ºæ°æ®é?
        train_dataset = BertDataset(train_data)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        
        # åå»ºåç±»å?
        self.classifier = BertClassifier(input_size).to(self.device)
        
        # æå¤±å½æ°åä¼åå¨
        criterion = nn.BCELoss()
        optimizer = torch.optim.Adam(self.classifier.parameters(), lr=learning_rate)
        scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=decay_rate)
        
        # è®­ç»å¾ªç¯
        self.bert.eval()  # BERTå§ç»ä¿æè¯ä¼°æ¨¡å¼
        self.classifier.train()
        
        for epoch in range(num_epochs):
            total_loss = 0
            num_batches = 0
            
            for i, (words, labels) in enumerate(train_loader):
                # åè¯åç¼ç ?
                tokens = self.tokenizer(words, padding=True, truncation=True, 
                                      max_length=512, return_tensors='pt')
                input_ids = tokens["input_ids"].to(self.device)
                attention_mask = tokens["attention_mask"].to(self.device)
                labels = torch.tensor(labels, dtype=torch.float32).to(self.device)
                
                # è·åBERTè¾åºï¼å»ç»åæ°ï¼
                with torch.no_grad():
                    bert_outputs = self.bert(input_ids, attention_mask=attention_mask)
                    bert_output = bert_outputs[0][:, 0]  # [CLS] tokençè¾å?
                
                # åç±»å¨ååä¼ æ?
                optimizer.zero_grad()
                outputs = self.classifier(bert_output)
                logits = outputs.view(-1)
                loss = criterion(logits, labels)
                
                # ååä¼ æ­
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                num_batches += 1
                
                if (i + 1) % 10 == 0:
                    avg_loss = total_loss / num_batches
                    print(f"Epoch [{epoch+1}/{num_epochs}], Step [{i+1}], Loss: {avg_loss:.4f}")
                    total_loss = 0
                    num_batches = 0
            
            # å­¦ä¹ çè¡°å?
            scheduler.step()
            
            # ä¿å­æ¯ä¸ªepochçæ¨¡å?
            if kwargs.get('save_each_epoch', False):
                epoch_model_path = f"./model/bert_epoch_{epoch+1}.pth"
                os.makedirs(os.path.dirname(epoch_model_path), exist_ok=True)
                torch.save(self.classifier.state_dict(), epoch_model_path)
                print(f"å·²ä¿å­æ¨¡å? {epoch_model_path}")
        
        self.is_trained = True
        print(f"{self.model_name} æ¨¡åè®­ç»å®æï¼?)
    
    def predict(self, texts: List[str]) -> List[int]:
        """é¢æµææ¬ææ"""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼è¯·åè°ç¨trainæ¹æ³")
        
        predictions = []
        batch_size = 32
        
        self.bert.eval()
        self.classifier.eval()
        
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                
                # åè¯åç¼ç ?
                tokens = self.tokenizer(batch_texts, padding=True, truncation=True,
                                      max_length=512, return_tensors='pt')
                input_ids = tokens["input_ids"].to(self.device)
                attention_mask = tokens["attention_mask"].to(self.device)
                
                # è·åBERTè¾åº
                bert_outputs = self.bert(input_ids, attention_mask=attention_mask)
                bert_output = bert_outputs[0][:, 0]
                
                # åç±»å¨é¢æµ?
                outputs = self.classifier(bert_output)
                outputs = outputs.view(-1)
                
                # è½¬æ¢ä¸ºç±»å«æ ç­?
                preds = (outputs > 0.5).cpu().numpy()
                predictions.extend(preds.astype(int).tolist())
        
        return predictions
    
    def predict_single(self, text: str) -> Tuple[int, float]:
        """é¢æµåæ¡ææ¬çææ?""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼è¯·åè°ç¨trainæ¹æ³")
        
        self.bert.eval()
        self.classifier.eval()
        
        with torch.no_grad():
            # åè¯åç¼ç ?
            tokens = self.tokenizer([text], padding=True, truncation=True,
                                  max_length=512, return_tensors='pt')
            input_ids = tokens["input_ids"].to(self.device)
            attention_mask = tokens["attention_mask"].to(self.device)
            
            # è·åBERTè¾åº
            bert_outputs = self.bert(input_ids, attention_mask=attention_mask)
            bert_output = bert_outputs[0][:, 0]
            
            # åç±»å¨é¢æµ?
            output = self.classifier(bert_output)
            prob = output.item()
            
            prediction = int(prob > 0.5)
            confidence = prob if prediction == 1 else 1 - prob
        
        return prediction, confidence
    
    def save_model(self, model_path: str = None) -> None:
        """ä¿å­æ¨¡å"""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼æ æ³ä¿å­?)
        
        if model_path is None:
            model_path = f"./model/{self.model_name.lower()}_model.pth"
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # ä¿å­åç±»å¨åç¸å³ä¿¡æ¯
        model_data = {
            'classifier_state_dict': self.classifier.state_dict(),
            'model_path': self.model_path,
            'input_size': 768,
            'device': str(self.device)
        }
        
        torch.save(model_data, model_path)
        print(f"æ¨¡åå·²ä¿å­å°: {model_path}")
    
    def load_model(self, model_path: str) -> None:
        """å è½½æ¨¡å"""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"æ¨¡åæä»¶ä¸å­å? {model_path}")
        
        model_data = torch.load(model_path, map_location=self.device)
        
        # è®¾ç½®BERTæ¨¡åè·¯å¾
        self.model_path = model_data['model_path']
        
        # å è½½BERT
        self._load_bert()
        
        # éå»ºåç±»å?
        input_size = model_data['input_size']
        self.classifier = BertClassifier(input_size).to(self.device)
        
        # å è½½åç±»å¨æé?
        self.classifier.load_state_dict(model_data['classifier_state_dict'])
        
        self.is_trained = True
        print(f"å·²å è½½æ¨¡å? {model_path}")
    
    @staticmethod
    def load_data(train_path: str, test_path: str) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]:
        """å è½½BERTæ ¼å¼çæ°æ?""
        print("å è½½è®­ç»æ°æ®...")
        train_data = load_corpus_bert(train_path)
        print(f"è®­ç»æ°æ®é? {len(train_data)}")
        
        print("å è½½æµè¯æ°æ®...")
        test_data = load_corpus_bert(test_path)
        print(f"æµè¯æ°æ®é? {len(test_data)}")
        
        return train_data, test_data


def main():
    """ä¸»å½æ?""
    parser = argparse.ArgumentParser(description='BERTææåææ¨¡åè®­ç»')
    parser.add_argument('--train_path', type=str, default='./data/weibo2018/train.txt',
                        help='è®­ç»æ°æ®è·¯å¾')
    parser.add_argument('--test_path', type=str, default='./data/weibo2018/test.txt',
                        help='æµè¯æ°æ®è·¯å¾')
    parser.add_argument('--model_path', type=str, default='./model/bert_model.pth',
                        help='æ¨¡åä¿å­è·¯å¾')
    parser.add_argument('--bert_path', type=str, default='./model/chinese_wwm_pytorch',
                        help='BERTé¢è®­ç»æ¨¡åè·¯å¾?)
    parser.add_argument('--epochs', type=int, default=10,
                        help='è®­ç»è½®æ°')
    parser.add_argument('--batch_size', type=int, default=100,
                        help='æ¹å¤§å°?)
    parser.add_argument('--learning_rate', type=float, default=1e-3,
                        help='å­¦ä¹ ç?)
    parser.add_argument('--eval_only', action='store_true',
                        help='ä»è¯ä¼°å·²ææ¨¡åï¼ä¸è¿è¡è®­ç»?)
    
    args = parser.parse_args()
    
    # åå»ºæ¨¡å
    model = BertModel_Custom(args.bert_path)
    
    if args.eval_only:
        # ä»è¯ä¼°æ¨¡å¼?
        print("è¯ä¼°æ¨¡å¼ï¼å è½½å·²ææ¨¡åè¿è¡è¯ä¼?)
        model.load_model(args.model_path)
        
        # å è½½æµè¯æ°æ®
        _, test_data = model.load_data(args.train_path, args.test_path)
        
        # è¯ä¼°æ¨¡å
        model.evaluate(test_data)
    else:
        # è®­ç»æ¨¡å¼
        # å è½½æ°æ®
        train_data, test_data = model.load_data(args.train_path, args.test_path)
        
        # è®­ç»æ¨¡å
        model.train(
            train_data,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate
        )
        
        # è¯ä¼°æ¨¡å
        model.evaluate(test_data)
        
        # ä¿å­æ¨¡å
        model.save_model(args.model_path)
        
        # ç¤ºä¾é¢æµ
        print("\nç¤ºä¾é¢æµ:")
        test_texts = [
            "ä»å¤©å¤©æ°çå¥½ï¼å¿æå¾æ£?,
            "è¿é¨çµå½±å¤ªæ èäºï¼æµªè´¹æ¶é?,
            "åååï¼å¤ªæè¶£äº"
        ]
        
        for text in test_texts:
            pred, conf = model.predict_single(text)
            sentiment = "æ­£é¢" if pred == 1 else "è´é¢"
            print(f"ææ¬: {text}")
            print(f"é¢æµ: {sentiment} (ç½®ä¿¡åº? {conf:.4f})")
            print()


if __name__ == "__main__":
    main()
