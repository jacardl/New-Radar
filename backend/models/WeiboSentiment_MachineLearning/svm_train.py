# -*- coding: utf-8 -*-
"""
SVMææåææ¨¡åè®­ç»èæ¬
"""
import argparse
import pandas as pd
from typing import List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn import svm
from sklearn.metrics import accuracy_score, f1_score

from base_model import BaseModel
from utils import stopwords


class SVMModel(BaseModel):
    """SVMææåææ¨¡å"""
    
    def __init__(self):
        super().__init__("SVM")
        
    def train(self, train_data: List[Tuple[str, int]], **kwargs) -> None:
        """è®­ç»SVMæ¨¡å
        
        Args:
            train_data: è®­ç»æ°æ®ï¼æ ¼å¼ä¸º[(text, label), ...]
            **kwargs: å¶ä»åæ°ï¼æ¯ækernel, Cç­SVMåæ°
        """
        print(f"å¼å§è®­ç»?{self.model_name} æ¨¡å...")
        
        # åå¤æ°æ®
        df_train = pd.DataFrame(train_data, columns=["words", "label"])
        
        # ç¹å¾ç¼ç ï¼TF-IDFæ¨¡åï¼?
        print("æå»ºTF-IDFç¹å¾...")
        self.vectorizer = TfidfVectorizer(
            token_pattern=r'\[?\w+\]?', 
            stop_words=stopwords
        )
        
        X_train = self.vectorizer.fit_transform(df_train["words"])
        y_train = df_train["label"]
        
        print(f"ç¹å¾ç»´åº¦: {X_train.shape[1]}")
        
        # è·åSVMåæ°
        kernel = kwargs.get('kernel', 'rbf')
        C = kwargs.get('C', 1.0)
        gamma = kwargs.get('gamma', 'scale')
        
        # è®­ç»æ¨¡å
        print(f"è®­ç»SVMåç±»å?(kernel={kernel}, C={C}, gamma={gamma})...")
        self.model = svm.SVC(kernel=kernel, C=C, gamma=gamma, probability=True)
        self.model.fit(X_train, y_train)
        
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
        
        # é¢æµ
        predictions = self.model.predict(X)
        
        return predictions.tolist()
    
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
        
        # é¢æµ
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        confidence = max(probabilities)
        
        return int(prediction), float(confidence)


def main():
    """ä¸»å½æ?""
    parser = argparse.ArgumentParser(description='SVMææåææ¨¡åè®­ç»')
    parser.add_argument('--train_path', type=str, default='./data/weibo2018/train.txt',
                        help='è®­ç»æ°æ®è·¯å¾')
    parser.add_argument('--test_path', type=str, default='./data/weibo2018/test.txt',
                        help='æµè¯æ°æ®è·¯å¾')
    parser.add_argument('--model_path', type=str, default='./model/svm_model.pkl',
                        help='æ¨¡åä¿å­è·¯å¾')
    parser.add_argument('--kernel', type=str, default='rbf', choices=['linear', 'poly', 'rbf', 'sigmoid'],
                        help='SVMæ ¸å½æ°ç±»å?)
    parser.add_argument('--C', type=float, default=1.0,
                        help='SVMæ­£åååæ°C')
    parser.add_argument('--gamma', type=str, default='scale',
                        help='SVMæ ¸å½æ°åæ°gamma')
    parser.add_argument('--eval_only', action='store_true',
                        help='ä»è¯ä¼°å·²ææ¨¡åï¼ä¸è¿è¡è®­ç»?)
    
    args = parser.parse_args()
    
    # åå»ºæ¨¡å
    model = SVMModel()
    
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
        model.train(train_data, kernel=args.kernel, C=args.C, gamma=args.gamma)
        
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
