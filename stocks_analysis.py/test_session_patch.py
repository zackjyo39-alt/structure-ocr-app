#!/usr/bin/env python3
"""测试3：彻底 monkey patch requests.Session"""

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

# Monkey patch requests.Session.__init__ 来禁用代理
_original_session_init = requests.Session.__init__

def patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.trust_env = False
    self.proxies = {}

requests.Session.__init__ = patched_session_init

# Monkey patch requests.get 和 requests.post
_original_get = requests.get
_original_post = requests.post

def patched_get(url, params=None, **kwargs):
    kwargs.setdefault('proxies', {})
    kwargs.setdefault('timeout', 30)
    if 'headers' not in kwargs:
        kwargs['headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    return _original_get(url, params=params, **kwargs)

def patched_post(url, data=None, json=None, **kwargs):
    kwargs.setdefault('proxies', {})
    kwargs.setdefault('timeout', 30)
    if 'headers' not in kwargs:
        kwargs['headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    return _original_post(url, data=data, json=json, **kwargs)

requests.get = patched_get
requests.post = patched_post

# 也 patch Session.request 方法
_original_session_request = requests.Session.request
def patched_session_request(self, method, url, **kwargs):
    kwargs.setdefault('proxies', {})
    kwargs.setdefault('timeout', 30)
    if 'headers' not in kwargs:
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
    return _original_session_request(self, method, url, **kwargs)
requests.Session.request = patched_session_request

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
except requests.exceptions.ProxyError as e:
    print(f"✗ ProxyError: {str(e)[:200]}")
    print("代理问题仍然存在")
except Exception as e:
    print(f"✗ {type(e).__name__}: {str(e)[:200]}")
