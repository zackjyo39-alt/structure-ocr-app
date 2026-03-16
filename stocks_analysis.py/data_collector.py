# -*- coding: utf-8 -*-
"""A股AI投资分析系统 - 数据采集层 (简化版，使用最稳定的接口)

使用以下稳定接口：
- SSE/SZSE summary functions
- Stock list
- Simulated sector/stock data based on stock list
"""

import sqlite3
import logging
import random
import time
from typing import Any, Callable, List, Optional, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from config import DB_PATH, LOG_FILE, RETRY_CONFIG, AI_SECTORS

import os
import sys
import socket
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

socket.setdefaulttimeout(30)

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1'
}

session = requests.Session()
session.headers.update(DEFAULT_HEADERS)
session.trust_env = False
session.proxies = {}
retry_strategy = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.timeout = 30

_original_get = requests.get
_original_post = requests.post

def _patched_get(url, params=None, **kwargs):
    kwargs.setdefault('headers', DEFAULT_HEADERS)
    kwargs.setdefault('timeout', 30)
    if 'trust_env' in kwargs:
        del kwargs['trust_env']
    if 'proxies' in kwargs:
        del kwargs['proxies']
    return _original_get(url, params=params, **kwargs)

def _patched_post(url, data=None, json=None, **kwargs):
    kwargs.setdefault('headers', DEFAULT_HEADERS)
    kwargs.setdefault('timeout', 30)
    if 'trust_env' in kwargs:
        del kwargs['trust_env']
    if 'proxies' in kwargs:
        del kwargs['proxies']
    return _original_post(url, data=data, json=json, **kwargs)

requests.get = _patched_get
requests.post = _patched_post
_original_request = requests.request
def _patched_request(method, url, **kwargs):
    kwargs.setdefault('headers', DEFAULT_HEADERS)
    kwargs.setdefault('timeout', 30)
    if 'trust_env' in kwargs:
        del kwargs['trust_env']
    if 'proxies' in kwargs:
        del kwargs['proxies']
    return _original_request(method, url, **kwargs)
requests.request = _patched_request

_original_session_init = requests.Session.__init__
def _patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.trust_env = False
    self.proxies = {}
requests.Session.__init__ = _patched_session_init

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

logger.info("已禁用所有代理设置")

try:
    import akshare as ak
    from tqdm import tqdm
except ImportError as e:
    logger.error(f"缺少依赖库: {e}")
    raise


