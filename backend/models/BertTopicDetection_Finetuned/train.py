import os
import sys
import json
import re
import argparse
import math
import inspect
from typing import Dict, List, Optional, Tuple

# ========== åå¡éå®ï¼å¨å¯¼å¥ torch/transformers åæ§è¡ï¼ ==========
def _extract_gpu_arg(argv: List[str], default: str = "0") -> str:
    for i, arg in enumerate(argv):
        if arg.startswith("--gpu="):
            return arg.split("=", 1)[1]
        if arg == "--gpu" and i + 1 < len(argv):
            return argv[i + 1]
    return default

env_vis = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
try:
    gpu_to_use = _extract_gpu_arg(sys.argv, default="0")
except Exception:
    gpu_to_use = "0"
# è¥æªè®¾ç½®ææ´é²äºå¤å¡ï¼åå¼ºå¶åªæ´é²åå¡ï¼é»è®¤0ï¼ä»¥ç¡®ä¿ç´æ¥è¿è¡ç¨³å®
if (not env_vis) or ("," in env_vis):
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_to_use
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")

# æ¸çå¯è½ç±å¤é¨å¯å¨å¨æ³¨å¥çåå¸å¼ç¯å¢åéï¼é¿åè¯¯è§¦å¤å?åå¸å¼?
for _k in ["RANK", "LOCAL_RANK", "WORLD_SIZE"]:
    os.environ.pop(_k, None)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import torch
from torch.utils.data import Dataset
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
import pandas as pd

from transformers import (
    AutoTokenizer,
    AutoModel,
    AutoModelForSequenceClassification,
    AutoConfig,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
    set_seed,
)
try:
    from transformers import EarlyStoppingCallback  # type: ignore
except Exception:  # pragma: no cover
    EarlyStoppingCallback = None  # type: ignore

# é¢ç½®å¯éä¸­æåºåº§æ¨¡åï¼å¯æ©å±ï¼
BACKBONE_CANDIDATES: List[Tuple[str, str]] = [
    ("1) google-bert/bert-base-chinese", "google-bert/bert-base-chinese"),
    ("2) hfl/chinese-roberta-wwm-ext-large", "hfl/chinese-roberta-wwm-ext-large"),
    ("3) hfl/chinese-macbert-large", "hfl/chinese-macbert-large"),
    ("4) IDEA-CCNL/Erlangshen-DeBERTa-v2-710M-Chinese", "IDEA-CCNL/Erlangshen-DeBERTa-v2-710M-Chinese"),
    ("5) IDEA-CCNL/Erlangshen-DeBERTa-v3-Base-Chinese", "IDEA-CCNL/Erlangshen-DeBERTa-v3-Base-Chinese"),
    ("6) Langboat/mengzi-bert-base", "Langboat/mengzi-bert-base"),
    ("7) BAAI/bge-base-zh", "BAAI/bge-base-zh"),
    ("8) nghuyong/ernie-3.0-base-zh", "nghuyong/ernie-3.0-base-zh"),
]


