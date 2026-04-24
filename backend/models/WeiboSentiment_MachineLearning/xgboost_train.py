# -*- coding: utf-8 -*-
"""
XGBoostææåææ¨¡åè®­ç»èæ¬
"""
import argparse
import pandas as pd
import numpy as np
from typing import List, Tuple
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
import xgboost as xgb

from base_model import BaseModel
from utils import stopwords


class XGBoostModel(BaseModel):
    """XGBoostææåææ¨¡å"""
    
    def __init__(self):
        super().__init__("XGBoost")
        
    def train(self, train_data: List[Tuple[str, int]], **kwargs) -> None:
        """è®­ç»XGBoostæ¨¡å
        
        Args:
            train_data: è®­ç»æ°æ®ï¼æ ¼å¼ä¸º[(text, label), ...]
            **kwargs: å¶ä»åæ°ï¼æ¯æXGBoostçåç§åæ?
        """
        print(f"å¼å§è®­ç»?{self.model_name} æ¨¡å...")
        
        # åå¤æ°æ®
        df_train = pd.DataFrame(train_data, columns=["words", "label"])
        
        # ç¹å¾ç¼ç ï¼è¯è¢æ¨¡åï¼éå¶ç¹å¾æ°éï¼?
        max_features = kwargs.get('max_features', 2000)
        print(f"æå»ºè¯è¢æ¨¡å (max_features={max_features})...")
        self.vectorizer = CountVectorizer(
            token_pattern=r'\[?\w+\]?', 
            stop_words=stopwords,
            max_features=max_features
        )
        
        X_train = self.vectorizer.fit_transform(df_train["words"])
        y_train = df_train["label"]
        
        print(f"ç¹å¾ç»´åº¦: {X_train.shape[1]}")
        
        # XGBooståæ°è®¾ç½®
        params = {
            'booster': kwargs.get('booster', 'gbtree'),
            'max_depth': kwargs.get('max_depth', 6),
            'scale_pos_weight': kwargs.get('scale_pos_weight', 0.5),
            'colsample_bytree': kwargs.get('colsample_bytree', 0.8),
            'objective': 'binary:logistic',
            'eval_metric': 'error',
            'eta': kwargs.get('eta', 0.3),
            'nthread': kwargs.get('nthread', 10),
        }
        
        num_boost_round = kwargs.get('num_boost_round', 200)
        
        print(f"è®­ç»XGBooståç±»å?..")
        print(f"åæ°: {params}")
        print(f"è¿­ä»£è½®æ°: {num_boost_round}")
        
        # åå»ºDMatrix
        dmatrix = xgb.DMatrix(X_train, label=y_train)
        
        # è®­ç»æ¨¡å
        self.model = xgb.train(params, dmatrix, num_boost_round=num_boost_round)
        
        self.is_trained = True
        print(f"{self.model_name} æ¨¡åè®­ç»å®æï¼?)
        
    def predict(self, texts: List[str]) -> List[int]:
        """é¢æµææ¬ææ
        
        Args:
            texts: å¾é¢æµææ¬åè¡?
            
        Returns:
            é¢æµç»æåè¡¨
        """
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼è¯·åè°ç¨trainæ¹æ³")
            
        # ç¹å¾è½¬æ¢
        X = self.vectorizer.transform(texts)
        
        # åå»ºDMatrix
        dmatrix = xgb.DMatrix(X)
        
        # é¢æµæ¦ç
        y_prob = self.model.predict(dmatrix)
        
        # è½¬æ¢ä¸ºç±»å«æ ç­?
        y_pred = (y_prob > 0.5).astype(int)
        
        return y_pred.tolist()
    
    def predict_single(self, text: str) -> Tuple[int, float]:
        """é¢æµåæ¡ææ¬çææ?
        
        Args:
            text: å¾é¢æµææ?
            
        Returns:
            (predicted_label, confidence)
        """
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼è¯·åè°ç¨trainæ¹æ³")
            
        # ç¹å¾è½¬æ¢
        X = self.vectorizer.transform([text])
        
        # åå»ºDMatrix
        dmatrix = xgb.DMatrix(X)
        
        # é¢æµæ¦ç
        prob = self.model.predict(dmatrix)[0]
        
        # è½¬æ¢ä¸ºç±»å«æ ç­¾åç½®ä¿¡åº?
        prediction = int(prob > 0.5)
        confidence = prob if prediction == 1 else 1 - prob
        
        return prediction, float(confidence)
    
    def evaluate(self, test_data: List[Tuple[str, int]]) -> dict:
        """è¯ä¼°æ¨¡åæ§è½ï¼åå«AUCææ """
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»ï¼è¯·åè°ç¨trainæ¹æ³")
            
        texts = [item[0] for item in test_data]
        labels = [item[1] for item in test_data]
        
        # é¢æµç±»å«
        predictions = self.predict(texts)
        
        # é¢æµæ¦çï¼ç¨äºè®¡ç®AUCï¼?
        X = self.vectorizer.transform(texts)
        dmatrix = xgb.DMatrix(X)
        probabilities = self.model.predict(dmatrix)
        
        accuracy = accuracy_score(labels, predictions)
        f1 = f1_score(labels, predictions, average='weighted')
        auc = roc_auc_score(labels, probabilities)
        
        print(f"\n{self.model_name} æ¨¡åè¯ä¼°ç»æ:")
        print(f"åç¡®ç? {accuracy:.4f}")
        print(f"F1åæ°: {f1:.4f}")
        print(f"AUC: {auc:.4f}")
        
        return {
            'accuracy': accuracy,
            'f1_score': f1,
            'auc': auc
        }


def main():
    """ä¸»å½æ?""
    parser = argparse.ArgumentParser(description='XGBoostææåææ¨¡åè®­ç»')
    parser.add_argument('--train_path', type=str, default='./data/weibo2018/train.txt',
                        help='è®­ç»æ°æ®è·¯å¾')
    parser.add_argument('--test_path', type=str, default='./data/weibo2018/test.txt',
                        help='æµè¯æ°æ®è·¯å¾')
    parser.add_argument('--model_path', type=str, default='./model/xgboost_model.pkl',
                        help='æ¨¡åä¿å­è·¯å¾')
    parser.add_argument('--max_features', type=int, default=2000,
                        help='æå¤§ç¹å¾æ°é?)
    parser.add_argument('--max_depth', type=int, default=6,
                        help='XGBoostæå¤§æ·±åº?)
    parser.add_argument('--eta', type=float, default=0.3,
                        help='XGBoostå­¦ä¹ ç?)
    parser.add_argument('--num_boost_round', type=int, default=200,
                        help='XGBoostè¿­ä»£è½®æ°')
    parser.add_argument('--eval_only', action='store_true',
                        help='ä»è¯ä¼°å·²ææ¨¡åï¼ä¸è¿è¡è®­ç»?)
    
    args = parser.parse_args()
    
    # åå»ºæ¨¡å
    model = XGBoostModel()
    
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
            max_features=args.max_features,
            max_depth=args.max_depth,
            eta=args.eta,
            num_boost_round=args.num_boost_round
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
