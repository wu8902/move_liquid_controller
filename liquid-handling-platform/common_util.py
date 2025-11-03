import json
import os
from logger_handler import create_logger

log = create_logger("INFO", "CommonUtil")
TOKEN_CACHE = "./.token_cache"

def save_cache(token: str, cache_type = TOKEN_CACHE) -> None:
    """
    将 token 保存到文件
    """
    try:
        with open(cache_type, 'w') as f:
            f.write(token)
        log.info(f"Token 已保存至: {os.path.abspath(cache_type)}")
    except IOError as e:
        log.info(f"Token 保存失败: {str(e)}")

def load_cache(cache_type = TOKEN_CACHE) -> str:
    """
    从文件加载 token
    """
    try:
        if not os.path.exists(cache_type):
            return ""
        with open(cache_type, 'r') as f:
            return f.read().strip()
    except IOError as e:
        log.info(f"读取失败: {str(e)}")
        return ""
    
def split_array(arr, max_length=12):
    return [arr[i:i + max_length] for i in range(0, len(arr), max_length)]
    
class cacheInfoUtil():

    @staticmethod
    def init_cache(cache_name, default_cache_info):
        manage_dict = {}
        if not os.path.exists(cache_name):
            save_cache(json.dumps(default_cache_info), cache_name)    
        try:
            manage_dict = json.loads(load_cache(cache_name))
        except Exception as e:
            log.info(f"加载架子信息失败: {str(e)}")
        
        return manage_dict
    
    @staticmethod
    def reset_cache_info(cache_name, manage_dict, default_cache_info):
        """
        重置cache信息
        """
        manage_dict = default_cache_info
        save_cache(json.dumps(manage_dict), cache_name) 