def prompt_backbone_interactive(current_id: str) -> str:
    """äº¤äºå¼éæ©åºåº§æ¨¡å

    - å½å¤äºéäº¤äºç¯å¢ï¼stdin é?TTYï¼æè®¾ç½®äºç¯å¢åé?NON_INTERACTIVE=1 æ¶ï¼ç´æ¥è¿å current_id
    - ç¨æ·å¯è¾å¥åºå·éæ©é¢ç½®é¡¹ï¼æç´æ¥è¾å¥ä»»æ?Hugging Face æ¨¡å ID
    - ç©ºåè½¦ä½¿ç¨å½åé»è®¤
    """
    if os.environ.get("NON_INTERACTIVE", "0") == "1":
        return current_id
    try:
        if not sys.stdin.isatty():
            return current_id
    except Exception:
        return current_id

    print("\nå¯éä¸­æåºåº§æ¨¡åï¼ç´æ¥åè½¦ä½¿ç¨é»è®¤ï¼?")
    for label, hf_id in BACKBONE_CANDIDATES:
        print(f"  {label}")
    print(f"å½åé»è®¤: {current_id}")
    choice = input("è¯·è¾å¥åºå·æç´æ¥ç²è´´æ¨¡åIDï¼åè½¦æ²¿ç¨é»è®¤ï¼: ").strip()
    if not choice:
        return current_id
    # æ°å­éé¡¹
    if choice.isdigit():
        idx = int(choice)
        for label, hf_id in BACKBONE_CANDIDATES:
            if label.startswith(f"{idx})"):
                return hf_id
        print("æªæ¾å°è¯¥åºå·ï¼æ²¿ç¨é»è®¤)
        return current_id
    # èªå®ä¹?HF æ¨¡å ID
    return choice


def preprocess_text(text: str) -> str:
    if text is None:
        return ""
    cleaned = str(text)
    cleaned = cleaned.replace("\u200b", "").replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def ensure_base_model_local(model_name_or_path: str, local_model_root: str) -> Tuple[str, AutoTokenizer]:
    os.makedirs(local_model_root, exist_ok=True)
    base_dir = os.path.join(local_model_root, "bert-base-chinese")

    def is_ready(path: str) -> bool:
        return os.path.isdir(path) and os.path.isfile(os.path.join(path, "config.json"))

    # 1) æ¬å°ç°æ
    if is_ready(base_dir):
        tokenizer = AutoTokenizer.from_pretrained(base_dir)
        return base_dir, tokenizer

    # 2) æ¬æºç¼å­
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, local_files_only=True)
        base = AutoModel.from_pretrained(model_name_or_path, local_files_only=True)
        os.makedirs(base_dir, exist_ok=True)
        tokenizer.save_pretrained(base_dir)
        base.save_pretrained(base_dir)
        return base_dir, tokenizer
    except Exception:
        pass

    # 3) è¿ç¨ä¸è½½
    tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
    base = AutoModel.from_pretrained(model_name_or_path)
    os.makedirs(base_dir, exist_ok=True)
    tokenizer.save_pretrained(base_dir)
    base.save_pretrained(base_dir)
    return base_dir, tokenizer


class TextClassificationDataset(Dataset):
    def __init__(
        self,
        dataframe: pd.DataFrame,
        tokenizer: AutoTokenizer,
        text_column: str,
        label_column: str,
        label2id: Dict[str, int],
        max_length: int,
    ) -> None:
        self.dataframe = dataframe.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.text_column = text_column
        self.label_column = label_column
        self.label2id = label2id
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.dataframe)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        row = self.dataframe.iloc[idx]
        text = preprocess_text(row[self.text_column])
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            truncation=True,
            padding=False,
            return_tensors="pt",
        )
        item = {k: v.squeeze(0) for k, v in encoding.items()}
        if self.label_column in row and pd.notna(row[self.label_column]):
            label_str = str(row[self.label_column])
            item["labels"] = torch.tensor(self.label2id[label_str], dtype=torch.long)
        return item


def build_label_mappings(train_df: pd.DataFrame, label_column: str) -> Tuple[Dict[str, int], Dict[int, str]]:
    labels: List[str] = [str(x) for x in train_df[label_column].dropna().astype(str).tolist()]
    unique_sorted = sorted(set(labels))
    label2id = {label: i for i, label in enumerate(unique_sorted)}
    id2label = {i: label for label, i in label2id.items()}
    return label2id, id2label