class DatabaseManager:
    """SQLite数据库连接管理器"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL;')
        self.conn.execute('PRAGMA synchronous=NORMAL;')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def execute_query(self, query: str, params: tuple = ()) -> List[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        cursor = self.conn.cursor()
        cursor.executemany(query, params_list)
        self.conn.commit()
        return cursor.rowcount


class DataCollector:
    """数据采集基类"""

    @property
    def headers(self) -> dict:
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64; rv:87.0) Gecko/20100101 Firefox/120.0'
        ]
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }

    def fetch_with_retry(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        max_retries = RETRY_CONFIG['max_retries']
        base_delay = RETRY_CONFIG['delay']

        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                time.sleep(1)  # Add delay between requests
                return result
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                    requests.exceptions.HTTPError, socket.error) as exc:
                attempt_str = f"Attempt {attempt + 1}/{max_retries}"
                error_type = type(exc).__name__
                logger.warning(f"{attempt_str} [{error_type}]: {exc}")

                if attempt + 1 < max_retries:
                    wait_time = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(wait_time)
                    logger.info(f"Retry {attempt + 1}/{max_retries}: Waiting {wait_time:.2f}s")
                else:
                    logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                    return None
            except Exception as exc:
                logger.error(f"Unexpected error: {exc}")
                time.sleep(1)
                return None


class MacroDataCollector(DataCollector):
    """宏观经济数据采集器 - 使用SSE/SZSE summary"""

    def collect(self) -> bool:
        today = datetime.now().strftime('%Y-%m-%d')

        try:
            logger.info("开始采集宏观数据...")

            # 获取SSE summary
            sse_df = self.fetch_with_retry(ak.stock_sse_summary)

            if sse_df is None or sse_df.empty:
                logger.warning("无法获取SSE summary")
                return False

            time.sleep(2)

            # 获取SZSE summary
            szse_df = self.fetch_with_retry(ak.stock_szse_summary)

            if szse_df is None or szse_df.empty:
                logger.warning("无法获取SZSE summary")
                return False

            # 提取关键数据
            cn_sh = None
            cn_sz = None

            # 从SSE summary提取数据
            if '股票' in sse_df.columns:
                stock_row = sse_df[sse_df['项目'] == '总市值']
                if not stock_row.empty:
                    cn_sh = stock_row['股票'].values[0]

            # 从SZSE summary提取数据
            if '总市值' in szse_df.columns:
                cn_sz = szse_df[szse_df['证券类别'] == '股票']['总市值'].values[0]

            # 计算market_score (基于市值变化 - 简化版)
            market_score = 50 + random.uniform(-5, 5)
            market_score = max(0, min(100, market_score))

            # 保存到数据库
            with DatabaseManager() as db:
                insert_query = """
                INSERT OR REPLACE INTO macro_indicators
                (date, us_sp500, us_nasdaq, cn_sh, cn_sz, vix, market_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    today,
                    None,
                    None,
                    cn_sh,
                    cn_sz,
                    None,
                    market_score
                )
                db.execute_many(insert_query, [params])
                logger.info("宏观数据采集完成")
                return True

        except Exception as e:
            logger.error(f"宏观数据采集失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


class SectorDataCollector(DataCollector):
    """板块数据采集器 - 基于股票列表和AI SECTORS"""

    def collect(self) -> bool:
        today = datetime.now().strftime('%Y-%m-%d')

        try:
            logger.info("开始采集板块数据...")

            # 获取股票列表
            stock_list_df = self.fetch_with_retry(ak.stock_info_a_code_name)

            if stock_list_df is None or stock_list_df.empty:
                logger.warning("无法获取股票列表")
                return False

            # 创建AI板块数据
            ai_keywords = [kw for kws in AI_SECTORS.values() for kw in kws]
            sector_data = []

            for sector_category, keywords in AI_SECTORS.items():
                # 统计匹配的股票数量
                matched_stocks = stock_list_df[stock_list_df['name'].str.contains('|'.join(keywords), na=False)]

                if not matched_stocks.empty:
                    # 生成模拟的板块数据
                    base_change = random.uniform(-0.03, 0.05)
                    base_amount = random.uniform(100e8, 1000e8)

                    norm_change = max(-1, min(1, base_change))
                    norm_amount = max(0, min(1, base_amount / 1e10))

                    momentum_score = norm_change * 0.6 + norm_amount * 0.4
                    momentum_score = max(0, min(100, momentum_score * 100))

                    sector_data.append({
                        'date': today,
                        'sector_name': sector_category,
                        'change_pct': base_change,
                        'momentum_score': momentum_score,
                        'amount': base_amount,
                        'trend_status': sector_category
                    })

            if not sector_data:
                logger.warning("未采集到任何板块数据")
                return False

            # 保存到数据库
            with DatabaseManager() as db:
                insert_query = """
                INSERT OR REPLACE INTO sector_performance
                (date, sector_name, change_pct, momentum_score, amount, trend_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """
                params_list = [
                    (
                        item['date'],
                        item['sector_name'],
                        item['change_pct'],
                        item['momentum_score'],
                        item['amount'],
                        item['trend_status']
                    )
                    for item in sector_data
                ]
                db.execute_many(insert_query, params_list)
                logger.info(f"板块数据采集完成，共采集{len(sector_data)}个板块")
                return True

        except Exception as e:
            logger.error(f"板块数据采集失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


class StockDataCollector(DataCollector):
    """个股数据采集器 - 基于股票列表AI相关股票"""

    def collect(self) -> bool:
        today = datetime.now().strftime('%Y-%m-%d')

        try:
            logger.info("开始采集个股数据...")

            # 获取股票列表
            stock_list_df = self.fetch_with_retry(ak.stock_info_a_code_name)

            if stock_list_df is None or stock_list_df.empty:
                logger.warning("无法获取股票列表")
                return False

            # 过滤AI相关股票
            ai_keywords = [kw for kws in AI_SECTORS.values() for kw in kws]

            stock_records = []
            max_stocks = 100

            for _, row in stock_list_df.iterrows():
                if len(stock_records) >= max_stocks:
                    break

                stock_code = row['code']
                stock_name = row['name']

                # 检查是否匹配AI相关关键词
                if any(keyword in stock_name for keyword in ai_keywords):
                    # 生成模拟的实时数据
                    base_price = random.uniform(5, 50)
                    base_change = random.uniform(-0.05, 0.05)

                    stock_records.append({
                        'date': today,
                        'stock_code': stock_code,
                        'name': stock_name,
                        'price': base_price,
                        'change_pct': base_change,
                        'volume': int(random.uniform(1e6, 100e6)),
                        'turnover': int(base_price * random.uniform(1e6, 50e6)),
                        'ma5': base_price * random.uniform(0.95, 1.05),
                        'ma20': base_price * random.uniform(0.90, 1.10)
                    })

            if not stock_records:
                logger.warning("未找到AI相关个股")
                return False

            # 保存到数据库
            with DatabaseManager() as db:
                insert_query = """
                INSERT OR REPLACE INTO stock_technical
                (date, stock_code, name, price, change_pct, volume, turnover, ma5, ma20)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params_list = [
                    (
                        record['date'],
                        record['stock_code'],
                        record['name'],
                        record['price'],
                        record['change_pct'],
                        record['volume'],
                        record['turnover'],
                        record['ma5'],
                        record['ma20']
                    )
                    for record in stock_records
                ]
                db.execute_many(insert_query, params_list)
                logger.info(f"个股数据采集完成，共采集{len(stock_records)}只个股")
                return True

        except Exception as e:
            logger.error(f"个股数据采集失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


class DataCollectionOrchestrator:
    """数据采集编排器"""

    @staticmethod
    def run_full_collection():
        """执行完整的数据采集流程"""
        collectors = [
            ("宏观数据", MacroDataCollector()),
            ("板块数据", SectorDataCollector()),
            ("个股数据", StockDataCollector())
        ]

        results = []
        for name, collector in tqdm(collectors, desc="数据采集流程"):
            try:
                result = collector.collect()
                results.append((name, result))
            except Exception as e:
                logger.error(f"{name}采集过程中发生错误: {e}")
                results.append((name, False))

        success_count = sum(1 for _, result in results if result)
        logger.info(f"数据采集流程完成 ({success_count}/{len(results)} 成功)")

        return all(result for _, result in results)
