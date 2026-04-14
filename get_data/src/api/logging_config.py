# -*- coding: utf-8 -*-
"""FastAPI 应用日志配置"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.logger import setup_logger

# 初始化日志
logger = setup_logger('api_server', log_to_file=True)
