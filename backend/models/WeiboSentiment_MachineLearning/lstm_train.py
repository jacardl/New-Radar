# -*- coding: utf-8 -*-
"""
LSTMææåææ¨¡åè®­ç»èæ¬
"""
import argparse
import os
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence, pack_padded_sequence, pad_packed_sequence
from gensim import models
from sklearn.metrics import accuracy_score, f1_score, classification_report, roc_auc_score
from typing import List, Tuple, Dict, Any
import numpy as np

from base_model import BaseModel


class LSTMDataset(Dataset):
    """LSTMæ°æ®é?""
    
    def __init__(self, data: List[Tuple[str, int]], word2vec_model):
        self.data = []
        self.label = []
        
        for text, label in data:
            vectors = []
            for word in text.split(" "):
                if word in word2vec_model.wv.key_to_index:
                    vectors.append(word2vec_model.wv[word])
            
            if len(vectors) > 0:  # ç¡®ä¿æææçè¯åé?
                vectors = torch.Tensor(vectors)
                self.data.append(vectors)
                self.label.append(label)
    
    def __getitem__(self, index):
        return self.data[index], self.label[index]
    
    def __len__(self):
        return len(self.label)


def collate_fn(data):
    """æ¹å¤çå½æ?""
    data.sort(key=lambda x: len(x[0]), reverse=True)
    data_length = [len(sq[0]) for sq in data]
    x = [i[0] for i in data]
    y = [i[1] for i in data]
    data = pad_sequence(x, batch_first=True, padding_value=0)
    return data, torch.tensor(y, dtype=torch.float32), data_length


class LSTMNet(nn.Module):
    """LSTMç½ç»ç»æ"""
    
    def __init__(self, input_size, hidden_size, num_layers):
        super(LSTMNet, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                           batch_first=True, bidirectional=True)
        self.fc = nn.Linear(hidden_size * 2, 1)  # ååLSTM
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x, lengths):
        device = x.device
        h0 = torch.zeros(self.num_layers * 2, x.size(0), self.hidden_size).to(device)
        c0 = torch.zeros(self.num_layers * 2, x.size(0), self.hidden_size).to(device)
        
        packed_input = pack_padded_sequence(input=x, lengths=lengths, batch_first=True)
        packed_out, (h_n, h_c) = self.lstm(packed_input, (h0, c0))
        
        # ååLSTMï¼æ¼æ¥æåçéèç¶æ?
        lstm_out = torch.cat([h_n[-2], h_n[-1]], 1)
        out = self.fc(lstm_out)
        out = self.sigmoid(out)
        return out


