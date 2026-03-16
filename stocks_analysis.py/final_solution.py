#!/usr/bin/env python3 
"""
临时解决方案：修改 akshare 使用 httpx 和更真实的浏览器 headers
"""

import os
# 清除代理环境变量
for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(var, None)

import httpx
import pandas as pd
import json

# 创建 httpx client，使用更真实的配置
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://quote.eastmoney.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
}

def get_index_daily_custom(symbol='sh000001', start_date='20240101', end_date='20500101'):
    """自定义的指数数据获取函数"""
    market_map = {"sz": "0", "sh": "1", "csi": "2", "bj": "0"}

    if symbol.find("sz") != -1:
        secid = "{}.{}".format(market_map["sz"], symbol.replace("sz", ""))
    elif symbol.find("bj") != -1:
        secid = "{}.{}".format(market_map["bj"], symbol.replace("bj", ""))
    elif symbol.find("sh") != -1:
        secid = "{}.{}".format(market_map["sh"], symbol.replace("sh", ""))
    elif symbol.find("csi") != -1:
        secid = "{}.{}".format(market_map["csi"], symbol.replace("csi", ""))
    else:
        return pd.DataFrame()

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "klt": "101",
        "fqt": "0",
        "beg": start_date,
        "end": end_date,
    }

    # 使用 httpx 并禁用 HTTP/2（某些服务器可能不支持）
    try:
        with httpx.Client(
            trust_env=False,
            verify=True,
            timeout=30.0,
            http1=True,
            http2=False
        ) as client:
            response = client.get(url, params=params, headers=DEFAULT_HEADERS)
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")

            if response.status_code == 200:
                data_json = response.json()
                if not data_json.get("data") or not data_json["data"].get("klines"):
                    print(f"Response data: {response.text[:500]}")
                    return pd.DataFrame()

                temp_df = pd.DataFrame(
                    [item.split(",") for item in data_json["data"]["klines"]]
                )
                temp_df.columns = ["date", "open", "close", "high", "low", "volume", "amount", "_"]
                temp_df = temp_df[["date", "open", "close", "high", "low", "volume", "amount"]]
                temp_df["open"] = pd.to_numeric(temp_df["open"], errors="coerce")
                temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
                temp_df["high"] = pd.to_numeric(temp_df["high"], errors="coerce")
                temp_df["low"] = pd.to_numeric(temp_df["low"], errors="coerce")
                temp_df["volume"] = pd.to_numeric(temp_df["volume"], errors="coerce")
                temp_df["amount"] = pd.to_numeric(temp_df["amount"], errors="coerce")
                return temp_df
            else:
                print(f"Non-200 response: {response.text[:500]}")
                return pd.DataFrame()
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    print("测试自定义函数获取上证指数数据...")
    sh_data = get_index_daily_custom(symbol='sh000001')
    if not sh_data.empty:
        print(f'✓ 成功！获取到 {len(sh_data)} 条数据')
        print(f'最新数据:\n{sh_data.tail(3)}')
    else:
        print('✗ 获取失败')
