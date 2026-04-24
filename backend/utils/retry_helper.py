"""
éè¯æºå¶å·¥å·æ¨¡å
æä¾éç¨çç½ç»è¯·æ±éè¯åè½ï¼å¢å¼ºç³»ç»å¥å£®æ§
"""

import time
from functools import wraps
from typing import Callable, Any
import requests
from loguru import logger

# éç½®æ¥å¿
class RetryConfig:
    """éè¯éç½®ç±»"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        retry_on_exceptions: tuple = None
    ):
        """
        åå§åéè¯éç½®
        
        Args:
            max_retries: æå¤§éè¯æ¬¡æ°
            initial_delay: åå§å»¶è¿ç§æ°
            backoff_factor: éé¿å å­ï¼æ¯æ¬¡éè¯å»¶è¿ç¿»åï¼
            max_delay: æå¤§å»¶è¿ç§æ°
            retry_on_exceptions: éè¦éè¯çå¼å¸¸ç±»ååç»
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        
        # é»è®¤éè¦éè¯çå¼å¸¸ç±»å
        if retry_on_exceptions is None:
            self.retry_on_exceptions = (
                requests.exceptions.RequestException,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
                requests.exceptions.Timeout,
                requests.exceptions.TooManyRedirects,
                ConnectionError,
                TimeoutError,
                Exception  # OpenAIåå¶ä»APIå¯è½æåºçä¸è¬å¼å¸¸
            )
        else:
            self.retry_on_exceptions = retry_on_exceptions

# é»è®¤éç½®
DEFAULT_RETRY_CONFIG = RetryConfig()

