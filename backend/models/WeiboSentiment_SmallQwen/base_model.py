# -*- coding: utf-8 -*-
"""
Qwen3æ¨¡ååºç¡ç±»ï¼ç»ä¸æ¥å£
"""
import os
import pickle
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.model_selection import train_test_split


class BaseQwenModel(ABC):
    """Qwen3ææåææ¨¡ååºç±»"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None
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
    
    @abstractmethod
    def save_model(self, model_path: str = None) -> None:
        """ä¿å­æ¨¡åå°æä»?""
        pass
    
    @abstractmethod
    def load_model(self, model_path: str) -> None:
        """ä»æä»¶å è½½æ¨¡å?""
        pass
    
    @staticmethod
    def load_data(train_path: str = None, test_path: str = None, csv_path: str = 'dataset/weibo_senti_100k.csv') -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]:
        """å è½½è®­ç»åæµè¯æ°æ?
        
        Args:
            train_path: è®­ç»æ°æ®txtæä»¶è·¯å¾ï¼å¯éï¼
            test_path: æµè¯æ°æ®txtæä»¶è·¯å¾ï¼å¯éï¼
            csv_path: CSVæ°æ®æä»¶è·¯å¾ï¼é»è®¤ä½¿ç¨ï¼
        """
        
        # ä¼åå°è¯ä½¿ç¨CSVæä»¶
        if os.path.exists(csv_path):
            print(f"ä»CSVæä»¶å è½½æ°æ®: {csv_path}")
            df = pd.read_csv(csv_path)
            
            # æ£æ¥æ°æ®æ ¼å¼?
            if 'review' in df.columns and 'label' in df.columns:
                # å°DataFrameè½¬æ¢ä¸ºåç»åè¡?
                data = [(row['review'], row['label']) for _, row in df.iterrows()]
                
                # åå²è®­ç»åæµè¯æ°æ®ï¼åºå®æµè¯éä¸º5000æ?
                total_samples = len(data)
                if total_samples > 5000:
                    test_size = 5000
                    train_data, test_data = train_test_split(
                        data, 
                        test_size=test_size, 
                        random_state=42, 
                        stratify=[label for _, label in data]
                    )
                else:
                    # å¦ææ»æ°æ®ä¸è¶?000æ¡ï¼ä½¿ç¨20%ä½ä¸ºæµè¯é?
                    train_data, test_data = train_test_split(
                        data, 
                        test_size=0.2, 
                        random_state=42, 
                        stratify=[label for _, label in data]
                    )
                
                print(f"è®­ç»æ°æ®é? {len(train_data)}")
                print(f"æµè¯æ°æ®é? {len(test_data)}")
                
                return train_data, test_data
            else:
                print(f"CSVæä»¶æ ¼å¼ä¸æ­£ç¡®ï¼ç¼ºå°'review'æ?label'å?)
        
        # å¦æCSVä¸å­å¨ï¼å°è¯ä½¿ç¨txtæä»¶
        elif train_path and test_path and os.path.exists(train_path) and os.path.exists(test_path):
            def load_corpus(path):
                data = []
                with open(path, "r", encoding="utf8") as f:
                    for line in f:
                        parts = line.strip().split("\t")
                        if len(parts) >= 2:
                            content = parts[0]
                            sentiment = int(parts[1])
                            data.append((content, sentiment))
                return data
            
            print("ä»txtæä»¶å è½½è®­ç»æ°æ®...")
            train_data = load_corpus(train_path)
            print(f"è®­ç»æ°æ®é? {len(train_data)}")
            
            print("ä»txtæä»¶å è½½æµè¯æ°æ®...")
            test_data = load_corpus(test_path)
            print(f"æµè¯æ°æ®é? {len(test_data)}")
            
            return train_data, test_data
        
        else:
            # å¦æé½æ²¡æï¼æä¾æ ·ä¾æ°æ®åå»ºæå¯¼
            print("æªæ¾å°æ°æ®æä»?")
            print("è¯·ç¡®ä¿ä»¥ä¸æä»¶ä¹ä¸å­å¨:")
            print(f"1. CSVæä»¶: {csv_path}")
            print(f"2. txtæä»¶: {train_path} å?{test_path}")
            print("\næ°æ®æ ¼å¼è¦æ±:")
            print("CSVæä»¶: åå«'review'å?label'å?)
            print("txtæä»¶: æ¯è¡æ ¼å¼ä¸?ææ¬åå®¹\\tæ ç­¾'")
            
            # åå»ºæ ·ä¾æ°æ®
            sample_data = [
                ("ä»å¤©å¤©æ°çå¥½ï¼å¿æå¾æ£?", 1),
                ("è¿é¨çµå½±å¤ªæ èäº", 0),
                ("éå¸¸åæ¬¢è¿ä¸ªäº§å", 1),
                ("æå¡æåº¦å¾å·®", 0),
                ("è´¨éä¸éï¼å¼å¾æ¨è", 1)
            ]
            
            print("ä½¿ç¨æ ·ä¾æ°æ®è¿è¡æ¼ç¤º...")
            train_data = sample_data * 20  # æ©åæ ·ä¾æ°æ®
            test_data = sample_data * 5
            
            return train_data, test_data
