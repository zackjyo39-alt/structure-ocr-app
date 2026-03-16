#!/usr/bin/env python3
"""测试2：在 import akshare 之前完全禁用代理"""

import os
import sys

# 第一步：完全禁用所有代理环境变量（设置为空字符串）
proxy_vars = [
    'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
    'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy',
    'REQUESTS_PROXY', 'CURL_PROXY', 'ftp_proxy', 'FTP_PROXY',
    'socks_proxy', 'SOCKS_PROXY'
]
for var in proxy_vars:
    os.environ[var] = ''

# 第二步：禁用 requests 读取环境变量
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 创建一个配置好的 session
session = requests.Session()
session.trust_env = False
session.proxies = {}

# 重试策略
retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["HEAD", "GET", "OPTIONS"])
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.timeout = 30

# Monkey patch requests.get 和 requests.request（在导入 akshare 之前！）
_original_get = requests.get
_original_request = requests.request

def patched_get(url, params=None, **kwargs):
    kwargs.setdefault('proxies', {})
    kwargs.setdefault('timeout', 30)
    return _original_get(url, params=params, **kwargs)

def patched_request(method, url, **kwargs):
    kwargs.setdefault('proxies', {})
    kwargs.setdefault('timeout', 30)
    return _original_request(method, url, **kwargs)

requests.get = patched_get
requests.request = patched_request

# 第三步：现在才导入 akshare
print("导入 akshare...")
import akshare as ak

print(f"akshare 版本: {ak.__version__ if hasattr(ak, '__version__') else 'unknown'}")

# 第四步：测试获取数据
print("\n测试获取上证指数数据...")
try:
    sh_data = ak.stock_zh_index_daily_em(symbol='sh000001')
    print(f"✓ 成功！获取到 {len(sh_data)} 条数据")
    print(f"最新数据:\n{sh_data.tail(3)}")
    print("\n测试成功！代理问题已解决。")
except requests.exceptions.ProxyError as e:
    print(f"✗ ProxyError: {str(e)[:200]}")
    print("代理问题仍然存在")
except Exception as e:
    print(f"✗ {type(e).__name__}: {str(e)[:200]}")
