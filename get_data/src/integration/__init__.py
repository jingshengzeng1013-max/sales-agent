# -*- coding: utf-8 -*-
"""
集成模块

对接外部系统，如微信客服等。
"""

from .wechat_service import WeChatService, WeChatUser, get_wechat_service

__all__ = ["WeChatService", "WeChatUser", "get_wechat_service"]
