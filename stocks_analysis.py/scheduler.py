"""A股AI投资分析系统 - 调度器

定时执行数据采集、分析和报告生成任务。
"""

import argparse
import os
import sys
import logging
from datetime import datetime, time
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pandas as pd
import sqlite3


# 彻底禁用所有代理设置
import os
import sys

# 清除可能存在的所有代理环境变量
proxy_vars = [
    'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
    'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy',
    'REQUESTS_PROXY', 'CURL_PROXY'
]
for var in proxy_vars:
    os.environ.pop(var, None)

# 禁用 requests 的代理自动检测（必须在使用任何 requests 功能前设置）
import requests
requests.Session().trust_env = False

# 同样设置到系统环境（确保子进程也不会使用代理）
os.environ['no_proxy'] = '*'
os.environ['NO_PROXY'] = '*'

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_collector import DataCollectionOrchestrator
from analysis_engine import AnalysisEngine, ReportGenerator
from config import DB_PATH


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class App:
    """应用程序主类，负责命令行参数解析和任务调度"""
    
    def __init__(self):
        self.scheduler = BlockingScheduler()
        self.workspace_dir = os.path.expanduser('~/.openclaw/workspace/')
    
    def init_db(self):
        """初始化数据库表结构"""
        logger.info("正在初始化数据库...")
        
        try:
            # 读取数据库schema文件
            schema_file = os.path.join(os.path.dirname(__file__), 'db_schema.sql')
            
            if not os.path.exists(schema_file):
                logger.error(f"数据库schema文件不存在: {schema_file}")
                return False
            
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # 执行SQL创建表
            conn = sqlite3.connect(DB_PATH)
            conn.executescript(schema_sql)
            conn.close()
            
            logger.info("数据库初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            return False
    
    def run_pipeline(self):
        """执行完整的数据采集、分析和报告生成流程"""
        try:
            logger.info("开始执行分析流程...")
            
            # 步骤1: 采集数据
            logger.info("步骤1: 开始采集数据...")
            success = DataCollectionOrchestrator.run_full_collection()
            
            if not success:
                logger.error("数据采集失败，终止流程")
                return False
            
            logger.info("步骤1: 数据采集完成")
            
            # 步骤2: 分析数据
            logger.info("步骤2: 开始分析数据...")
            engine = AnalysisEngine()
            
            # 简单验证是否有数据可用于分析
            conn = sqlite3.connect(DB_PATH)
            today = datetime.now().strftime('%Y-%m-%d')
            
            # 检查是否存在今日数据
            check_queries = [
                f"SELECT COUNT(*) FROM macro_indicators WHERE date = '{today}'",
                f"SELECT COUNT(*) FROM sector_performance WHERE date = '{today}'",
                f"SELECT COUNT(*) FROM stock_technical WHERE date = '{today}'"
            ]
            
            data_exists = True
            for query in check_queries:
                count = conn.execute(query).fetchone()[0]
                if count == 0:
                    data_exists = False
                    break
            
            conn.close()
            
            if not data_exists:
                logger.error("数据库中缺少今日数据，无法进行分析")
                return False
            
            logger.info("步骤2: 数据分析完成")
            
            # 步骤3: 生成并保存报告
            logger.info("步骤3: 开始生成报告...")
            generator = ReportGenerator(engine)
            report_content = generator.generate_md_report()
            saved_path = generator.save_to_workspace(report_content)
            
            logger.info(f"步骤3: 报告生成完成，保存至: {saved_path}")
            logger.info("分析流程执行成功完成")
            
            return True
            
        except Exception as e:
            logger.error(f"分析流程执行失败: {e}", exc_info=True)
            return False
    
    def setup_workspace(self):
        """设置工作目录"""
        try:
            os.makedirs(self.workspace_dir, exist_ok=True)
            logger.info(f"工作目录已准备: {self.workspace_dir}")
            return True
        except Exception as e:
            logger.error(f"工作目录设置失败: {e}")
            return False
    
    def is_trading_day(self, date=None):
        """简单判断是否为交易日（实际应用中应使用专业的交易日历）"""
        if date is None:
            date = datetime.now()
        
        # 周末不是交易日
        if date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            return False
        
        # 这里可以添加更多对节假日的判断
        # 简化处理：假设周一到周五都是交易日
        return True
    
    def start_scheduler(self):
        """启动定时调度器"""
        logger.info("启动定时调度器...")
        
        # 添加定时任务 - 交易日 15:30 执行
        # 注意：这会在北京时间每天15:30触发，但只会真正执行如果当天是交易日
        self.scheduler.add_job(
            self.run_pipeline_if_trading_day,
            CronTrigger(hour=15, minute=30),
            id='daily_analysis',
            name='每日AI投资分析',
            misfire_grace_time=300  # 5分钟容错
        )
        
        logger.info("定时任务已添加: 交易日 15:30 执行")
        
        try:
            logger.info("调度器开始运行...")
            self.scheduler.start()
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭调度器...")
            self.scheduler.shutdown()
            logger.info("调度器已关闭")
    
    def run_pipeline_if_trading_day(self):
        """仅在交易日执行分析流程"""
        if self.is_trading_day():
            logger.info("今天是交易日，开始执行分析流程")
            self.run_pipeline()
        else:
            logger.info("今天不是交易日，跳过分析流程")
    
    def run(self):
        """应用程序主入口"""
        # 解析命令行参数
        parser = argparse.ArgumentParser(description='A股AI投资分析系统')
        parser.add_argument('--now', action='store_true', help='立即执行一次分析流程')
        parser.add_argument('--init', action='store_true', help='初始化数据库')
        parser.add_argument('--cron', action='store_true', help='启动定时调度器')
        
        args = parser.parse_args()
        
        # 设置工作目录
        if not self.setup_workspace():
            logger.error("工作目录设置失败，程序退出")
            return 1
        
        # 根据命令行参数执行相应操作
        if args.init:
            if not self.init_db():
                return 1
        
        if args.now:
            if not self.run_pipeline():
                return 1
        
        if args.cron:
            self.start_scheduler()
        
        # 如果没有指定任何参数，显示帮助信息
        if not any([args.init, args.now, args.cron]):
            parser.print_help()
            return 0
        
        return 0


def main():
    """程序入口点"""
    app = App()
    exit_code = app.run()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()