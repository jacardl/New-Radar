# -*- coding: utf-8 -*-
"""
ç»ä¸çææåæé¢æµç¨åº?
æ¯æå è½½æææ¨¡åè¿è¡ææé¢æµ?
"""
import argparse
import os
import re
from typing import Dict, Tuple, List
import warnings
warnings.filterwarnings("ignore")

# å¯¼å¥æææ¨¡åç±»
from bayes_train import BayesModel
from svm_train import SVMModel
from xgboost_train import XGBoostModel
from lstm_train import LSTMModel
from bert_train import BertModel_Custom
from utils import processing


class SentimentPredictor:
    """ææåæé¢æµå?""
    
    def __init__(self):
        self.models = {}
        self.available_models = {
            'bayes': BayesModel,
            'svm': SVMModel,
            'xgboost': XGBoostModel,
            'lstm': LSTMModel,
            'bert': BertModel_Custom
        }
        
    def load_model(self, model_type: str, model_path: str, **kwargs) -> None:
        """å è½½æå®ç±»åçæ¨¡å?
        
        Args:
            model_type: æ¨¡åç±»å ('bayes', 'svm', 'xgboost', 'lstm', 'bert')
            model_path: æ¨¡åæä»¶è·¯å¾
            **kwargs: å¶ä»åæ°ï¼å¦BERTçé¢è®­ç»æ¨¡åè·¯å¾ï¼?
        """
        if model_type not in self.available_models:
            raise ValueError(f"ä¸æ¯æçæ¨¡åç±»å: {model_type}")
        
        if not os.path.exists(model_path):
            print(f"è­¦å: æ¨¡åæä»¶ä¸å­å? {model_path}")
            return
        
        print(f"å è½½ {model_type.upper()} æ¨¡å...")
        
        try:
            if model_type == 'bert':
                # BERTéè¦é¢å¤çé¢è®­ç»æ¨¡åè·¯å¾?
                bert_path = kwargs.get('bert_path', './model/chinese_wwm_pytorch')
                model = BertModel_Custom(bert_path)
            else:
                model = self.available_models[model_type]()
            
            model.load_model(model_path)
            self.models[model_type] = model
            print(f"{model_type.upper()} æ¨¡åå è½½æå")
            
        except Exception as e:
            print(f"å è½½ {model_type.upper()} æ¨¡åå¤±è´¥: {e}")
    
    def load_all_models(self, model_dir: str = './model', bert_path: str = './model/chinese_wwm_pytorch') -> None:
        """å è½½ææå¯ç¨çæ¨¡å
        
        Args:
            model_dir: æ¨¡åæä»¶ç®å½
            bert_path: BERTé¢è®­ç»æ¨¡åè·¯å¾?
        """
        model_files = {
            'bayes': os.path.join(model_dir, 'bayes_model.pkl'),
            'svm': os.path.join(model_dir, 'svm_model.pkl'),
            'xgboost': os.path.join(model_dir, 'xgboost_model.pkl'),
            'lstm': os.path.join(model_dir, 'lstm_model.pth'),
            'bert': os.path.join(model_dir, 'bert_model.pth')
        }
        
        print("å¼å§å è½½ææå¯ç¨æ¨¡å?..")
        for model_type, model_path in model_files.items():
            self.load_model(model_type, model_path, bert_path=bert_path)
        
        print(f"\nå·²å è½?{len(self.models)} ä¸ªæ¨¡å? {list(self.models.keys())}")
    
    def predict_single(self, text: str, model_type: str = None) -> Dict[str, Tuple[int, float]]:
        """é¢æµåæ¡ææ¬çææ?
        
        Args:
            text: å¾é¢æµææ?
            model_type: æå®æ¨¡åç±»åï¼å¦æä¸ºNoneåä½¿ç¨ææå·²å è½½çæ¨¡å?
            
        Returns:
            Dict[model_type, (prediction, confidence)]
        """
        # ææ¬é¢å¤ç?
        processed_text = processing(text)
        
        if model_type:
            if model_type not in self.models:
                raise ValueError(f"æ¨¡å {model_type} æªå è½?)
            
            prediction, confidence = self.models[model_type].predict_single(processed_text)
            return {model_type: (prediction, confidence)}
        
        # ä½¿ç¨æææ¨¡åé¢æµ?
        results = {}
        for name, model in self.models.items():
            try:
                prediction, confidence = model.predict_single(processed_text)
                results[name] = (prediction, confidence)
            except Exception as e:
                print(f"æ¨¡å {name} é¢æµå¤±è´¥: {e}")
                results[name] = (0, 0.0)
        
        return results
    
    def predict_batch(self, texts: List[str], model_type: str = None) -> Dict[str, List[int]]:
        """æ¹éé¢æµææ¬ææ
        
        Args:
            texts: å¾é¢æµææ¬åè¡?
            model_type: æå®æ¨¡åç±»åï¼å¦æä¸ºNoneåä½¿ç¨ææå·²å è½½çæ¨¡å?
            
        Returns:
            Dict[model_type, predictions]
        """
        # ææ¬é¢å¤ç?
        processed_texts = [processing(text) for text in texts]
        
        if model_type:
            if model_type not in self.models:
                raise ValueError(f"æ¨¡å {model_type} æªå è½?)
            
            predictions = self.models[model_type].predict(processed_texts)
            return {model_type: predictions}
        
        # ä½¿ç¨æææ¨¡åé¢æµ?
        results = {}
        for name, model in self.models.items():
            try:
                predictions = model.predict(processed_texts)
                results[name] = predictions
            except Exception as e:
                print(f"æ¨¡å {name} é¢æµå¤±è´¥: {e}")
                results[name] = [0] * len(texts)
        
        return results
    
    def ensemble_predict(self, text: str, weights: Dict[str, float] = None) -> Tuple[int, float]:
        """éæé¢æµï¼å¤ä¸ªæ¨¡åæç¥¨ï¼
        
        Args:
            text: å¾é¢æµææ?
            weights: æ¨¡åæéï¼å¦æä¸ºNoneåå¹³åæé?
            
        Returns:
            (prediction, confidence)
        """
        if len(self.models) == 0:
            raise ValueError("æ²¡æå è½½ä»»ä½æ¨¡å")
        
        results = self.predict_single(text)
        
        if weights is None:
            weights = {name: 1.0 for name in results.keys()}
        
        # å æå¹³å
        total_weight = 0
        weighted_prob = 0
        
        for model_name, (pred, conf) in results.items():
            if model_name in weights:
                weight = weights[model_name]
                prob = conf if pred == 1 else 1 - conf
                weighted_prob += prob * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0, 0.5
        
        final_prob = weighted_prob / total_weight
        final_pred = int(final_prob > 0.5)
        final_conf = final_prob if final_pred == 1 else 1 - final_prob
        
        return final_pred, final_conf
    
    def interactive_predict(self):
        """äº¤äºå¼é¢æµæ¨¡å¼?""
        if len(self.models) == 0:
            print("éè¯¯: æ²¡æå è½½ä»»ä½æ¨¡åï¼è¯·åå è½½æ¨¡å?)
            return
        
        print("\n" + "="*50)
        print("="*50)
        print(f"å·²å è½½æ¨¡å? {', '.join(self.models.keys())}")
        print("è¾å¥ 'q' éåºç¨åº?)
        print("è¾å¥ 'models' æ¥çæ¨¡ååè¡¨")
        print("è¾å¥ 'ensemble' ä½¿ç¨éæé¢æµ")
        print("-"*50)
        
        while True:
            try:
                text = input("\nè¯·è¾å¥è¦åæçå¾®ååå®? ").strip()
                
                if text.lower() == 'q':
                    print("ð åè§ï¼?)
                    break
                
                if text.lower() == 'models':
                    print(f"å·²å è½½æ¨¡å? {list(self.models.keys())}")
                    continue
                
                if text.lower() == 'ensemble':
                    if len(self.models) > 1:
                        pred, conf = self.ensemble_predict(text)
                        sentiment = "ð æ­£é¢" if pred == 1 else "ð è´é¢"
                        print(f"\nð¤ éæé¢æµç»æ:")
                        print(f"   ææå¾å: {sentiment}")
                        print(f"   ç½®ä¿¡åº? {conf:.4f}")
                    else:
                        print("â?éæé¢æµéè¦è³å°?ä¸ªæ¨¡å?)
                    continue
                
                if not text:
                    print("â?è¯·è¾å¥ææåå®?)
                    continue
                
                # é¢æµ
                results = self.predict_single(text)
                
                print(f"\nð åæ: {text}")
                print("ð é¢æµç»æ:")
                
                for model_name, (pred, conf) in results.items():
                    sentiment = "ð æ­£é¢" if pred == 1 else "ð è´é¢"
                    print(f"   {model_name.upper():8}: {sentiment} (ç½®ä¿¡åº? {conf:.4f})")
                
                # å¦ææå¤ä¸ªæ¨¡åï¼æ¾ç¤ºéæç»æ
                if len(results) > 1:
                    ensemble_pred, ensemble_conf = self.ensemble_predict(text)
                    ensemble_sentiment = "ð æ­£é¢" if ensemble_pred == 1 else "ð è´é¢"
                    print(f"   {'éæ':8}: {ensemble_sentiment} (ç½®ä¿¡åº? {ensemble_conf:.4f})")
                
            except KeyboardInterrupt:
                print("\n\nð ç¨åºè¢«ä¸­æ­ï¼åè§ï¼?)
                break
            except Exception as e:
                print(f"â?é¢æµè¿ç¨ä¸­åºç°éè¯? {e}")


def main():
    """ä¸»å½æ?""
    parser = argparse.ArgumentParser(description='å¾®åææåæç»ä¸é¢æµç¨åº')
    parser.add_argument('--model_dir', type=str, default='./model',
                        help='æ¨¡åæä»¶ç®å½')
    parser.add_argument('--bert_path', type=str, default='./model/chinese_wwm_pytorch',
                        help='BERTé¢è®­ç»æ¨¡åè·¯å¾?)
    parser.add_argument('--model_type', type=str, choices=['bayes', 'svm', 'xgboost', 'lstm', 'bert'],
                        help='æå®åä¸ªæ¨¡åç±»åè¿è¡é¢æµ')
    parser.add_argument('--text', type=str,
                        help='ç´æ¥é¢æµæå®ææ¬')
    parser.add_argument('--interactive', action='store_true', default=True,
                        help='äº¤äºå¼é¢æµæ¨¡å¼ï¼é»è®¤ï¼?)
    parser.add_argument('--ensemble', action='store_true',
                        help='ä½¿ç¨éæé¢æµ')
    
    args = parser.parse_args()
    
    # åå»ºé¢æµå?
    predictor = SentimentPredictor()
    
    # å è½½æ¨¡å
    if args.model_type:
        # å è½½æå®æ¨¡å
        model_files = {
            'bayes': 'bayes_model.pkl',
            'svm': 'svm_model.pkl',
            'xgboost': 'xgboost_model.pkl',
            'lstm': 'lstm_model.pth',
            'bert': 'bert_model.pth'
        }
        model_path = os.path.join(args.model_dir, model_files[args.model_type])
        predictor.load_model(args.model_type, model_path, bert_path=args.bert_path)
    else:
        # å è½½æææ¨¡å?
        predictor.load_all_models(args.model_dir, args.bert_path)
    
    # å¦ææå®äºææ¬ï¼ç´æ¥é¢æµ
    if args.text:
        if args.ensemble and len(predictor.models) > 1:
            pred, conf = predictor.ensemble_predict(args.text)
            sentiment = "æ­£é¢" if pred == 1 else "è´é¢"
            print(f"ææ¬: {args.text}")
            print(f"éæé¢æµ: {sentiment} (ç½®ä¿¡åº? {conf:.4f})")
        else:
            results = predictor.predict_single(args.text, args.model_type)
            print(f"ææ¬: {args.text}")
            for model_name, (pred, conf) in results.items():
                sentiment = "æ­£é¢" if pred == 1 else "è´é¢"
                print(f"{model_name.upper()}: {sentiment} (ç½®ä¿¡åº? {conf:.4f})")
    elif args.interactive:
        # äº¤äºå¼æ¨¡å¼?
        predictor.interactive_predict()


if __name__ == "__main__":
    main()
