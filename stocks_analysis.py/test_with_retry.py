#!/usr/bin/env python3
"""测试4：增加重试和延迟"""

import os
import sys

# 清除所有代理环境变量
proxy_vars = [
    'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
    'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy',
    'REQUESTS_PROXY', 'CURL_PROXY', 'ftp_proxy', 'FTP_PROXY',
    'socks_proxy', 'SOCKS_PROXY'
]
for var in proxy_vars:
    os.environ[var] = ''

import requests
import time

# 默认 headers
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
}

# Monkey patch requests.Session.__init__
_original_session_init = requests.Session.__init__
def patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.trust_env = False
    self.proxies = {}
    self.headers.update(DEFAULT_HEADERS)
    self.timeout = 30
requests.Session.__init__ = patched_session_init

# Monkey patch requests.get with retry
_original_get = requests.get
def patched_get(url, params=None, **kwargs):
    kwargs.setdefault('proxies', {})
    kwargs.setdefault('timeout', 30)
    kwargs.setdefault('headers', DEFAULT_HEADERS)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            return _original_get(url, params=params, **kwargs)
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"  连接失败，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                raise
requests.get = patched_get

# 导入 akshare
print("导入 akshare...")
import akshare as ak

print(f"akshare 版本: {ak.__version__ if hasattr(ak, '__version__') else 'unknown'}")

# 测试获取数据
print("\n测试获取上证指数数据...")
try:
    sh_data = ak.stock_zh_index_daily_em(symbol='sh000001')
    print(f"✓ 成功！获取到 {len(sh_data)} 条数据")
    print(f"最新数据:\n{sh_data.tail(3)}")
    print("\n测试成功！代理问题已解决。")
except Exception as e:
    print(f"✗ {type(e).__name__}: {str(e)[:300]}")
