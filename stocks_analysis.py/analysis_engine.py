# -*- coding: utf-8 -*-
"""A股AI投资分析系统 - 分析引擎层

包含市场情绪分析、板块轮动分析、选股筛选和报告生成功能。
"""

import os
import json
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from config import DB_PATH, THRESHOLDS


class AnalysisEngine:
    """数据分析引擎，负责从数据库读取数据并进行分析"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    def analyze_market_mood(self) -> Dict[str, any]:
        """根据宏观数据判断市场情绪（牛/熊/震荡）
        
        Returns:
            包含市场情绪判断和依据的字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            query = "SELECT * FROM macro_indicators ORDER BY date DESC LIMIT 1"
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                return {
                    "mood": "未知",
                    "score": 0,
                    "reason": "无宏观数据"
                }
            
            row = df.iloc[0]
            market_score = row['market_score']
            
            # 根据market_score判断市场情绪
            if market_score >= 70:
                mood = "牛市"
            elif market_score <= 30:
                mood = "熊市"
            else:
                mood = "震荡市"
            
            return {
                "mood": mood,
                "score": market_score,
                "reason": f"市场得分 {market_score:.1f}，基于上证指数相对20日均线乖离率计算"
            }
        except Exception as e:
            return {
                "mood": "未知",
                "score": 0,
                "reason": f"分析失败: {str(e)}"
            }
    
    def analyze_sector_rotation(self) -> Dict[str, any]:
        """分析AI板块资金流向（上游硬件 vs 下游应用）
        
        Returns:
            包含板块轮动分析结果的字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            today = datetime.now().strftime('%Y-%m-%d')
            query = "SELECT * FROM sector_performance WHERE date = ?"
            df = pd.read_sql_query(query, conn, params=(today,))
            conn.close()
            
            if df.empty:
                return {
                    "hardware_avg_change": 0,
                    "application_avg_change": 0,
                    "capital_flow": "未知",
                    "details": []
                }
            
            # 定义板块分类
            hardware_sectors = ["算力核心", "传输存储"]
            application_sectors = ["应用重估"]
            
            # 分别计算硬件和应用板块的平均涨幅
            hardware_data = df[df['trend_status'].isin(hardware_sectors)]
            application_data = df[df['trend_status'].isin(application_sectors)]
            
            hardware_avg_change = hardware_data['change_pct'].mean() if not hardware_data.empty else 0
            application_avg_change = application_data['change_pct'].mean() if not application_data.empty else 0
            
            # 判断资金流向
            if hardware_avg_change > application_avg_change:
                capital_flow = "上游硬件"
            elif application_avg_change > hardware_avg_change:
                capital_flow = "下游应用"
            else:
                capital_flow = "均衡"
            
            # 准备详细信息
            details = []
            for _, row in df.iterrows():
                details.append({
                    "sector_name": row['sector_name'],
                    "change_pct": row['change_pct'],
                    "momentum_score": row['momentum_score'],
                    "category": row['trend_status']
                })
            
            return {
                "hardware_avg_change": hardware_avg_change,
                "application_avg_change": application_avg_change,
                "capital_flow": capital_flow,
                "details": details
            }
        except Exception as e:
            return {
                "hardware_avg_change": 0,
                "application_avg_change": 0,
                "capital_flow": "未知",
                "details": [],
                "error": str(e)
            }
    
    def screen_stocks(self, strategy: str) -> List[Dict[str, any]]:
        """根据指定策略筛选股票
        
        Args:
            strategy: 策略类型 ('aggressive', 'balanced', 'conservative')
            
        Returns:
            符合条件的股票列表
        """
        if strategy not in THRESHOLDS:
            raise ValueError(f"无效策略: {strategy}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            today = datetime.now().strftime('%Y-%m-%d')
            query = "SELECT * FROM stock_technical WHERE date = ?"
            df = pd.read_sql_query(query, conn, params=(today,))
            conn.close()
            
            if df.empty:
                return []
            
            # 获取策略阈值
            threshold = THRESHOLDS[strategy]
            min_change = threshold["涨幅"]
            min_turnover = threshold["换手率"]
            
            # 计算换手率（成交额/市值，这里简化处理）
            df['turnover_rate'] = df['turnover'] / (df['price'] * df['volume'] + 1e-8)  # 避免除零
            
            # 筛选条件
            filtered_df = df[
                (df['change_pct'] > min_change) & 
                (df['turnover_rate'] > min_turnover)
            ].copy()
            
            # 添加强势标记
            filtered_df['is_strong'] = filtered_df['price'] > filtered_df['ma20']
            
            # 转换为字典列表
            result = []
            for _, row in filtered_df.iterrows():
                result.append({
                    "code": row['stock_code'],
                    "name": row['name'],
                    "price": row['price'],
                    "change_pct": row['change_pct'],
                    "turnover_rate": row['turnover_rate'],
                    "ma5": row['ma5'],
                    "ma20": row['ma20'],
                    "is_strong": bool(row['is_strong'])
                })
            
            return result
        except Exception as e:
            print(f"选股筛选失败: {e}")
            return []


class ReportGenerator:
    """报告生成器，负责生成Markdown格式的投资分析报告"""
    
    def __init__(self, engine: AnalysisEngine):
        self.engine = engine
    
    def generate_md_report(self, strategy: str = "balanced") -> str:
        """生成Markdown格式的投资分析报告
        
        Args:
            strategy: 筛选策略
            
        Returns:
            Markdown格式的报告字符串
        """
        # 获取分析数据
        market_mood = self.engine.analyze_market_mood()
        sector_rotation = self.engine.analyze_sector_rotation()
        screened_stocks = self.engine.screen_stocks(strategy)
        
        # 生成报告日期
        report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建Markdown报告
        md_content = f"# A股AI投资分析报告\\n\\n"
        md_content += f"> 报告生成时间: {report_date}\\n\\n"
        
        # 市场情绪分析
        md_content += "## 📊 市场情绪分析\\n\\n"
        md_content += f"**市场情绪**: {market_mood['mood']}\\n\\n"
        md_content += f"**情绪得分**: {market_mood['score']:.1f}/100\\n\\n"
        md_content += f"**分析依据**: {market_mood['reason']}\\n\\n"
        
        # 板块轮动分析
        md_content += "## 🔄 板块轮动分析\\n\\n"
        md_content += f"**资金流向**: {sector_rotation['capital_flow']}\\n\\n"
        md_content += f"**硬件板块平均涨幅**: {sector_rotation['hardware_avg_change']:.2%}\\n\\n"
        md_content += f"**应用板块平均涨幅**: {sector_rotation['application_avg_change']:.2%}\\n\\n"
        
        # 个股筛选结果
        md_content += "## 📈 个股筛选结果\\n\\n"
        md_content += f"**筛选策略**: {strategy.capitalize()}\\n\\n"
        
        if not screened_stocks:
            md_content += "_暂无符合条件的个股_"
        else:
            md_content += "| 股票代码 | 股票名称 | 最新价 | 涨跌幅 | 换手率 | MA5 | MA20 | 状态 |\\n"
            md_content += "|---------|---------|-------|-------|-------|-----|------|-----|\\n"
            
            for stock in screened_stocks[:20]:  # 限制显示前20只
                status = "🔥强势" if stock['is_strong'] else "📊普通"
                ma5_str = f"{stock['ma5']:.2f}" if stock['ma5'] is not None else 'N/A'
                ma20_str = f"{stock['ma20']:.2f}" if stock['ma20'] is not None else 'N/A'
                md_content += (
                    f"| {stock['code']} | {stock['name']} | {stock['price']:.2f} | "
                    f"{stock['change_pct']:.2%} | {stock['turnover_rate']:.2%} | "
                    f"{ma5_str} | {ma20_str} | {status} |\n"
                )
            
            if len(screened_stocks) > 20:
                md_content += f"\\n_还有{len(screened_stocks) - 20}只股票符合条件，此处仅显示前20只_\\n"
        
        # JSON数据摘要（供LLM分析）
        json_summary = {
            "report_date": report_date,
            "market_mood": market_mood,
            "sector_rotation": sector_rotation,
            "screened_stocks": screened_stocks[:20]  # 限制JSON大小
        }
        
        md_content += "\\n<!--\\n<OPENCLAW_AI_ANALYSIS>\\n"
        md_content += json.dumps(json_summary, ensure_ascii=False, indent=2)
        md_content += "\\n</OPENCLAW_AI_ANALYSIS>\\n-->\\n"
        
        return md_content
    
    def save_to_workspace(self, content: str, filename: Optional[str] = None) -> str:
        """保存报告到本地及workspace目录
        
        Args:
            content: 报告内容
            filename: 文件名，默认按日期生成
            
        Returns:
            保存的文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ai_investment_analysis_{timestamp}.md"
        
        # 保存到当前目录
        local_path = filename
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 保存到workspace目录
        workspace_dir = os.path.expanduser('~/.openclaw/workspace/')
        os.makedirs(workspace_dir, exist_ok=True)
        workspace_path = os.path.join(workspace_dir, filename)
        
        with open(workspace_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return local_path