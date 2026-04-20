# -*- coding: utf-8 -*-
"""
测试代理可用性 (支持白名单和账密模式)
"""
import requests
import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import CRAWLER_CONFIG
from src.crawler.proxy_manager import proxy_manager

from curl_cffi import requests as requests_cffi

def test_proxy_api():
    print(f"正在通过 ProxyManager 提取代理...\n")
    
    # 强制刷新代理池
    proxy_manager.get_proxy(force_refresh=True)
    
    if not proxy_manager.proxy_pool:
        print("未能提取到任何代理 IP，请检查 API 链接、白名单或账密配置。")
        return

    print(f"成功提取到 {len(proxy_manager.proxy_pool)} 个代理，开始逐个测试可用性...\n")
    
    # 打印当前的认证配置（隐藏部分密码）
    user = CRAWLER_CONFIG.get("proxy_user", "")
    pwd = CRAWLER_CONFIG.get("proxy_password", "")
    if user and pwd:
        masked_pwd = pwd[:2] + "*" * (len(pwd)-2) if len(pwd) > 2 else "***"
        print(f"当前模式: [账密认证] User: {user}, Pwd: {masked_pwd}")
    else:
        print(f"当前模式: [白名单认证]")
        
    print(f"\n{'代理地址':<30} {'状态':<10} {'响应时间':<10} {'测试结果'}")
    print("-" * 85)

    test_url = "https://search.ccgp.gov.cn/bxsearch"
    
    for proxy_dict in proxy_manager.proxy_pool:
        # 获取用于显示的地址 (从 http://user:pwd@ip:port 提取 ip:port)
        proxy_url = proxy_dict["http"]
        display_addr = proxy_url.split('@')[-1] if '@' in proxy_url else proxy_url.replace('http://', '')
        
        start_time = time.time()
        try:
            # 使用 curl_cffi 模拟浏览器访问
            r = requests_cffi.get(
                test_url, 
                proxies=proxy_dict, 
                timeout=15, 
                impersonate="chrome124",
                verify=False # 忽略证书错误，有时代理会导致证书校验失败
            )
            elapsed = time.time() - start_time
            
            if r.status_code == 200:
                if "频繁访问" in r.text:
                    print(f"{display_addr:<30} {'200':<10} {elapsed:<10.2f}s [FAIL] Blocked (Frequent Access)")
                else:
                    print(f"{display_addr:<30} {'200':<10} {elapsed:<10.2f}s [OK] Available")
            else:
                print(f"{display_addr:<30} {r.status_code:<10} {elapsed:<10.2f}s [FAIL] HTTP Error")
        
        except Exception as e:
            elapsed = time.time() - start_time
            err_msg = str(e)
            if "407" in err_msg:
                print(f"{display_addr:<30} {'407':<10} {elapsed:<10.2f}s [FAIL] Proxy Auth Required (Check Pwd)")
            else:
                print(f"{display_addr:<30} {'Error':<10} {elapsed:<10.2f}s [FAIL] Connection Failed ({err_msg[:25]}...)")

if __name__ == "__main__":
    test_proxy_api()
