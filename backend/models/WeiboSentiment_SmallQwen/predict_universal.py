#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen3å¾®åææåæç»ä¸é¢æµæ¥å£
æ¯æ0.6BBBä¸ç§è§æ ¼çEmbeddingåLoRAæ¨¡å
"""

import os
import sys
import argparse
import torch
from typing import List, Dict, Tuple, Any

# æ·»å å½åç®å½å°è·¯å¾?
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models_config import QWEN3_MODELS, MODEL_PATHS
from qwen3_embedding_universal import Qwen3EmbeddingUniversal
from qwen3_lora_universal import Qwen3LoRAUniversal


class Qwen3UniversalPredictor:
    """Qwen3ç»ä¸é¢æµå?""
    
    def __init__(self):
        self.models = {}  # å­å¨å·²å è½½çæ¨¡å {model_key: {model: obj, display_name: str}}
        
    def _get_model_key(self, model_type: str, model_size: str) -> str:
        """çææ¨¡åé®å?""
        return f"{model_type}_{model_size}"
    
    def load_model(self, model_type: str, model_size: str) -> None:
        """å è½½æå®çæ¨¡å?""
        if model_type not in ['embedding', 'lora']:
            raise ValueError(f"ä¸æ¯æçæ¨¡åç±»å: {model_type}")
        if model_size not in ['0.6B', '4B', '8B']:
            raise ValueError(f"ä¸æ¯æçæ¨¡åå¤§å°: {model_size}")
            
        model_path = MODEL_PATHS[model_type][model_size]
        model_key = self._get_model_key(model_type, model_size)
        
        # æ£æ¥è®­ç»å¥½çæ¨¡åæä»¶æ¯å¦å­å?
        if not os.path.exists(model_path):
            print(f"è®­ç»å¥½çæ¨¡åæä»¶ä¸å­å? {model_path}")
            print(f"è¯·åè®­ç» {model_type.upper()}-{model_size} æ¨¡åï¼ææ£æ¥æ¨¡åè·¯å¾éç½?)
            return
        
        print(f"å è½½ {model_type.upper()}-{model_size} æ¨¡å...")
        
        try:
            if model_type == 'embedding':
                model = Qwen3EmbeddingUniversal(model_size)
                model.load_model(model_path)
            else:  # lora
                model = Qwen3LoRAUniversal(model_size)
                model.load_model(model_path)
            
            self.models[model_key] = {
                'model': model,
                'display_name': f"Qwen3-{model_type.title()}-{model_size}"
            }
            print(f"{model_type.upper()}-{model_size} æ¨¡åå è½½æå")
            
        except Exception as e:
            print(f"å è½½ {model_type.upper()}-{model_size} æ¨¡åå¤±è´¥: {e}")
            print(f"è¿å¯è½æ¯å ä¸ºåºç¡æ¨¡åä¸è½½å¤±è´¥æè®­ç»å¥½çæ¨¡åæä»¶æå?)
    
    def load_all_models(self, model_dir: str = './models') -> None:
        """å è½½ææå¯ç¨çæ¨¡å"""
        print("å¼å§å è½½ææå¯ç¨çQwen3æ¨¡å...")
        
        loaded_count = 0
        for model_type in ['embedding', 'lora']:
            for model_size in ['0.6B', '4B', '8B']:
                try:
                    self.load_model(model_type, model_size)
                    loaded_count += 1
                except Exception as e:
                    print(f"è·³è¿ {model_type}-{model_size}: {e}")
        
        print(f"\nå·²å è½?{loaded_count} ä¸ªæ¨¡å?)
        self._print_loaded_models()
    
    def load_specific_models(self, model_configs: List[Tuple[str, str]]) -> None:
        """å è½½æå®çæ¨¡åéç½?
        Args:
            model_configs: [(model_type, model_size), ...] çåè¡?
        """
        print("å è½½æå®çQwen3æ¨¡å...")
        
        for model_type, model_size in model_configs:
            try:
                self.load_model(model_type, model_size)
            except Exception as e:
                print(f"è·³è¿ {model_type}-{model_size}: {e}")
        
        print(f"\nå·²å è½?{len(self.models)} ä¸ªæ¨¡å?)
        self._print_loaded_models()
    
    def _print_loaded_models(self):
        """æå°å·²å è½½çæ¨¡ååè¡¨"""
        if self.models:
            print("å·²å è½½æ¨¡å?")
            for model_info in self.models.values():
                print(f"  - {model_info['display_name']}")
        else:
            print("æ²¡ææåå è½½ä»»ä½æ¨¡å")
    
    def predict_single(self, text: str, model_key: str = None) -> Dict[str, Tuple[int, float]]:
        """åææ¬é¢æµ?
        Args:
            text: è¦é¢æµçææ¬
            model_key: æå®æ¨¡åé®å¼ï¼Noneè¡¨ç¤ºä½¿ç¨æææ¨¡å?
        Returns:
            {model_name: (prediction, confidence), ...}
        """
        results = {}
        
        if model_key and model_key in self.models:
            # ä½¿ç¨æå®æ¨¡å
            model_info = self.models[model_key]
            try:
                prediction, confidence = model_info['model'].predict_single(text)
                results[model_info['display_name']] = (prediction, confidence)
            except Exception as e:
                print(f"æ¨¡å {model_info['display_name']} é¢æµå¤±è´¥: {e}")
                results[model_info['display_name']] = (0, 0.0)
        else:
            # ä½¿ç¨æææ¨¡å?
            for model_info in self.models.values():
                try:
                    prediction, confidence = model_info['model'].predict_single(text)
                    results[model_info['display_name']] = (prediction, confidence)
                except Exception as e:
                    print(f"æ¨¡å {model_info['display_name']} é¢æµå¤±è´¥: {e}")
                    results[model_info['display_name']] = (0, 0.0)
        
        return results
    
    def predict_batch(self, texts: List[str]) -> Dict[str, List[int]]:
        """æ¹éé¢æµ"""
        results = {}
        
        for model_info in self.models.values():
            try:
                predictions = model_info['model'].predict(texts)
                results[model_info['display_name']] = predictions
            except Exception as e:
                print(f"æ¨¡å {model_info['display_name']} é¢æµå¤±è´¥: {e}")
                results[model_info['display_name']] = [0] * len(texts)
        
        return results
    
    def ensemble_predict(self, text: str) -> Tuple[int, float]:
        """éæé¢æµ"""
        if len(self.models) < 2:
            raise ValueError("éæé¢æµéè¦è³å°?ä¸ªæ¨¡å?)
        
        results = self.predict_single(text)
        
        # å æå¹³åï¼è¿éä½¿ç¨ç®åå¹³åï¼å¯ä»¥æ ¹æ®æ¨¡åæ§è½è°æ´æéï¼?
        total_weight = 0
        weighted_prob = 0
        
        for model_name, (pred, conf) in results.items():
            if conf > 0:  # åªèèææé¢æµ
                prob = conf if pred == 1 else 1 - conf
                weighted_prob += prob
                total_weight += 1
        
        if total_weight == 0:
            return 0, 0.5
        
        final_prob = weighted_prob / total_weight
        final_pred = int(final_prob > 0.5)
        final_conf = final_prob if final_pred == 1 else 1 - final_prob
        
        return final_pred, final_conf
    
    def _select_and_load_model(self):
        """è®©ç¨æ·éæ©å¹¶å è½½æ¨¡å?""
        print("Qwen3å¾®åææåæé¢æµç³»ç»")
        print("="*40)
        print("è¯·éæ©è¦ä½¿ç¨çæ¨¡å:")
        print("\næ¹æ³éæ©:")
        print("  1. Embedding + åç±»å¤?(æ¨çå¿«éï¼æ¾å­å ç¨å°?")
        print("  2. LoRAå¾®è° (æææ´å¥½ï¼æ¾å­å ç¨è¾å¤?")
        
        method_choice = None
        while method_choice not in ['1', '2']:
            method_choice = input("\nè¯·éæ©æ¹æ³ (1/2): ").strip()
            if method_choice not in ['1', '2']:
                print("æ æéæ©ï¼è¯·è¾å¥ 1 æ?2")
        
        method_type = "embedding" if method_choice == '1' else "lora"
        method_name = "Embedding + åç±»å¤? if method_choice == '1' else "LoRAå¾®è°"
        
        print(f"\nå·²éæ©: {method_name}")
        print("\næ¨¡åå¤§å°éæ©:")
        print("  1. 0.6B - è½»éçº§ï¼æ¨çå¿«é?)
        print("  2. 4B  - ä¸­ç­è§æ¨¡ï¼æ§è½åè¡¡") 
        print("  3. 8B  - å¤§è§æ¨¡ï¼æ§è½æä½?)
        
        size_choice = None
        while size_choice not in ['1', '2', '3']:
            size_choice = input("\nè¯·éæ©æ¨¡åå¤§å° (1/2/3): ").strip()
            if size_choice not in ['1', '2', '3']:
                print("æ æéæ©ï¼è¯·è¾å¥ 1 æ?3")
        
        size_map = {'1': '0.6B', '2': '4B', '3': '8B'}
        model_size = size_map[size_choice]
        
        print(f"å·²éæ©: Qwen3-{method_name}-{model_size}")
        print("æ­£å¨å è½½æ¨¡å...")
        
        try:
            self.load_model(method_type, model_size)
            print(f"æ¨¡åå è½½æå!")
        except Exception as e:
            print(f"æ¨¡åå è½½å¤±è´¥: {e}")
            print("è¯·æ£æ¥æ¨¡åæä»¶æ¯å¦å­å¨ï¼æåè¿è¡è®­ç»")
    
    def interactive_predict(self):
        """äº¤äºå¼é¢æµæ¨¡å¼?""
        if len(self.models) == 0:
            # è®©ç¨æ·éæ©è¦å è½½çæ¨¡å
            self._select_and_load_model()
            if len(self.models) == 0:
                print("æ²¡æå è½½ä»»ä½æ¨¡åï¼éåºé¢æµ?)
                return
        
        print("\n" + "="*60)
        print("Qwen3å¾®åææåæé¢æµç³»ç»")
        print("="*60)
        print("å·²å è½½æ¨¡å?")
        for model_info in self.models.values():
            print(f"   - {model_info['display_name']}")
        print("\nå½ä»¤æç¤º:")
        print("   è¾å¥ 'q' éåºç¨åº?)
        print("   è¾å¥ 'switch' åæ¢æ¨¡å")  
        print("   è¾å¥ 'models' æ¥çå·²å è½½æ¨¡å?)
        print("   è¾å¥ 'compare' æ¯è¾æææ¨¡åæ§è½")
        print("-"*60)
        
        while True:
            try:
                text = input("\nè¯·è¾å¥è¦åæçå¾®ååå®? ").strip()
                
                if text.lower() == 'q':
                    print("æè°¢ä½¿ç¨ï¼åè§ï¼")
                    break
                
                if text.lower() == 'models':
                    print("å·²å è½½æ¨¡å?")
                    for model_info in self.models.values():
                        print(f"   - {model_info['display_name']}")
                    continue
                
                if text.lower() == 'switch':
                    print("åæ¢æ¨¡å...")
                    self.models.clear()  # æ¸ç©ºå½åæ¨¡å
                    self._select_and_load_model()
                    if len(self.models) > 0:
                        print("æ¨¡ååæ¢æå!")
                        for model_info in self.models.values():
                            print(f"   å½åæ¨¡å: {model_info['display_name']}")
                    continue
                
                if text.lower() == 'compare':
                    test_text = input("è¯·è¾å¥è¦æ¯è¾çææ? ")
                    self._compare_models(test_text)
                    continue
                
                if not text:
                    print("è¯·è¾å¥ææåå®?)
                    continue
                
                # é¢æµ
                results = self.predict_single(text)
                
                print(f"\nåæ: {text}")
                print("é¢æµç»æ:")
                
                # ææ¨¡åç±»ååå¤§å°æåºæ¾ç¤º
                sorted_results = sorted(results.items())
                for model_name, (pred, conf) in sorted_results:
                    sentiment = "æ­£é¢" if pred == 1 else "è´é¢"
                    print(f"   {model_name:20}: {sentiment} (ç½®ä¿¡åº? {conf:.4f})")
                
                # åªæ¾ç¤ºåä¸ªæ¨¡åçé¢æµç»æï¼ä¸è¿è¡éæï¼?
                
            except KeyboardInterrupt:
                print("\n\nç¨åºè¢«ä¸­æ­ï¼åè§ï¼?)
                break
            except Exception as e:
                print(f"é¢æµè¿ç¨ä¸­åºç°éè¯? {e}")
    
    def _compare_models(self, text: str):
        """æ¯è¾ä¸åæ¨¡åçæ§è½"""
        print(f"\næ¨¡åæ§è½æ¯è¾ - ææ¬: {text}")
        print("-" * 60)
        
        results = self.predict_single(text)
        
        embedding_models = []
        lora_models = []
        
        for model_name, (pred, conf) in results.items():
            sentiment = "æ­£é¢" if pred == 1 else "è´é¢"
            if "Embedding" in model_name:
                embedding_models.append((model_name, sentiment, conf))
            elif "Lora" in model_name:
                lora_models.append((model_name, sentiment, conf))
        
        if embedding_models:
            print("Embedding + åç±»å¤´æ¹æ³?")
            for name, sentiment, conf in embedding_models:
                print(f"   {name}: {sentiment} ({conf:.4f})")
        
        if lora_models:
            print("LoRAå¾®è°æ¹æ³:")
            for name, sentiment, conf in lora_models:
                print(f"   {name}: {sentiment} ({conf:.4f})")


def main():
    """ä¸»å½æ?""
    parser = argparse.ArgumentParser(description='Qwen3å¾®åææåæç»ä¸é¢æµæ¥å£')
    parser.add_argument('--model_dir', type=str, default='./models',
                        help='æ¨¡åæä»¶ç®å½')
    parser.add_argument('--model_type', type=str, choices=['embedding', 'lora'],
                        help='æå®æ¨¡åç±»å')
    parser.add_argument('--model_size', type=str, choices=['0.6B', '4B', '8B'],
                        help='æå®æ¨¡åå¤§å°')
    parser.add_argument('--text', type=str,
                        help='ç´æ¥é¢æµæå®ææ¬')
    parser.add_argument('--interactive', action='store_true', default=True,
                        help='äº¤äºå¼é¢æµæ¨¡å¼ï¼é»è®¤ï¼?)
    parser.add_argument('--ensemble', action='store_true',
                        help='ä½¿ç¨éæé¢æµ')
    parser.add_argument('--load_all', action='store_true',
                        help='å è½½ææå¯ç¨æ¨¡å?)
    
    args = parser.parse_args()
    
    # åå»ºé¢æµå?
    predictor = Qwen3UniversalPredictor()
    
    # å è½½æ¨¡å
    if args.load_all:
        # å è½½æææ¨¡å?
        predictor.load_all_models(args.model_dir)
    elif args.model_type and args.model_size:
        # å è½½æå®æ¨¡å
        predictor.load_model(args.model_type, args.model_size)
    # å¦ææ²¡ææå®æ¨¡åï¼äº¤äºå¼æ¨¡å¼ä¼è®©ç¨æ·éæ©
    
    # å¦ææå®äºææ¬ï¼ç´æ¥é¢æµ
    if args.text:
        if args.ensemble and len(predictor.models) > 1:
            pred, conf = predictor.ensemble_predict(args.text)
            sentiment = "æ­£é¢" if pred == 1 else "è´é¢"
            print(f"ææ¬: {args.text}")
            print(f"éæé¢æµ: {sentiment} (ç½®ä¿¡åº? {conf:.4f})")
        else:
            results = predictor.predict_single(args.text)
            print(f"ææ¬: {args.text}")
            for model_name, (pred, conf) in results.items():
                sentiment = "æ­£é¢" if pred == 1 else "è´é¢"
                print(f"{model_name}: {sentiment} (ç½®ä¿¡åº? {conf:.4f})")
    else:
        # è¿å¥äº¤äºå¼æ¨¡å¼?
        predictor.interactive_predict()


if __name__ == "__main__":
    main()
