# -*- coding: utf-8 -*-
"""
日志配置模块

使用 Python 标准库 logging 模块替代 loguru。
"""

import sys
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


# 日志根目录统一使用项目配置，避免按工作目录相对创建
from config import settings
LOG_DIR = str(settings.LOG_PATH)
os.makedirs(LOG_DIR, exist_ok=True)

# 日志格式
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "travel-agent") -> logging.Logger:
    """
    配置并返回日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复配置
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # 日志格式
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 文件处理器：按天切割，最多保留7天
    log_file = os.path.join(LOG_DIR, f"travel_{datetime.now().strftime('%Y-%m-%d')}.log")
    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "travel-agent") -> logging.Logger:
    """
    获取带模块名的日志实例
    
    Args:
        name: 模块名称
        
    Returns:
        日志记录器实例
    """
    return setup_logger(name)


# 默认日志实例
logger = get_logger()