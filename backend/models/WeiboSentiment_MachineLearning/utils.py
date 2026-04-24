# -*- coding: utf-8 -*-
import jieba
import re
import os
import pickle
from typing import List, Tuple, Any


# å è½½åç¨è¯?
stopwords = []
stopwords_path = "data/stopwords.txt"
if os.path.exists(stopwords_path):
    with open(stopwords_path, "r", encoding="utf8") as f:
        for w in f:
            stopwords.append(w.strip())
else:
    print(f"è­¦å: åç¨è¯æä»?{stopwords_path} ä¸å­å¨ï¼å°ä½¿ç¨ç©ºåç¨è¯åè¡?)


def load_corpus(path):
    """
    å è½½è¯­æåº?
    """
    data = []
    with open(path, "r", encoding="utf8") as f:
        for line in f:
            [_, seniment, content] = line.split(",", 2)
            content = processing(content)
            data.append((content, int(seniment)))
    return data


def load_corpus_bert(path):
    """
    å è½½è¯­æåº?
    """
    data = []
    with open(path, "r", encoding="utf8") as f:
        for line in f:
            [_, seniment, content] = line.split(",", 2)
            content = processing_bert(content)
            data.append((content, int(seniment)))
    return data


def processing(text):
    """
    æ°æ®é¢å¤ç? å¯ä»¥æ ¹æ®èªå·±çéæ±è¿è¡éè½?
    """
    # æ°æ®æ¸æ´é¨å
    text = re.sub("\{%.+?%\}", " ", text)           # å»é¤ {%xxx%} (å°çå®ä½, å¾®åè¯é¢ç­?
    text = re.sub("@.+?( |$)", " ", text)           # å»é¤ @xxx (ç¨æ·å?
    text = re.sub("+?, " ", text)              # å»é¤ x(éé¢çåå®¹éå¸¸é½ä¸æ¯ç¨æ·èªå·±åç?
    text = re.sub("\u200b", " ", text)              # '\u200b'æ¯è¿ä¸ªæ°æ®éä¸­çä¸ä¸ªbad case, ä¸ç¨ç¹å«å¨æ
    # åè¯
    words = [w for w in jieba.lcut(text) if w.isalpha()]
    # å¯¹å¦å®è¯`ä¸`åç¹æ®å¤ç? ä¸å¶åé¢çè¯è¿è¡æ¼æ¥
    while "ä¸? in words:
        index = words.index("ä¸?)
        if index == len(words) - 1:
            break
        words[index: index+2] = ["".join(words[index: index+2])]  # åè¡¨åçèµå¼çé·ç«åæ³
    # ç¨ç©ºæ ¼æ¼æ¥æå­ç¬¦ä¸?
    result = " ".join(words)
    return result


def processing_bert(text):
    """
    æ°æ®é¢å¤ç? å¯ä»¥æ ¹æ®èªå·±çéæ±è¿è¡éè½?
    """
    # æ°æ®æ¸æ´é¨å
    text = re.sub("\{%.+?%\}", " ", text)           # å»é¤ {%xxx%} (å°çå®ä½, å¾®åè¯é¢ç­?
    text = re.sub("@.+?( |$)", " ", text)           # å»é¤ @xxx (ç¨æ·å?
    text = re.sub("+?, " ", text)              # å»é¤ x(éé¢çåå®¹éå¸¸é½ä¸æ¯ç¨æ·èªå·±åç?
    text = re.sub("\u200b", " ", text)              # '\u200b'æ¯è¿ä¸ªæ°æ®éä¸­çä¸ä¸ªbad case, ä¸ç¨ç¹å«å¨æ
    return text


def save_model(model: Any, model_path: str) -> None:
    """
    ä¿å­æ¨¡åå°æä»?
    
    Args:
        model: è¦ä¿å­çæ¨¡åå¯¹è±¡
        model_path: ä¿å­è·¯å¾
    """
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"æ¨¡åå·²ä¿å­å°: {model_path}")


def load_model(model_path: str) -> Any:
    """
    ä»æä»¶å è½½æ¨¡å?
    
    Args:
        model_path: æ¨¡åæä»¶è·¯å¾
        
    Returns:
        å è½½çæ¨¡åå¯¹è±?
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"æ¨¡åæä»¶ä¸å­å? {model_path}")
    
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    
    print(f"å·²å è½½æ¨¡å? {model_path}")
    return model


def preprocess_text_simple(text: str) -> str:
    """
    ç®åçææ¬é¢å¤çå½æ°ï¼ç¨äºé¢æµæ¶çææ¬æ¸æ´
    
    Args:
        text: åå§ææ¬
        
    Returns:
        æ¸æ´åçææ¬
    """
    # æ°æ®æ¸æ´
    text = re.sub("\{%.+?%\}", " ", text)           # å»é¤ {%xxx%}
    text = re.sub("@.+?( |$)", " ", text)           # å»é¤ @xxx
    text = re.sub("+?, " ", text)              # å»é¤ x
    text = re.sub("\u200b", " ", text)              # å»é¤ç¹æ®å­ç¬¦
    
    # å é¤è¡¨æç¬¦å·
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001f900-\U0001f9ff\U0001f018-\U0001f270\U0000231a-\U0000231b\U0000238d-\U0000238d\U000024c2-\U0001f251]+', '', text)
    
    # å¤ä¸ªç©ºæ ¼åå¹¶ä¸ºä¸ä¸?
    text = re.sub(r"\s+", " ", text)
    
    return text.strip()
