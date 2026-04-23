# -*- coding: utf-8 -*-
"""
代理管理器：支持多 IP 池，负责从青果网络获取并自动轮询刷新代理 IP
"""

import time
import requests
import logging
import threading
from typing import Dict, Optional, List
from src.config import CRAWLER_CONFIG

logger = logging.getLogger("proxy_manager")

class ProxyManager:
    def __init__(self):
        self.api_url = CRAWLER_CONFIG.get("proxy_api_url")
        self.use_proxy = CRAWLER_CONFIG.get("use_proxy", False)
        self.ttl = CRAWLER_CONFIG.get("proxy_ttl", 60)
        self.proxy_user = CRAWLER_CONFIG.get("proxy_user", "")
        self.proxy_password = CRAWLER_CONFIG.get("proxy_password", "")
        
        self.proxy_pool: List[Dict[str, str]] = []
        self.last_fetch_time: float = 0
        self._lock = threading.Lock()
        self._current_index = 0
        
    def get_proxy(self, force_refresh: bool = False) -> Optional[Dict[str, str]]:
        """
        获取一个代理。采用轮询方式从池中取。
        如果池为空、超过 TTL 或强制刷新，则从 API 重新获取。
        """
        if not self.use_proxy:
            return None
            
        with self._lock:
            now = time.time()
            
            # 频率保护：如果距离上次成功提取不足 5 秒，即使强制刷新也忽略，防止触发 API 400 错误
            is_too_frequent = (now - self.last_fetch_time) < 5
            
            # 决定是否需要刷新
            need_refresh = False
            if not self.proxy_pool:
                need_refresh = True
            elif (now - self.last_fetch_time) >= self.ttl:
                need_refresh = True
            elif force_refresh and not is_too_frequent:
                need_refresh = True
            
            if need_refresh:
                # 如果是强制刷新，先清空旧池，防止旧 IP 继续被使用
                if force_refresh:
                    self.proxy_pool = []
                self._fetch_new_proxies()
            
            if not self.proxy_pool:
                return None
            
            # 轮询取出下一个代理
            proxy = self.proxy_pool[self._current_index]
            self._current_index = (self._current_index + 1) % len(self.proxy_pool)
            return proxy

    def _build_proxy_url(self, server: str) -> str:
        """根据是否配置了账密构建代理 URL"""
        if self.proxy_user and self.proxy_password:
            return f"http://{self.proxy_user}:{self.proxy_password}@{server}"
        return f"http://{server}"

    def _fetch_new_proxies(self):
        """从青果网络 API 提取一批新代理 (支持 TXT 格式)"""
        try:
            logger.info(f"正在从青果网络批量提取新代理 IP...")
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                text = response.text.strip()
                if not text:
                    logger.error("提取代理失败: API 返回内容为空")
                    return
                
                # 尝试解析为 JSON (兼容旧格式)
                try:
                    res_json = response.json()
                    if res_json.get("code") == "SUCCESS" and res_json.get("data"):
                        new_pool = []
                        for item in res_json["data"]:
                            server = item.get("server")
                            if server:
                                proxy_url = self._build_proxy_url(server)
                                new_pool.append({"http": proxy_url, "https": proxy_url})
                        if new_pool:
                            self._update_pool(new_pool)
                            return
                except:
                    # 如果不是 JSON，按 TXT 格式处理 (每行一个 IP:Port)
                    lines = [line.strip() for line in text.split('\n') if ':' in line]
                    if lines:
                        new_pool = []
                        for line in lines:
                            proxy_url = self._build_proxy_url(line)
                            new_pool.append({"http": proxy_url, "https": proxy_url})
                        self._update_pool(new_pool)
                        return
                
                logger.error(f"解析代理响应失败: {text[:200]}")
            else:
                logger.error(f"请求代理 API 失败，状态码: {response.status_code}")
                
        except Exception as e:
            logger.error(f"提取代理异常: {e}")
            
        # 如果提取失败且池子已过期，清空池子
        if not self.proxy_pool or (time.time() - self.last_fetch_time) >= self.ttl:
            self.proxy_pool = []

    def _update_pool(self, new_pool: List[Dict[str, str]]):
        """更新代理池状态"""
        self.proxy_pool = new_pool
        self.last_fetch_time = time.time()
        self._current_index = 0
        logger.info(f"成功提取并加载 {len(new_pool)} 个代理 IP。")

# 全局单例
proxy_manager = ProxyManager()
