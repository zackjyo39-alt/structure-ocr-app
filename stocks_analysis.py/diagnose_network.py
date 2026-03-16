#!/usr/bin/env python3
"""诊断脚本：测试网络连接和代理配置"""

import os
import sys

# 清除所有代理环境变量
proxy_vars = [
    'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
    'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy',
    'REQUESTS_PROXY', 'CURL_PROXY'
]
print("=" * 60)
print("第一步：清除代理环境变量")
for var in proxy_vars:
    if var in os.environ:
        val = os.environ[var]
        del os.environ[var]
        print(f"  ✓ 删除 {var} = {val}")
    else:
        print(f"  - {var} 不存在")

import requests
import socket
import subprocess

# 配置请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

print("\n" + "=" * 60)
print("第二步：测试 curl 命令（绕过 Python）")
test_urls = [
    "http://push2.eastmoney.com",
    "http://push2his.eastmoney.com",
    "http://79.push2.eastmoney.com",
]
for url in test_urls:
    print(f"  测试: {url}")
    try:
        result = subprocess.run([
            'curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
            '--connect-timeout', '10',
            url
        ], capture_output=True, timeout=15)
        code = result.stdout.decode().strip()
        if code == '000':
            print(f"    ✗ 连接失败 (curl 返回 000)")
        elif code == '200':
            print(f"    ✓ 成功 (HTTP {code})")
        else:
            print(f"    ℹ 状态码: {code}")
    except Exception as e:
        print(f"    ✗ 错误: {e}")

print("\n" + "=" * 60)
print("第三步：测试 Python requests (禁用代理)")

for url in test_urls:
    print(f"  测试: {url}")
    try:
        # 使用临时 session，显式禁用所有代理
        session = requests.Session()
        session.trust_env = False
        session.proxies.clear()
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"    ✓ 成功 (HTTP {response.status_code})")
        else:
            print(f"    ℹ 状态码: {response.status_code}")
    except requests.exceptions.ProxyError as e:
        print(f"    ✗ ProxyError (仍然在尝试使用代理!)")
        print(f"       错误详情: {str(e)[:100]}")
    except Exception as e:
        print(f"    ✗ {type(e).__name__}: {str(e)[:100]}")

print("\n" + "=" * 60)
print("第四步：测试 akshare 获取上证指数数据")
sys.path.insert(0, '.')
try:
    import akshare as ak
    print("  调用 ak.stock_zh_index_daily_em(symbol='sh000001')...")
    sh_data = ak.stock_zh_index_daily_em(symbol='sh000001')
    print(f"    ✓ 成功获取 {len(sh_data)} 条数据")
    print(f"    最新数据: {sh_data.tail(1)}")
except requests.exceptions.ProxyError as e:
    print(f"    ✗ ProxyError (akshare 仍然在使用代理!)")
    print(f"       错误详情: {str(e)[:200]}")
except Exception as e:
    print(f"    ✗ {type(e).__name__}: {str(e)[:200]}")

print("\n" + "=" * 60)
print("诊断完成")
print("\n如果 curl 成功但 requests 失败，说明 Python 配置有问题")
print("如果 curl 也失败，说明 ClashXPro 配置未生效")
print("=" * 60)
