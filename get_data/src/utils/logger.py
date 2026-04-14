# -*- coding: utf-8 -*-
"""
统一日志配置模块
集中管理所有日志配置
"""

import os
import sys
import logging
from datetime import datetime

# 项目根目录
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志根目录
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


def setup_logger(name: str, level: int = logging.INFO, log_to_file: bool = True) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志名称（通常是模块名）
        level: 日志级别
        log_to_file: 是否写入文件

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    if log_to_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(LOGS_DIR, f"{name}_{timestamp}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """获取已存在的日志记录器"""
    return logging.getLogger(name)


def cleanup_old_logs(days: int = 30):
    """
    清理指定天数之前的日志文件

    Args:
        days: 保留天数，默认 30 天
    """
    import time
    now = time.time()
    cutoff = now - (days * 86400)

    for filename in os.listdir(LOGS_DIR):
        if filename.endswith('.log'):
            filepath = os.path.join(LOGS_DIR, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f"已删除旧日志：{filename}")


# 预定义的日志级别
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}
