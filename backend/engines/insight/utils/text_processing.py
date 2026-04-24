"""
ææ¬å¤çå·¥å·å½æ°
ç¨äºæ¸çLLMè¾åºãè§£æJSONç­?
"""

import re
import json
from typing import Dict, Any, List
from json.decoder import JSONDecodeError


def clean_json_tags(text: str) -> str:
    """
    æ¸çææ¬ä¸­çJSONæ ç­¾
    
    Args:
        text: åå§ææ¬
        
    Returns:
        æ¸çåçææ¬
    """
    # ç§»é¤```json å?```æ ç­¾
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = re.sub(r'```', '', text)
    
    return text.strip()


def clean_markdown_tags(text: str) -> str:
    """
    æ¸çææ¬ä¸­çMarkdownæ ç­¾
    
    Args:
        text: åå§ææ¬
        
    Returns:
        æ¸çåçææ¬
    """
    # ç§»é¤```markdown å?```æ ç­¾
    text = re.sub(r'```markdown\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = re.sub(r'```', '', text)
    
    return text.strip()


def remove_reasoning_from_output(text: str) -> str:
    """
    ç§»é¤è¾åºä¸­çæ¨çè¿ç¨ææ¬
    
    Args:
        text: åå§ææ¬
        
    Returns:
        æ¸çåçææ¬
    """
    # æ¥æ¾JSONå¼å§ä½ç½?
    json_start = -1
    
    # å°è¯æ¾å°ç¬¬ä¸ä¸?{ æ?[
    for i, char in enumerate(text):
        if char in '{[':
            json_start = i
            break
    
    if json_start != -1:
        # ä»JSONå¼å§ä½ç½®æªå?
        return text[json_start:].strip()
    
    # å¦ææ²¡ææ¾å°JSONæ è®°ï¼å°è¯å¶ä»æ¹æ³?
    # ç§»é¤å¸¸è§çæ¨çæ è¯?
    patterns = [
        r'(?:reasoning|æ¨ç|æè|åæ)[:ï¼]\s*.*?(?=\{|\[)',  # ç§»é¤æ¨çé¨å
        r'(?:explanation|è§£é|è¯´æ)[:ï¼]\s*.*?(?=\{|\[)',   # ç§»é¤è§£éé¨å
        r'^.*?(?=\{|\[)',  # ç§»é¤JSONåçææææ?
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    return text.strip()


def extract_clean_response(text: str) -> Dict[str, Any]:
    """
    æåå¹¶æ¸çååºä¸­çJSONåå®¹
    
    Args:
        text: åå§ååºææ¬
        
    Returns:
        è§£æåçJSONå­å¸
    """
    # æ¸çææ¬
    cleaned_text = clean_json_tags(text)
    cleaned_text = remove_reasoning_from_output(cleaned_text)
    
    # å°è¯ç´æ¥è§£æ
    try:
        return json.loads(cleaned_text)
    except JSONDecodeError:
        pass
    
    # å°è¯ä¿®å¤ä¸å®æ´çJSON
    fixed_text = fix_incomplete_json(cleaned_text)
    if fixed_text:
        try:
            return json.loads(fixed_text)
        except JSONDecodeError:
            pass
    
    # å°è¯æ¥æ¾JSONå¯¹è±¡
    json_pattern = r'\{.*\}'
    match = re.search(json_pattern, cleaned_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except JSONDecodeError:
            pass
    
    # å°è¯æ¥æ¾JSONæ°ç»
    array_pattern = r'\[.*\]'
    match = re.search(array_pattern, cleaned_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except JSONDecodeError:
            pass
    
    # å¦ææææ¹æ³é½å¤±è´¥ï¼è¿åéè¯¯ä¿¡æ?
    print(f"æ æ³è§£æJSONååº: {cleaned_text[:200]}...")
    return {"error": "JSONè§£æå¤±è´¥", "raw_text": cleaned_text}


def fix_incomplete_json(text: str) -> str:
    """
    ä¿®å¤ä¸å®æ´çJSONååº
    
    Args:
        text: åå§ææ¬
        
    Returns:
        ä¿®å¤åçJSONææ¬ï¼å¦ææ æ³ä¿®å¤åè¿åç©ºå­ç¬¦ä¸²
    """
    import json_repair
    try:
        # json_repair.repair_json ä¼èªå¨è¡¥å¨ç¼ºå¤±çå¼å·ãæ¬å·ç­
        repaired = json_repair.repair_json(text, return_objects=False)
        if repaired:
            return repaired
    except Exception as e:
        print(f"json_repair ä¿®å¤å¤±è´¥: {e}")
    
    return ""


def fix_aggressive_json(text: str) -> str:
    """
    æ´æ¿è¿çJSONä¿®å¤æ¹æ³
    
    Args:
        text: åå§ææ¬
        
    Returns:
        ä¿®å¤åçJSONææ¬
    """
    # æ¥æ¾ææå¯è½çJSONå¯¹è±¡
    objects = re.findall(r'\{[^{}]*\}', text)
    
    if len(objects) >= 2:
        # å¦ææå¤ä¸ªå¯¹è±¡ï¼åè£ææ°ç»?
        return '[' + ','.join(objects) + ']'
    elif len(objects) == 1:
        # å¦æåªæä¸ä¸ªå¯¹è±¡ï¼åè£ææ°ç»?
        return '[' + objects[0] + ']'
    else:
        # å¦ææ²¡ææ¾å°å¯¹è±¡ï¼è¿åç©ºæ°ç»
        return '[]'


def update_state_with_search_results(search_results: List[Dict[str, Any]], 
                                   paragraph_index: int, state: Any) -> Any:
    """
    å°æç´¢ç»ææ´æ°å°ç¶æä¸­
    
    Args:
        search_results: æç´¢ç»æåè¡¨
        paragraph_index: æ®µè½ç´¢å¼
        state: ç¶æå¯¹è±?
        
    Returns:
        æ´æ°åçç¶æå¯¹è±?
    """
    if 0 <= paragraph_index < len(state.paragraphs):
        # è·åæåä¸æ¬¡æç´¢çæ¥è¯¢ï¼åè®¾æ¯å½åæ¥è¯¢ï¼?
        current_query = ""
        if search_results:
            # ä»æç´¢ç»ææ¨æ­æ¥è¯¢ï¼è¿ééè¦æ¹è¿ä»¥è·åå®éæ¥è¯¢ï¼?
            current_query = "æç´¢æ¥è¯¢"
        
        # æ·»å æç´¢ç»æå°ç¶æ?
        state.paragraphs[paragraph_index].research.add_search_results(
            current_query, search_results
        )
    
    return state


def validate_json_schema(data: Dict[str, Any], required_fields: List[str]) -> bool:
    """
    éªè¯JSONæ°æ®æ¯å¦åå«å¿éå­æ®µ
    
    Args:
        data: è¦éªè¯çæ°æ®
        required_fields: å¿éå­æ®µåè¡¨
        
    Returns:
        éªè¯æ¯å¦éè¿
    """
    return all(field in data for field in required_fields)


def truncate_content(content: str, max_length: int = 20000) -> str:
    """
    æªæ­åå®¹å°æå®é¿åº?
    
    Args:
        content: åå§åå®¹
        max_length: æå¤§é¿åº?
        
    Returns:
        æªæ­åçåå®¹
    """
    if len(content) <= max_length:
        return content
    
    # å°è¯å¨åè¯è¾¹çæªæ?
    truncated = content[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # å¦ææåä¸ä¸ªç©ºæ ¼ä½ç½®åç?
        return truncated[:last_space] + "..."
    else:
        return truncated + "..."


def format_search_results_for_prompt(search_results: List[Dict[str, Any]], 
                                   max_length: int = 20000) -> List[str]:
    """
    æ ¼å¼åæç´¢ç»æç¨äºæç¤ºè¯
    
    Args:
        search_results: æç´¢ç»æåè¡¨
        max_length: æ¯ä¸ªç»æçæå¤§é¿åº?
        
    Returns:
        æ ¼å¼ååçåå®¹åè¡?
    """
    formatted_results = []
    
    for result in search_results:
        content = result.get('content', '')
        if content:
            truncated_content = truncate_content(content, max_length)
            formatted_results.append(truncated_content)
    
    return formatted_results
