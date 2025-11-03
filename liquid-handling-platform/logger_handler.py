from datetime import datetime, timedelta
import logging
from logging.handlers import TimedRotatingFileHandler, SysLogHandler
import os
import time
import re

backup_days = 30
remote_address = "192.168.1.229"
log_dir = "./logs"

def make_dir(make_dir_path):
    path = make_dir_path.strip()
    if not os.path.exists(path):
        os.makedirs(path)

class DailyFileHandler(logging.FileHandler):
    def __init__(self, log_dir, filename_prefix="gateway",  backup_days=30):
        self.log_dir = log_dir
        self.filename_prefix = filename_prefix
        self.current_date = datetime.now().strftime("%Y%m%d")
        os.makedirs(log_dir, exist_ok=True)
        self.backup_days = backup_days
        current_path = self._get_today_log_path()
        super().__init__(current_path, encoding="utf-8")
        self._cleanup_old_logs()

    def _get_today_log_path(self):
        return os.path.join(
            self.log_dir,
            f"{self.current_date}_{self.filename_prefix}.log"
        )
    
    def _cleanup_old_logs(self):
        """定期删除旧日志文件"""
        try:
            now = datetime.now()
            # 计算截止日期
            cutoff_date = now - timedelta(days=backup_days)
            
            # 遍历日志目录
            for filename in os.listdir(self.log_dir):
                filepath = os.path.join(self.log_dir, filename)
                if os.path.isfile(filepath):
                    # 匹配格式：20241024_gateway.log
                    match = re.match(r'(\d{8})_' + re.escape(self.filename_prefix) + r'\.log', filename)
                    if match:
                        file_date_str = match.group(1)
                        try:
                            file_date = datetime.strptime(file_date_str, "%Y%m%d")
                            # 如果文件日期早于截止日期，则删除
                            if file_date < cutoff_date:
                                os.remove(filepath)
                                print(f"Deleted old log file: {filename}")
                        except ValueError:
                            # 日期解析失败，跳过此文件
                            continue
        except Exception as e:
            print(f"Error during log cleanup: {e}")

    def emit(self, record):
        today = datetime.now().strftime("%Y%m%d")
        if today != self.current_date:
            self.close()
            self.current_date = today
            self.baseFilename = self._get_today_log_path()
            self.stream = self._open()
        super().emit(record)

def create_logger(level='DEBUG', name=None):
    make_dir(log_dir)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 移除原有轮转 Handler
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
            logger.removeHandler(handler)
    
    # 1. 添加自定义每日文件 Handler
    daily_handler = DailyFileHandler(log_dir, filename_prefix="gateway", backup_days=backup_days)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(threadName)s - %(filename)s - %(funcName)s - %(lineno)s - %(message)s'
    )
    daily_handler.setFormatter(formatter)
    logger.addHandler(daily_handler)
    
    # 2. 新增控制台处理器 [6,7](@ref)
    console_handler = logging.StreamHandler()  # 输出到sys.stderr
    console_handler.setLevel(level)  # 与控制台日志级别一致
    console_handler.setFormatter(formatter)  # 复用相同格式
    logger.addHandler(console_handler)
    
    return logger