class LSTMModel(BaseModel):
    """LSTMææåææ¨¡å"""
    
    def __init__(self):
        super().__init__("LSTM")
        self.word2vec_model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
    def _train_word2vec(self, train_data: List[Tuple[str, int]], **kwargs):
        """è®­ç»Word2Vecè¯åé?""
        print("è®­ç»Word2Vecè¯åé?..")
        
        # åå¤Word2Vecè¾å¥æ°æ®
        wv_input = [text.split(" ") for text, _ in train_data]
        
        vector_size = kwargs.get('vector_size', 64)
        min_count = kwargs.get('min_count', 1)
        epochs = kwargs.get('epochs', 1000)
        
        # è®­ç»Word2Vec
        self.word2vec_model = models.Word2Vec(
            wv_input,
            vector_size=vector_size,
            min_count=min_count,
            epochs=epochs
        )
        
        print(f"Word2Vecè®­ç»å®æï¼è¯åéç»´åº¦: {vector_size}")
        
    def train(self, train_data: List[Tuple[str, int]], **kwargs) -> None:
        """è®­ç»LSTMæ¨¡å"""
        print(f"å¼å§è®­ç»?{self.model_name} æ¨¡å...")
        
        # è®­ç»Word2Vec
        self._train_word2vec(train_data, **kwargs)
        
        # è¶åæ?
        learning_rate = kwargs.get('learning_rate', 5e-4)
        num_epochs = kwargs.get('num_epochs', 5)
        batch_size = kwargs.get('batch_size', 100)
        embed_size = kwargs.get('embed_size', 64)
        hidden_size = kwargs.get('hidden_size', 64)
        num_layers = kwargs.get('num_layers', 2)
        
        print(f"LSTMè¶åæ? lr={learning_rate}, epochs={num_epochs}, "
              f"batch_size={batch_size}, hidden_size={hidden_size}")
        
        # åå»ºæ°æ®é?
        train_dataset = LSTMDataset(train_data, self.word2vec_model)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, 
                                 collate_fn=collate_fn, shuffle=True)
        
        # åå»ºæ¨¡å
        self.model = LSTMNet(embed_size, hidden_size, num_layers).to(self.device)
        
        # æå¤±å½æ°åä¼åå¨
        criterion = nn.BCELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        
        # è®­ç»å¾ªç¯
        self.model.train()
        for epoch in range(num_epochs):
            total_loss = 0
            num_batches = 0
            
            for i, (x, labels, lengths) in enumerate(train_loader):
                x = x.to(self.device)
                labels = labels.to(self.device)
                
                # ååä¼ æ­
                outputs = self.model(x, lengths)
                logits = outputs.view(-1)
                loss = criterion(logits, labels)
                
                # ååä¼ æ­
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                num_batches += 1
                
                if (i + 1) % 10 == 0:
                    avg_loss = total_loss / num_batches
                    print(f"Epoch [{epoch+1}/{num_epochs}], Step [{i+1}], Loss: {avg_loss:.4f}")
            
            # ä¿å­æ¯ä¸ªepochçæ¨¡å?
            if kwargs.get('save_each_epoch', False):
                epoch_model_path = f"./model/lstm_epoch_{epoch+1}.pth"
                os.makedirs(os.path.dirname(epoch_model_path), exist_ok=True)
                torch.save(self.model.state_dict(), epoch_model_path)
                print(f"å·²ä¿å­æ¨¡å? {epoch_model_path}")
        
        self.is_trained = True
        print(f"{self.model_name} æ¨¡åè®­ç»å®æï¼?)
    
    def predict(self, texts: List[str]) -> List[int]:
        """é¢æµææ¬ææ"""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼è¯·åè°ç¨trainæ¹æ³")
        
        # åå»ºæ°æ®é?
        test_data = [(text, 0) for text in texts]  # æ ç­¾æ å³ç´§è¦
        test_dataset = LSTMDataset(test_data, self.word2vec_model)
        test_loader = DataLoader(test_dataset, batch_size=32, collate_fn=collate_fn)
        
        predictions = []
        self.model.eval()
        
        with torch.no_grad():
            for x, _, lengths in test_loader:
                x = x.to(self.device)
                outputs = self.model(x, lengths)
                outputs = outputs.view(-1)
                
                # è½¬æ¢ä¸ºç±»å«æ ç­?
                preds = (outputs > 0.5).cpu().numpy()
                predictions.extend(preds.astype(int).tolist())
        
        return predictions
    
    def predict_single(self, text: str) -> Tuple[int, float]:
        """é¢æµåæ¡ææ¬çææ?""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼è¯·åè°ç¨trainæ¹æ³")
        
        # è½¬æ¢ä¸ºè¯åé
        vectors = []
        for word in text.split(" "):
            if word in self.word2vec_model.wv.key_to_index:
                vectors.append(self.word2vec_model.wv[word])
        
        if len(vectors) == 0:
            return 0, 0.5  # å¦ææ²¡æææè¯åéï¼è¿åé»è®¤å?
        
        # è½¬æ¢ä¸ºtensor
        x = torch.Tensor(vectors).unsqueeze(0).to(self.device)  # æ·»å batchç»´åº¦
        lengths = [len(vectors)]
        
        self.model.eval()
        with torch.no_grad():
            output = self.model(x, lengths)
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
        
        # ä¿å­æ¨¡åç¶æåWord2Vec
        model_data = {
            'model_state_dict': self.model.state_dict(),
            'word2vec_model': self.word2vec_model,
            'model_config': {
                'embed_size': 64,
                'hidden_size': 64,
                'num_layers': 2
            },
            'device': str(self.device)
        }
        
        torch.save(model_data, model_path)
        print(f"æ¨¡åå·²ä¿å­å°: {model_path}")
    
    def load_model(self, model_path: str) -> None:
        """å è½½æ¨¡å"""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"æ¨¡åæä»¶ä¸å­å? {model_path}")
        
        model_data = torch.load(model_path, map_location=self.device)
        
        # å è½½Word2Vec
        self.word2vec_model = model_data['word2vec_model']
        
        # éå»ºLSTMç½ç»
        config = model_data['model_config']
        self.model = LSTMNet(
            config['embed_size'],
            config['hidden_size'],
            config['num_layers']
        ).to(self.device)
        
        # å è½½æ¨¡åæé
        self.model.load_state_dict(model_data['model_state_dict'])
        
        self.is_trained = True
        print(f"å·²å è½½æ¨¡å? {model_path}")


def main():
    """ä¸»å½æ?""
    parser = argparse.ArgumentParser(description='LSTMææåææ¨¡åè®­ç»')
    parser.add_argument('--train_path', type=str, default='./data/weibo2018/train.txt',
                        help='è®­ç»æ°æ®è·¯å¾')
    parser.add_argument('--test_path', type=str, default='./data/weibo2018/test.txt',
                        help='æµè¯æ°æ®è·¯å¾')
    parser.add_argument('--model_path', type=str, default='./model/lstm_model.pth',
                        help='æ¨¡åä¿å­è·¯å¾')
    parser.add_argument('--epochs', type=int, default=5,
                        help='è®­ç»è½®æ°')
    parser.add_argument('--batch_size', type=int, default=100,
                        help='æ¹å¤§å°?)
    parser.add_argument('--hidden_size', type=int, default=64,
                        help='LSTMéèå±å¤§å°?)
    parser.add_argument('--learning_rate', type=float, default=5e-4,
                        help='å­¦ä¹ ç?)
    parser.add_argument('--eval_only', action='store_true',
                        help='ä»è¯ä¼°å·²ææ¨¡åï¼ä¸è¿è¡è®­ç»?)
    
    args = parser.parse_args()
    
    # åå»ºæ¨¡å
    model = LSTMModel()
    
    if args.eval_only:
        # ä»è¯ä¼°æ¨¡å¼?
        print("è¯ä¼°æ¨¡å¼ï¼å è½½å·²ææ¨¡åè¿è¡è¯ä¼?)
        model.load_model(args.model_path)
        
        # å è½½æµè¯æ°æ®
        _, test_data = BaseModel.load_data(args.train_path, args.test_path)
        
        # è¯ä¼°æ¨¡å
        model.evaluate(test_data)
    else:
        # è®­ç»æ¨¡å¼
        # å è½½æ°æ®
        train_data, test_data = BaseModel.load_data(args.train_path, args.test_path)
        
        # è®­ç»æ¨¡å
        model.train(
            train_data,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
            hidden_size=args.hidden_size,
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
