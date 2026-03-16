#!/usr/bin/env python3
"""临时解决方案：使用 curl 获取数据"""

import subprocess
import json
import pandas as pd

def fetch_with_curl(url, params=None, headers=None):
    """使用 curl 获取数据"""
    cmd = ['curl', '-s', '--connect-timeout', '30']

    if headers:
        for key, value in headers.items():
            cmd.extend(['-H', f'{key}: {value}'])

    if params:
        param_str = '&'.join([f'{k}={v}' for k, v in params.items()])
        full_url = f'{url}?{param_str}'
    else:
        full_url = url

    cmd.append(full_url)

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=35)
        if result.returncode == 0:
            return result.stdout.decode('utf-8')
        else:
            return None
    except Exception as e:
        print(f'curl 错误: {e}')
        return None

def get_index_daily(symbol='sh000001', start_date='20240101', end_date='20500101'):
    """获取指数日线数据 (兼容 akshare 接口)"""
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

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    response_text = fetch_with_curl(url, params, headers)
    if not response_text:
        return pd.DataFrame()

    try:
        data_json = json.loads(response_text)
        if not data_json.get("data") or not data_json["data"].get("klines"):
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
    except Exception as e:
        print(f'解析数据错误: {e}')
        return pd.DataFrame()

if __name__ == '__main__':
    print('使用 curl 获取上证指数数据...')
    sh_data = get_index_daily(symbol='sh000001')
    if not sh_data.empty:
        print(f'✓ 成功！获取到 {len(sh_data)} 条数据')
        print(f'最新数据:\n{sh_data.tail(3)}')
    else:
        print('✗ 获取失败')
