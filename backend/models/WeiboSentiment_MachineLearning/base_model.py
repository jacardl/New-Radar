# -*- coding: utf-8 -*-
"""
åºç¡æ¨¡åç±»ï¼ä¸ºææææåææ¨¡åæä¾ç»ä¸æ¥å£
"""
import os
import pickle
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, classification_report
from utils import load_corpus


class BaseModel(ABC):
    """ææåææ¨¡ååºç±»"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None
        self.vectorizer = None
        self.is_trained = False
        
    @abstractmethod
    def train(self, train_data: List[Tuple[str, int]], **kwargs) -> None:
        """è®­ç»æ¨¡å"""
        pass
    
    @abstractmethod
    def predict(self, texts: List[str]) -> List[int]:
        """é¢æµææ¬ææ"""
        pass
    
    def predict_single(self, text: str) -> Tuple[int, float]:
        """é¢æµåæ¡ææ¬çææ?
        
        Args:
            text: å¾é¢æµææ?
            
        Returns:
            (predicted_label, confidence)
        """
        predictions = self.predict([text])
        return predictions[0], 0.0  # é»è®¤ç½®ä¿¡åº¦ä¸º0
    
    def evaluate(self, test_data: List[Tuple[str, int]]) -> Dict[str, float]:
        """è¯ä¼°æ¨¡åæ§è½"""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼è¯·åè°ç¨trainæ¹æ³")
            
        texts = [item[0] for item in test_data]
        labels = [item[1] for item in test_data]
        
        predictions = self.predict(texts)
        
        accuracy = accuracy_score(labels, predictions)
        f1 = f1_score(labels, predictions, average='weighted')
        
        print(f"\n{self.model_name} æ¨¡åè¯ä¼°ç»æ:")
        print(f"åç¡®ç? {accuracy:.4f}")
        print(f"F1åæ°: {f1:.4f}")
        print("\nè¯¦ç»æ¥å:")
        print(classification_report(labels, predictions))
        
        return {
            'accuracy': accuracy,
            'f1_score': f1,
            'classification_report': classification_report(labels, predictions)
        }
    
    def save_model(self, model_path: str = None) -> None:
        """ä¿å­æ¨¡åå°æä»?""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼æ æ³ä¿å­?)
            
        if model_path is None:
            model_path = f"model/{self.model_name}_model.pkl"
            
        # åå»ºä¿å­ç®å½
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # ä¿å­æ¨¡åæ°æ®
        model_data = {
            'model': self.model,
            'vectorizer': self.vectorizer,
            'model_name': self.model_name,
            'is_trained': self.is_trained
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
            
        print(f"æ¨¡åå·²ä¿å­å°: {model_path}")
    
    def load_model(self, model_path: str) -> None:
        """ä»æä»¶å è½½æ¨¡å?""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"æ¨¡åæä»¶ä¸å­å? {model_path}")
            
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
            
        self.model = model_data['model']
        self.vectorizer = model_data.get('vectorizer')
        self.model_name = model_data['model_name']
        self.is_trained = model_data['is_trained']
        
        print(f"å·²å è½½æ¨¡å? {model_path}")
    
    @staticmethod
    def load_data(train_path: str, test_path: str) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]:
        """å è½½è®­ç»åæµè¯æ°æ?""
        print("å è½½è®­ç»æ°æ®...")
        train_data = load_corpus(train_path)
        print(f"è®­ç»æ°æ®é? {len(train_data)}")
        
        print("å è½½æµè¯æ°æ®...")
        test_data = load_corpus(test_path)
        print(f"æµè¯æ°æ®é? {len(test_data)}")
        
        return train_data, test_data