def with_retry(config: RetryConfig = None):
    """
    éè¯è£é¥°å¨
    
    Args:
        config: éè¯éç½®ï¼å¦æä¸æä¾åä½¿ç¨é»è®¤éç½®
    
    Returns:
        è£é¥°å¨å½æ°
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):  # +1 å ä¸ºç¬¬ä¸æ¬¡ä¸ç®éè¯
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"å½æ° {func.__name__} å¨ç¬¬ {attempt + 1} æ¬¡å°è¯åæå")
                    return result
                    
                except config.retry_on_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        # æåä¸æ¬¡å°è¯ä¹å¤±è´¥äº
                        logger.error(f"å½æ° {func.__name__} å¨ {config.max_retries + 1} æ¬¡å°è¯åä»ç¶å¤±è´¥")
                        logger.error(f"æç»éè¯¯: {str(e)}")
                        raise e
                    
                    # è®¡ç®å»¶è¿æ¶é´
                    delay = min(
                        config.initial_delay * (config.backoff_factor ** attempt),
                        config.max_delay
                    )
                    
                    logger.warning(f"å½æ° {func.__name__} ç¬¬ {attempt + 1} æ¬¡å°è¯å¤±è´¥: {str(e)}")
                    logger.info(f"å°å¨ {delay:.1f} ç§åè¿è¡ç¬¬ {attempt + 2} æ¬¡å°è¯...")
                    
                    time.sleep(delay)
                
                except Exception as e:
                    # ä¸å¨éè¯åè¡¨ä¸­çå¼å¸¸ï¼ç´æ¥æåº
                    logger.error(f"å½æ° {func.__name__} éå°ä¸å¯éè¯çå¼å¸¸: {str(e)}")
                    raise e
            
            # è¿éä¸åºè¯¥å°è¾¾ï¼ä½ä½ä¸ºå®å¨ç½
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator

def retry_on_network_error(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0
):
    """
    ä¸é¨ç¨äºç½ç»éè¯¯çéè¯è£é¥°å¨ï¼ç®åçï¼
    
    Args:
        max_retries: æå¤§éè¯æ¬¡æ°
        initial_delay: åå§å»¶è¿ç§æ°
        backoff_factor: éé¿å å­
    
    Returns:
        è£é¥°å¨å½æ°
    """
    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor
    )
    return with_retry(config)

class RetryableError(Exception):
    """èªå®ä¹çå¯éè¯å¼å¸¸"""
    pass

def with_graceful_retry(config: RetryConfig = None, default_return=None):
    """
    ä¼ééè¯è£é¥°å¨ - ç¨äºéå³é®APIè°ç¨
    å¤±è´¥åä¸ä¼æåºå¼å¸¸ï¼èæ¯è¿åé»è®¤å¼ï¼ä¿è¯ç³»ç»ç»§ç»­è¿è¡
    
    Args:
        config: éè¯éç½®ï¼å¦æä¸æä¾åä½¿ç¨é»è®¤éç½®
        default_return: ææéè¯å¤±è´¥åè¿åçé»è®¤å¼
    
    Returns:
        è£é¥°å¨å½æ°
    """
    if config is None:
        config = SEARCH_API_RETRY_CONFIG
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):  # +1 å ä¸ºç¬¬ä¸æ¬¡ä¸ç®éè¯
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"éå³é®API {func.__name__} å¨ç¬¬ {attempt + 1} æ¬¡å°è¯åæå")
                    return result
                    
                except config.retry_on_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        # æåä¸æ¬¡å°è¯ä¹å¤±è´¥äºï¼è¿åé»è®¤å¼èä¸æåºå¼å¸¸
                        logger.warning(f"éå³é®API {func.__name__} å¨ {config.max_retries + 1} æ¬¡å°è¯åä»ç¶å¤±è´¥")
                        logger.warning(f"æç»éè¯¯: {str(e)}")
                        logger.info(f"è¿åé»è®¤å¼ä»¥ä¿è¯ç³»ç»ç»§ç»­è¿è¡: {default_return}")
                        return default_return
                    
                    # è®¡ç®å»¶è¿æ¶é´
                    delay = min(
                        config.initial_delay * (config.backoff_factor ** attempt),
                        config.max_delay
                    )
                    
                    logger.warning(f"éå³é®API {func.__name__} ç¬¬ {attempt + 1} æ¬¡å°è¯å¤±è´¥: {str(e)}")
                    logger.info(f"å°å¨ {delay:.1f} ç§åè¿è¡ç¬¬ {attempt + 2} æ¬¡å°è¯...")
                    
                    time.sleep(delay)
                
                except Exception as e:
                    # ä¸å¨éè¯åè¡¨ä¸­çå¼å¸¸ï¼è¿åé»è®¤å¼
                    logger.warning(f"éå³é®API {func.__name__} éå°ä¸å¯éè¯çå¼å¸¸: {str(e)}")
                    logger.info(f"è¿åé»è®¤å¼ä»¥ä¿è¯ç³»ç»ç»§ç»­è¿è¡: {default_return}")
                    return default_return
            
            # è¿éä¸åºè¯¥å°è¾¾ï¼ä½ä½ä¸ºå®å¨ç½
            return default_return
            
        return wrapper
    return decorator

def make_retryable_request(
    request_func: Callable,
    *args,
    max_retries: int = 5,
    **kwargs
) -> Any:
    """
    ç´æ¥æ§è¡å¯éè¯çè¯·æ±ï¼ä¸ä½¿ç¨è£é¥°å¨ï¼
    
    Args:
        request_func: è¦æ§è¡çè¯·æ±å½æ°
        *args: ä¼ éç»è¯·æ±å½æ°çä½ç½®åæ°
        max_retries: æå¤§éè¯æ¬¡æ°
        **kwargs: ä¼ éç»è¯·æ±å½æ°çå³é®å­åæ°
    
    Returns:
        è¯·æ±å½æ°çè¿åå¼
    """
    config = RetryConfig(max_retries=max_retries)
    
    @with_retry(config)
    def _execute():
        return request_func(*args, **kwargs)
    
    return _execute()

# é¢å®ä¹ä¸äºå¸¸ç¨çéè¯éç½®
LLM_RETRY_CONFIG = RetryConfig(
    max_retries=6,        # ä¿æé¢å¤éè¯æ¬¡æ°
    initial_delay=60.0,   # é¦æ¬¡ç­å¾è³å° 1 åé
    backoff_factor=2.0,   # ç»§ç»­ä½¿ç¨ææ°éé¿
    max_delay=600.0       # åæ¬¡ç­å¾æé¿ 10 åé
)

SEARCH_API_RETRY_CONFIG = RetryConfig(
    max_retries=5,        # å¢å å°5æ¬¡éè¯
    initial_delay=2.0,    # å¢å åå§å»¶è¿
    backoff_factor=1.6,   # è°æ´éé¿å å­
    max_delay=25.0        # å¢å æå¤§å»¶è¿
)

DB_RETRY_CONFIG = RetryConfig(
    max_retries=5,        # å¢å å°5æ¬¡éè¯
    initial_delay=1.0,    # ä¿æè¾ç­çæ°æ®åºéè¯å»¶è¿
    backoff_factor=1.5,
    max_delay=10.0
)
