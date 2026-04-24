# -*- coding: utf-8 -*-
"""
Qwen3-LoRAéç¨è®­ç»èæ¬
æ¯æ0.6BBBä¸ç§è§æ¨¡çæ¨¡å?
"""
import argparse
import os
import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    TrainingArguments, 
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType, PeftModel
from datasets import Dataset
from typing import List, Tuple
import warnings
from tqdm import tqdm

from base_model import BaseQwenModel
from models_config import QWEN3_MODELS, MODEL_PATHS

warnings.filterwarnings("ignore")


class Qwen3LoRAUniversal(BaseQwenModel):
    """éç¨Qwen3-LoRAæ¨¡å"""
    
    def __init__(self, model_size: str = "0.6B"):
        if model_size not in QWEN3_MODELS:
            raise ValueError(f"ä¸æ¯æçæ¨¡åå¤§å°: {model_size}")
            
        super().__init__(f"Qwen3-{model_size}-LoRA")
        self.model_size = model_size
        self.config = QWEN3_MODELS[model_size]
        self.model_name_hf = self.config["base_model"]
        
        self.tokenizer = None
        self.base_model = None
        self.lora_model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
    def _load_base_model(self):
        """å è½½Qwen3åºç¡æ¨¡å"""
        print(f"å è½½{self.model_size}åºç¡æ¨¡å: {self.model_name_hf}")
        
        # ç¬¬ä¸æ­¥ï¼æ£æ¥å½åæä»¶å¤¹çmodelsç®å½
        local_model_dir = f"./models/qwen3-{self.model_size.lower()}"
        if os.path.exists(local_model_dir) and os.path.exists(os.path.join(local_model_dir, "config.json")):
            try:
                print(f"åç°æ¬å°æ¨¡åï¼ä»æ¬å°å è½½: {local_model_dir}")
                self.tokenizer = AutoTokenizer.from_pretrained(local_model_dir)
                self.base_model = AutoModelForCausalLM.from_pretrained(
                    local_model_dir,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None
                )
                
                # è®¾ç½®pad_token
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                    self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
                
                print(f"ä»æ¬å°æ¨¡åå è½½{self.model_size}åºç¡æ¨¡åæå")
                return
                
            except Exception as e:
                print(f"æ¬å°æ¨¡åå è½½å¤±è´¥: {e}")
        
        # ç¬¬äºæ­¥ï¼æ£æ¥HuggingFaceç¼å­
        try:
            from transformers.utils import default_cache_path
            cache_path = default_cache_path
            print(f"æ£æ¥HuggingFaceç¼å­: {cache_path}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name_hf)
            self.base_model = AutoModelForCausalLM.from_pretrained(
                self.model_name_hf,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None
            )
            
            # è®¾ç½®pad_token
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
            
            print(f"ä»HuggingFaceç¼å­å è½½{self.model_size}åºç¡æ¨¡åæå")
            
            # ä¿å­å°æ¬å°modelsç®å½
            print(f"ä¿å­æ¨¡åå°æ¬å? {local_model_dir}")
            os.makedirs(local_model_dir, exist_ok=True)
            self.tokenizer.save_pretrained(local_model_dir)
            self.base_model.save_pretrained(local_model_dir)
            print(f"æ¨¡åå·²ä¿å­å°: {local_model_dir}")
            
        except Exception as e:
            print(f"ä»HuggingFaceç¼å­å è½½å¤±è´¥: {e}")
            
            # ç¬¬ä¸æ­¥ï¼ä»HuggingFaceä¸è½½
            try:
                print(f"æ­£å¨ä»HuggingFaceä¸è½½{self.model_size}æ¨¡å...")
                
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name_hf,
                    force_download=True
                )
                self.base_model = AutoModelForCausalLM.from_pretrained(
                    self.model_name_hf,
                    force_download=True,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None
                )
                
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                    self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
                
                # ä¿å­å°æ¬å°modelsç®å½
                os.makedirs(local_model_dir, exist_ok=True)
                self.tokenizer.save_pretrained(local_model_dir)
                self.base_model.save_pretrained(local_model_dir)
                print(f"{self.model_size}æ¨¡åä¸è½½å¹¶ä¿å­å°: {local_model_dir}")
                
            except Exception as e2:
                print(f"ä»HuggingFaceä¸è½½ä¹å¤±è´? {e2}")
                raise RuntimeError(f"æ æ³å è½½{self.model_size}æ¨¡åï¼æææ¹æ³é½å¤±è´¥äº?)
    
    def _create_instruction_data(self, data: List[Tuple[str, int]]) -> Dataset:
        """åå»ºæä»¤æ ¼å¼çè®­ç»æ°æ?""
        instructions = []
        
        for text, label in data:
            sentiment = "æ­£é¢" if label == 1 else "è´é¢"
            
            # æå»ºæä»¤æ ¼å¼
            instruction = f"è¯·åæä»¥ä¸å¾®åææ¬çææå¾åï¼åç­?æ­£é¢'æ?è´é¢'n\nææ¬ï¼{text}\n\nææï¼?
            response = sentiment
            
            
            # ç»åæå®æ´çè®­ç»ææ¬
            full_text = f"{instruction}{response}{self.tokenizer.eos_token}"
            
            instructions.append({
                "instruction": instruction,
                "response": response,
                "text": full_text
            })
        
        return Dataset.from_list(instructions)
    
    def _tokenize_function(self, examples):
        """åè¯å½æ°"""
        tokenized = self.tokenizer(
            examples["text"],
            truncation=True,
            padding="max_length",
            max_length=512,
            return_tensors=None
        )
        
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized
    
    def _setup_lora(self, **kwargs):
        """è®¾ç½®LoRAéç½®"""
        lora_r = kwargs.get('lora_r', self.config['lora_r'])
        lora_alpha = kwargs.get('lora_alpha', self.config['lora_alpha'])
        
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=kwargs.get('lora_dropout', 0.1),
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )
        
        self.lora_model = get_peft_model(self.base_model, lora_config)
        
        # ç»è®¡åæ°
        total_params = sum(p.numel() for p in self.lora_model.parameters())
        trainable_params = sum(p.numel() for p in self.lora_model.parameters() if p.requires_grad)
        
        print(f"LoRAéç½®å®æ (r={lora_r}, alpha={lora_alpha})")
        print(f"æ»åæ? {total_params:,}")
        print(f"å¯è®­ç»åæ? {trainable_params:,}")
        print(f"å¯è®­ç»åæ°æ¯ä¾? {trainable_params / total_params * 100:.2f}%")
        self.lora_model.print_trainable_parameters()  # PEFTåºèªå¸¦çåæ°ç»è®¡
        
        return lora_config
    
    def train(self, train_data: List[Tuple[str, int]], **kwargs) -> None:
        """è®­ç»æ¨¡å"""
        print(f"å¼å§è®­ç»?Qwen3-{self.model_size}-LoRA æ¨¡å...")
        
        # å è½½åºç¡æ¨¡å
        self._load_base_model()
        
        # è®¾ç½®LoRA
        self._setup_lora(**kwargs)
        
        # è¶åæ°ï¼ä½¿ç¨éç½®æä»¶çæ¨èå¼æç¨æ·æå®å¼ï¼
        num_epochs = kwargs.get('num_epochs', 3)
        batch_size = kwargs.get('batch_size', self.config['recommended_batch_size'] // 2)  # LoRAéè¦æ´å°æ¹å¤§å°
        learning_rate = kwargs.get('learning_rate', self.config['recommended_lr'] / 2)  # LoRAä½¿ç¨æ´å°å­¦ä¹ ç?
        output_dir = kwargs.get('output_dir', f'./models/qwen3_lora_{self.model_size.lower()}_checkpoints')
        
        print(f"è¶åæ? epochs={num_epochs}, batch_size={batch_size}, lr={learning_rate}")
        
        # åå»ºæä»¤æ ¼å¼æ°æ®
        train_dataset = self._create_instruction_data(train_data)
        
        # åè¯
        tokenized_dataset = train_dataset.map(
            self._tokenize_function,
            batched=True,
            remove_columns=train_dataset.column_names
        )
        
        # è®­ç»åæ°
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=2,
            learning_rate=learning_rate,
            logging_steps=10,
            save_steps=100,
            save_total_limit=2,
            remove_unused_columns=False,
            dataloader_drop_last=False,
            report_to=None,
        )
        
        # æ°æ®æ´çå?
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False,
        )
        
        # åå»ºè®­ç»å?
        trainer = Trainer(
            model=self.lora_model,
            args=training_args,
            train_dataset=tokenized_dataset,
            data_collator=data_collator,
            tokenizer=self.tokenizer,
        )
        
        # å¼å§è®­ç»?
        print(f"å¼å§LoRAå¾®è°...")
        trainer.train()
        
        # ä¿å­æ¨¡å
        self.lora_model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
        self.model = self.lora_model
        self.is_trained = True
        print(f"Qwen3-{self.model_size}-LoRA æ¨¡åè®­ç»å®æï¼?)
    
    def _extract_sentiment(self, generated_text: str, instruction: str) -> int:
        """ä»çæçææ¬ä¸­æåæææ ç­?""
        response = generated_text[len(instruction):].strip()
        
        if "æ­£é¢" in response:
            return 1
        elif "è´é¢" in response:
            return 0
        else:
            return 0
    
    def predict(self, texts: List[str]) -> List[int]:
        """é¢æµææ¬ææ"""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»")
        
        predictions = []
        
        self.lora_model.eval()
        with torch.no_grad():
            for text in tqdm(texts, desc=f"Qwen3-{self.model_size}é¢æµä¸?):
                pred, _ = self.predict_single(text)
                predictions.append(pred)
        
        return predictions
    
    def predict_single(self, text: str) -> Tuple[int, float]:
        """é¢æµåæ¡ææ¬çææ?""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»")
        
        # æå»ºæä»¤
        instruction = f"è¯·åæä»¥ä¸å¾®åææ¬çææå¾åï¼åç­?æ­£é¢'æ?è´é¢'n\nææ¬ï¼{text}\n\nææï¼?
        
        # åè¯
        inputs = self.tokenizer(instruction, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # çæåç­
        self.lora_model.eval()
        with torch.no_grad():
            outputs = self.lora_model.generate(
                **inputs,
                max_new_tokens=10,
                do_sample=True,
                temperature=0.1,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        
        # è§£ç çæçææ?
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # æåæææ ç­¾
        prediction = self._extract_sentiment(generated_text, instruction)
        confidence = 0.8  # çæå¼æ¨¡åçç½®ä¿¡åº¦è®¡ç®è¾å¤æï¼è¿éç»ä¸ªåºå®å?
        
        return prediction, confidence
    
    def save_model(self, model_path: str = None) -> None:
        """ä¿å­æ¨¡å"""
        if not self.is_trained:
            raise ValueError(f"æ¨¡å {self.model_name} å°æªè®­ç»")
        
        if model_path is None:
            model_path = MODEL_PATHS["lora"][self.model_size]
        
        os.makedirs(model_path, exist_ok=True)
        
        # ä¿å­LoRAæé
        self.lora_model.save_pretrained(model_path)
        self.tokenizer.save_pretrained(model_path)
        
        print(f"LoRAæ¨¡åå·²ä¿å­å°: {model_path}")
    
    def load_model(self, model_path: str) -> None:
        """å è½½æ¨¡å"""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"æ¨¡åæä»¶ä¸å­å? {model_path}")
        
        # å è½½åºç¡æ¨¡å
        self._load_base_model()
        
        # å è½½LoRAæé
        self.lora_model = PeftModel.from_pretrained(self.base_model, model_path)
        
        self.model = self.lora_model
        self.is_trained = True
        print(f"å·²å è½½Qwen3-{self.model_size}-LoRAæ¨¡å: {model_path}")


def main():
    """ä¸»å½æ?""
    parser = argparse.ArgumentParser(description='Qwen3-LoRAéç¨è®­ç»èæ¬')
    parser.add_argument('--model_size', type=str, choices=['0.6B', '4B', '8B'], 
                        help='æ¨¡åå¤§å°')
    parser.add_argument('--train_path', type=str, default='./dataset/train.txt',
                        help='è®­ç»æ°æ®è·¯å¾')
    parser.add_argument('--test_path', type=str, default='./dataset/test.txt',
                        help='æµè¯æ°æ®è·¯å¾')
    parser.add_argument('--model_path', type=str, help='æ¨¡åä¿å­è·¯å¾ï¼å¯éï¼')
    parser.add_argument('--epochs', type=int, default=3, help='è®­ç»è½®æ°')
    parser.add_argument('--batch_size', type=int, help='æ¹å¤§å°ï¼å¯éï¼ä½¿ç¨æ¨èå¼ï¼')
    parser.add_argument('--learning_rate', type=float, help='å­¦ä¹ çï¼å¯éï¼ä½¿ç¨æ¨èå¼ï¼')
    parser.add_argument('--lora_r', type=int, help='LoRAç§©ï¼å¯éï¼ä½¿ç¨æ¨èå¼ï¼')
    parser.add_argument('--max_samples', type=int, default=0, help='æå¤§è®­ç»æ ·æ¬æ°ï¼?è¡¨ç¤ºä½¿ç¨å¨é¨æ°æ®ï¼?)
    parser.add_argument('--eval_only', action='store_true', help='ä»è¯ä¼°æ¨¡å¼?)
    
    args = parser.parse_args()
    
    # å¦ææ²¡ææå®æ¨¡åå¤§å°ï¼åè¯¢é®ç¨æ·
    if not args.model_size:
        print("Qwen3-LoRAæ¨¡åè®­ç»")
        print("="*40)
        print("å¯ç¨æ¨¡åå¤§å°:")
        print("  1. 0.6B - è½»éçº§ï¼è®­ç»å¿«éï¼æ¾å­éæ±çº¦8GB")
        print("  2. 4B  - ä¸­ç­è§æ¨¡ï¼æ§è½åè¡¡ï¼æ¾å­éæ±çº¦32GB") 
        print("  3. 8B  - å¤§è§æ¨¡ï¼æ§è½æä½³ï¼æ¾å­éæ±çº¦64GB")
        print("\næ³¨æ: LoRAå¾®è°æ¯Embeddingæ¹æ³éè¦æ´å¤æ¾å­?)
        
        while True:
            choice = input("\nè¯·éæ©æ¨¡åå¤§å° (1/2/3): ").strip()
            if choice == '1':
                args.model_size = '0.6B'
                break
            elif choice == '2':
                args.model_size = '4B'
                break
            elif choice == '3':
                args.model_size = '8B'
                break
            else:
                print("æ æéæ©ï¼è¯·è¾å¥ 1 æ?3")
        
        print(f"å·²éæ©: Qwen3-{args.model_size} + LoRA")
        print()
    
    # ç¡®ä¿modelsç®å½å­å¨
    os.makedirs('./models', exist_ok=True)
    
    # åå»ºæ¨¡å
    model = Qwen3LoRAUniversal(args.model_size)
    
    # ç¡®å®æ¨¡åä¿å­è·¯å¾
    model_path = args.model_path or MODEL_PATHS["lora"][args.model_size]
    
    if args.eval_only:
        # ä»è¯ä¼°æ¨¡å¼?
        print(f"è¯ä¼°æ¨¡å¼ï¼å è½½Qwen3-{args.model_size}-LoRAæ¨¡å")
        model.load_model(model_path)
        
        _, test_data = BaseQwenModel.load_data(args.train_path, args.test_path)
        # LoRAè¯ä¼°ä½¿ç¨å°éæ°æ®
        test_subset = test_data[:50]
        model.evaluate(test_subset)
    else:
        # è®­ç»æ¨¡å¼
        train_data, test_data = BaseQwenModel.load_data(args.train_path, args.test_path)
        
        # è®­ç»æ°æ®å¤ç
        if args.max_samples > 0:
            train_subset = train_data[:args.max_samples]
            print(f"ä½¿ç¨ {len(train_subset)} æ¡æ°æ®è¿è¡LoRAè®­ç»")
        else:
            train_subset = train_data
            print(f"ä½¿ç¨å¨é¨ {len(train_subset)} æ¡æ°æ®è¿è¡LoRAè®­ç»")
        
        # åå¤è®­ç»åæ°
        train_kwargs = {'num_epochs': args.epochs}
        if args.batch_size:
            train_kwargs['batch_size'] = args.batch_size
        if args.learning_rate:
            train_kwargs['learning_rate'] = args.learning_rate
        if args.lora_r:
            train_kwargs['lora_r'] = args.lora_r
        
        # è®­ç»æ¨¡å
        model.train(train_subset, **train_kwargs)
        
        # è¯ä¼°æ¨¡åï¼ä½¿ç¨å°éæµè¯æ°æ®ï¼
        test_subset = test_data[:50]
        model.evaluate(test_subset)
        
        # ä¿å­æ¨¡å
        model.save_model(model_path)
        
        # ç¤ºä¾é¢æµ
        print(f"\nQwen3-{args.model_size}-LoRA ç¤ºä¾é¢æµ:")
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