def compute_metrics_fn(eval_pred) -> Dict[str, float]:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="weighted", zero_division=0)
    acc = accuracy_score(labels, preds)
    return {
        "accuracy": float(acc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def autodetect_columns(df: pd.DataFrame, text_col: str, label_col: str) -> Tuple[str, str]:
    if text_col != "auto" and label_col != "auto":
        return text_col, label_col
    candidates_text = ["text", "content", "sentence", "title", "desc", "question"]
    candidates_label = ["label", "labels", "category", "topic", "class"]
    t = text_col
    l = label_col
    if text_col == "auto":
        for name in candidates_text:
            if name in df.columns:
                t = name
                break
    if label_col == "auto":
        for name in candidates_label:
            if name in df.columns:
                l = name
                break
    if t == "auto" or l == "auto":
        raise ValueError(
            f"æ æ³èªå¨è¯å«ååï¼è¯·æ¾å¼ä¼ å¥ --text_col ä¸?--label_colãç°æå: {list(df.columns)}"
        )
    return t, l


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ä½¿ç¨ google-bert/bert-base-chinese å¨æ¬ç®å½æ°æ®éä¸è¿è¡ææ¬åç±»å¾®è°")
    parser.add_argument("--train_file", type=str, default="./dataset/web_text_zh_train.csv")
    parser.add_argument("--valid_file", type=str, default="./dataset/web_text_zh_valid.csv")
    parser.add_argument("--text_col", type=str, default="auto", help="ææ¬ååï¼é»è®¤èªå¨è¯å?)
    parser.add_argument("--label_col", type=str, default="auto", help="æ ç­¾ååï¼é»è®¤èªå¨è¯å?)
    parser.add_argument("--model_root", type=str, default="./model", help="æ¬å°æ¨¡åæ ¹ç®å½?)
    parser.add_argument("--pretrained_name", type=str, default="google-bert/bert-base-chinese", help="Hugging Face æ¨¡åIDï¼çç©ºåè¿å¥äº¤äºéæ©")
    parser.add_argument("--save_subdir", type=str, default="bert-chinese-classifier")
    parser.add_argument("--max_length", type=int, default=128)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--num_epochs", type=int, default=10)
    parser.add_argument("--learning_rate", type=float, default=2e-5)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--warmup_ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--gpu", type=str, default=os.environ.get("CUDA_VISIBLE_DEVICES", "0"), help="æå®åå¡ GPUï¼å¦ 0 æ?1")
    parser.add_argument("--eval_fraction", type=float, default=0.25, help="æ¯å¤å°ä¸ª epoch åä¸æ¬¡è¯ä¼°ä¸ä¿å­ï¼ä¾å¦?0.25 è¡¨ç¤ºæ¯ååä¹ä¸ä¸?epoch")
    parser.add_argument("--early_stop_patience", type=int, default=5, help="æ©åèå¿ï¼ä»¥è¯ä¼°è½®æ¬¡è®¡ï¼")
    parser.add_argument("--early_stop_threshold", type=float, default=0.0, help="æ©åæå°æ¹åéå¼ï¼ä¸?metric_for_best_model ååä½ï¼")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_root = args.model_root if os.path.isabs(args.model_root) else os.path.join(script_dir, args.model_root)
    os.makedirs(model_root, exist_ok=True)

    # äº¤äºå¼éæ©åºåº§æ¨¡åï¼è¥åè®¸äº¤äºä¸æªéè¿ç¯å¢ç¦ç¨ï¼?
    selected_model_id = prompt_backbone_interactive(args.pretrained_name)
    # ç¡®ä¿åºç¡æ¨¡åå°±ç»ª
    base_dir, tokenizer = ensure_base_model_local(selected_model_id, model_root)
    print(f"[Info] ä½¿ç¨åºç¡æ¨¡åç®å½: {base_dir}")

    # è¯»åæ°æ®
    train_path = args.train_file if os.path.isabs(args.train_file) else os.path.join(script_dir, args.train_file)
    valid_path = args.valid_file if os.path.isabs(args.valid_file) else os.path.join(script_dir, args.valid_file)
    if not os.path.isfile(train_path):
        raise FileNotFoundError(f"è®­ç»éä¸å­å¨: {train_path}")
    train_df = pd.read_csv(train_path)
    if not os.path.isfile(valid_path):
        # è¥æªæä¾æä¸å­å¨éªè¯éï¼èªå¨åå
        shuffled = train_df.sample(frac=1.0, random_state=args.seed).reset_index(drop=True)
        split_idx = int(len(shuffled) * 0.9)
        valid_df = shuffled.iloc[split_idx:].reset_index(drop=True)
        train_df = shuffled.iloc[:split_idx].reset_index(drop=True)
    else:
        valid_df = pd.read_csv(valid_path)
    print(f"[Info] è®­ç»é? {train_path} | æ ·æ¬æ? {len(train_df)}")
    print(f"[Info] éªè¯é? {valid_path if os.path.isfile(valid_path) else '(ä»è®­ç»éåå)'} | æ ·æ¬æ? {len(valid_df)}")

    # èªå¨è¯å«åå
    text_col, label_col = autodetect_columns(train_df, args.text_col, args.label_col)
    print(f"[Info] ææ¬å? {text_col} | æ ç­¾å? {label_col}")

    # æ ç­¾æ å°ï¼ä½¿ç?è®­ç»éâªéªè¯é?çå¹¶éï¼é¿åéªè¯éä¸­åºç°æ°æ ç­¾å¯¼è´æ¥éï¼
    combined_labels_df = pd.concat([train_df[[label_col]], valid_df[[label_col]]], ignore_index=True)
    label2id, id2label = build_label_mappings(combined_labels_df, label_col)
    if len(label2id) < 2:
        raise ValueError("æ ç­¾ç±»å«æ°å°äº?2ï¼æ æ³è®­ç»åç±»æ¨¡å)
    print(f"[Info] æ ç­¾ç±»å«æ? {len(label2id)}")
    # æç¤ºéªè¯éä¸­æªåºç°å¨è®­ç»éçæ ç­¾æ°é
    try:
        train_label_set = set(str(x) for x in train_df[label_col].dropna().astype(str).tolist())
        valid_label_set = set(str(x) for x in valid_df[label_col].dropna().astype(str).tolist())
        unseen_in_train = sorted(valid_label_set - train_label_set)
        if unseen_in_train:
            preview = ", ".join(unseen_in_train[:10])
            print(f"[Warn] éªè¯éä¸­å­å¨ {len(unseen_in_train)} ä¸ªè®­ç»æªåºç°çæ ç­¾ï¼å·²çº³å¥æ å°ä»¥é¿åæ¥éï¼ãç¤ºä¾? {preview} ...")
    except Exception:
        pass

    # æ°æ®é?
    train_dataset = TextClassificationDataset(train_df, tokenizer, text_col, label_col, label2id, args.max_length)
    eval_dataset = TextClassificationDataset(valid_df, tokenizer, text_col, label_col, label2id, args.max_length)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)

    # æ¨¡å
    config = AutoConfig.from_pretrained(
        base_dir,
        num_labels=len(label2id),
        id2label={int(i): str(l) for i, l in id2label.items()},
        label2id={str(l): int(i) for l, i in label2id.items()},
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        base_dir,
        config=config,
        ignore_mismatched_sizes=True,
    )

    # è®­ç»åæ°
    output_dir = os.path.join(model_root, args.save_subdir)
    os.makedirs(output_dir, exist_ok=True)
    # è®­ç»åæ°ï¼å¼å®¹ä¸å?transformers çæ¬ï¼?
    args_dict = {
        "output_dir": output_dir,
        "per_device_train_batch_size": args.batch_size,
        "per_device_eval_batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "num_train_epochs": args.num_epochs,
        "logging_steps": 100,
        "fp16": args.fp16,
        "seed": args.seed,
    }

    sig = inspect.signature(TrainingArguments.__init__)
    allowed = set(sig.parameters.keys())

    # å¯éåæ°ï¼ä»å¨æ¯ææ¶æ·»å ï¼å°½éç®åä¸åèå®ç°ä¸è´ä»¥æåå¼å®¹æ§ï¼
    if "warmup_ratio" in allowed:
        args_dict["warmup_ratio"] = args.warmup_ratio
    if "report_to" in allowed:
        args_dict["report_to"] = []
    # è¯ä¼°/ä¿å­æ­¥è¿ï¼æ eval_fraction æç®æ¯ä¸ª epoch çæ­¥æ?
    steps_per_epoch = max(1, math.ceil(len(train_dataset) / max(1, args.batch_size)))
    eval_every_steps = max(1, math.ceil(steps_per_epoch * max(0.01, min(1.0, args.eval_fraction))))
    # ç­ç¥å¼ï¼æ?æ§çæ¬å­æ®µåå¼å®¹ï¼?
    key_eval = "evaluation_strategy" if "evaluation_strategy" in allowed else ("eval_strategy" if "eval_strategy" in allowed else None)
    if key_eval:
        args_dict[key_eval] = "steps"
    if "save_strategy" in allowed:
        args_dict["save_strategy"] = "steps"
    if "eval_steps" in allowed:
        args_dict["eval_steps"] = eval_every_steps
    if "save_steps" in allowed:
        args_dict["save_steps"] = eval_every_steps
    if "save_total_limit" in allowed:
        args_dict["save_total_limit"] = 5
    # å°æ¥å¿æ­¥é¿ä¸è¯ä¼°/ä¿å­æ­¥é¿å¯¹é½ï¼åå°å·å±?
    if "logging_steps" in allowed:
        args_dict["logging_steps"] = eval_every_steps
    # æä¼æ¨¡ååæ»ï¼ä»å½è¯ä¼°ä¸ä¿å­ç­ç¥ä¸è´æ¶å¼å¯ï¼
    if "metric_for_best_model" in allowed:
        args_dict["metric_for_best_model"] = "f1"
    if "greater_is_better" in allowed:
        args_dict["greater_is_better"] = True
    if "load_best_model_at_end" in allowed:
        eval_strat = args_dict.get("evaluation_strategy", args_dict.get("eval_strategy"))
        save_strat = args_dict.get("save_strategy")
        if eval_strat == save_strat and eval_strat in ("steps", "epoch"):
            args_dict["load_best_model_at_end"] = True

    # å¼å®¹æ?warmup_ratio ççæ¬ï¼è¥æ¯æ?warmup_steps åå¿½ç¥æ¯ä¾?
    if "warmup_ratio" not in allowed and "warmup_steps" in allowed:
        # ä¸è®¡ç®æ»æ­¥æ°ï¼é»è®¤ 0
        args_dict["warmup_steps"] = 0

    # è¥ä¸æ¯æç­ç¥å¼åæ°ï¼éåä¸ºæ¯?eval_every_steps æ­¥ä¿å­?è¯ä¼°
    if "save_strategy" not in allowed and "save_steps" in allowed:
        args_dict["save_steps"] = eval_every_steps
    if ("evaluation_strategy" not in allowed and "eval_strategy" not in allowed) and "eval_steps" in allowed:
        args_dict["eval_steps"] = eval_every_steps

    # å¦ææ¯æ load_best_model_at_endï¼ä½æ æ³åæ¶è®¾ç½®è¯ä¼°/ä¿å­ç­ç¥ï¼åå³é­å®ä»¥é¿åæ¥é
    if "load_best_model_at_end" in allowed:
        want_load_best = args_dict.get("load_best_model_at_end", False)
        eval_set = args_dict.get("evaluation_strategy", None)
        save_set = args_dict.get("save_strategy", None)
        if want_load_best and (eval_set is None or save_set is None or eval_set != save_set):
            args_dict["load_best_model_at_end"] = False

    training_args = TrainingArguments(**args_dict)
    print("[Info] è®­ç»åæ°è¦ç¹:")
    print(f"       epochs={args.num_epochs}, batch_size={args.batch_size}, lr={args.learning_rate}, weight_decay={args.weight_decay}")
    print(f"       max_length={args.max_length}, seed={args.seed}, fp16={args.fp16}")
    if "warmup_ratio" in allowed and "warmup_ratio" in args_dict:
        print(f"       warmup_ratio={args_dict['warmup_ratio']}")
    elif "warmup_steps" in allowed and "warmup_steps" in args_dict:
        print(f"       warmup_steps={args_dict['warmup_steps']}")
    print(f"       steps_per_epoch={steps_per_epoch}, eval_every_steps={eval_every_steps}")
    print(f"       eval_strategy={args_dict.get('evaluation_strategy', args_dict.get('eval_strategy'))}, save_strategy={args_dict.get('save_strategy')}, logging_steps={args_dict.get('logging_steps')}")
    print(f"       save_total_limit={args_dict.get('save_total_limit', 'n/a')}, load_best_model_at_end={args_dict.get('load_best_model_at_end', False)}")

    callbacks = []
    if EarlyStoppingCallback is not None and (args_dict.get("evaluation_strategy") in ("steps", "epoch") or "eval_steps" in allowed):
        try:
            callbacks.append(
                EarlyStoppingCallback(
                    early_stopping_patience=args.early_stop_patience,
                    early_stopping_threshold=args.early_stop_threshold,
                )
            )
        except Exception:
            pass

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=collator,
        compute_metrics=compute_metrics_fn,
        callbacks=callbacks,
    )
    # è®¾å¤ä¸?GPU ä¿¡æ¯
    try:
        device_cnt = torch.cuda.device_count()
        dev_name = torch.cuda.get_device_name(0) if device_cnt > 0 else "cpu"
        print(f"[Info] CUDA å¯è§è®¾å¤æ? {device_cnt}, å½åè®¾å¤: {dev_name}, CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}")
    except Exception:
        pass

    print("[Info] å¼å§è®­ç»?...")

    trainer.train()

    # ä¿å­
    tokenizer.save_pretrained(output_dir)
    trainer.model.config.id2label = {int(i): str(l) for i, l in id2label.items()}
    trainer.model.config.label2id = {str(l): int(i) for l, i in label2id.items()}
    trainer.save_model(output_dir)
    try:
        best_metric = getattr(trainer.state, "best_metric", None)
        best_ckpt = getattr(trainer.state, "best_model_checkpoint", None)
        if best_metric is not None and best_ckpt is not None:
            print(f"[Info] æä¼æ¨¡å? metric={best_metric:.6f} | checkpoint={best_ckpt}")
    except Exception:
        pass

    with open(os.path.join(output_dir, "label_map.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"label2id": trainer.model.config.label2id, "id2label": trainer.model.config.id2label},
            f,
            ensure_ascii=False,
            indent=2,
        )

    # è®­ç»æ²çº¿ï¼å¯éä¿å­è®­ç»ä¸è¯ä¼° loss
    try:
        import matplotlib.pyplot as plt  # type: ignore
        logs = trainer.state.log_history
        t_steps, t_losses, e_steps, e_losses = [], [], [], []
        step_counter = 0
        for rec in logs:
            if "loss" in rec and "epoch" in rec:
                step_counter += 1
                t_steps.append(step_counter)
                t_losses.append(rec["loss"])
            if "eval_loss" in rec:
                e_steps.append(step_counter)
                e_losses.append(rec["eval_loss"])
        if t_losses or e_losses:
            plt.figure(figsize=(8,4))
            if t_losses:
                plt.plot(t_steps, t_losses, label="train_loss")
            if e_losses:
                plt.plot(e_steps, e_losses, label="eval_loss")
            plt.xlabel("training step (logged)")
            plt.ylabel("loss")
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, "training_curve.png"))
    except Exception:
        pass

    print(f"å¾®è°å®æï¼æ¨¡åå·²ä¿å­å? {output_dir}")


if __name__ == "__main__":
    main()


