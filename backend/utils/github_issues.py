"""
GitHub Issues å·¥å·æ¨¡å

æä¾åå»º GitHub Issues URL åæ¾ç¤ºå¸¦é¾æ¥çéè¯¯ä¿¡æ¯çåè½
æ°æ®æ¨¡åå®ä¹ä½ç½®ï¼
- æ æ°æ®æ¨¡å
"""

from datetime import datetime
from urllib.parse import quote

# GitHub ä»åºä¿¡æ¯
GITHUB_REPO = "jacardl/BettaFish"
GITHUB_ISSUES_URL = f"https://github.com/{GITHUB_REPO}/issues/new"


def create_issue_url(title: str, body: str = "") -> str:
    """
    åå»º GitHub Issues URLï¼é¢å¡«åæ é¢ååå®¹
    
    Args:
        title: Issue æ é¢
        body: Issue åå®¹ï¼å¯éï¼
    
    Returns:
        å®æ´ç GitHub Issues URL
    """
    encoded_title = quote(title)
    encoded_body = quote(body) if body else ""
    
    if encoded_body:
        return f"{GITHUB_ISSUES_URL}?title={encoded_title}&body={encoded_body}"
    else:
        return f"{GITHUB_ISSUES_URL}?title={encoded_title}"


def error_with_issue_link(
    error_message: str,
    error_details: str = "",
    app_name: str = "Streamlit App"
) -> str:
    """
    çæå¸¦ GitHub Issues é¾æ¥çéè¯¯ä¿¡æ¯å­ç¬¦ä¸²
    
    ä»å¨éç¨å¼å¸¸å¤çä¸­ä½¿ç¨ï¼ä¸ç¨äºç¨æ·éç½®éè¯¯
    
    Args:
        error_message: éè¯¯æ¶æ¯
        error_details: éè¯¯è¯¦æï¼å¯éï¼ç¨äºå¡«åå° Issue bodyï¼
        app_name: åºç¨åç§°ï¼ç¨äºæ è¯éè¯¯æ¥æº
    
    Returns:
        åå«éè¯¯ä¿¡æ¯å GitHub Issues é¾æ¥ç Markdown æ ¼å¼å­ç¬¦ä¸²
    """
    issue_title = f"[{app_name}] {error_message[:50]}"
    issue_body = f"## éè¯¯ä¿¡æ¯\n\n{error_message}\n\n"
    
    if error_details:
        issue_body += f"## éè¯¯è¯¦æ\n\n```\n{error_details}\n```\n\n"
    
    issue_body += f"## ç¯å¢ä¿¡æ¯\n\n- åºç¨: {app_name}\n- æ¶é´: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    issue_url = create_issue_url(issue_title, issue_body)
    
    # ä½¿ç¨ markdown æ ¼å¼æ·»å è¶é¾æ¥
    error_display = f"{error_message}\n\n[ð æäº¤éè¯¯æ¥å]({issue_url})"
    
    if error_details:
        error_display = f"{error_message}\n\n```\n{error_details}\n```\n\n[ð æäº¤éè¯¯æ¥å]({issue_url})"
    
    return error_display


__all__ = [
    "create_issue_url",
    "error_with_issue_link",
    "GITHUB_REPO",
    "GITHUB_ISSUES_URL",
]

