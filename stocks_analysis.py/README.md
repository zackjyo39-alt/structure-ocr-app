# A股AI投资分析系统

基于思维链 + 对抗性优化的A股AI投资分析系统，提供完整的市场情绪分析、板块轮动分析和智能选股功能。

## 🚀 快速开始

### 1. 环境部署
```bash
# 克隆项目（如果需要）
# git clone <repository>
# cd ai_invest

# 运行部署脚本（自动创建虚拟环境、安装依赖、初始化数据库）
chmod +x deploy.sh
./deploy.sh
```

部署脚本会：
- ✅ 检查Python环境
- ✅ 创建虚拟环境 `venv`
- ✅ 安装所有依赖包
- ✅ 初始化SQLite数据库
- ✅ 可选：运行测试分析

### 2. 手动部署（可选）
```bash
# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python scheduler.py --init
```

## 📊 使用方法

### 立即执行分析
```bash
source venv/bin/activate
python scheduler.py --now
```

### 启动定时分析（交易日15:30自动执行）
```bash
source venv/bin/activate
python scheduler.py --cron
```

### 查看帮助
```bash
python scheduler.py --help
```

## 📁 项目结构

```
ai_invest/
├── config.py              # 配置文件（AI板块分类、策略阈值等）
├── db_schema.sql          # 数据库表结构
├── data_collector.py      # 数据采集层
├── analysis_engine.py     # 分析引擎
├── scheduler.py           # 主调度程序
├── deploy.sh              # 一键部署脚本
├── requirements.txt       # 依赖清单
├── ai_investment.db       # SQLite数据库
└── system.log             # 系统日志
```

## 🎯 核心功能

### 1. 市场情绪分析
- 基于上证指数20日均线乖离率计算市场得分
- 自动判断牛市/熊市/震荡市状态

### 2. AI板块轮动分析
- 四大核心板块：算力核心、传输存储、能源基座、应用重估
- 资金流向判断：上游硬件 vs 下游应用
- 动量评分算法（涨幅权重40% + 成交额权重60%）

### 3. 智能选股筛选
- 三种策略：激进型、平衡型、保守型
- 自动筛选强势个股（收盘价 > 20日均线）

### 4. 报告自动生成
- Markdown格式分析报告
- 同时保存到本地和 `~/.openclaw/workspace/`
- 包含JSON数据摘要，方便LLM进一步分析

## 📈 数据来源

- **宏观数据**: 上证指数、深证指数、标普500、纳斯达克、VIX恐慌指数
- **板块数据**: 东方财富行业板块和概念板块
- **个股数据**: A股实时行情和技术指标

## 🔧 配置说明

### AI板块分类 (`config.py`)
```python
AI_SECTORS = {
    "算力核心": ["半导体", "芯片", "AI芯片", "集成电路", "算力"],
    "传输存储": ["CPO概念", "光模块", "存储芯片", "HBM"],
    "能源基座": ["虚拟电厂", "智能电网", "核能核电", "电力行业"],
    "应用重估": ["银行", "Sora概念", "AIGC", "数字经济", "多模态AI"]
}
```

### 筛选策略阈值
```python
THRESHOLDS = {
    "aggressive": {"涨幅": 0.05, "换手率": 0.08, "动量": 70},
    "balanced": {"涨幅": 0.03, "换手率": 0.05, "动量": 60},
    "conservative": {"涨幅": 0.02, "换手率": 0.03, "动量": 50}
}
```

## 📋 依赖包

- `akshare>=1.16.72`: 财经数据接口
- `pandas>=2.0.0`: 数据处理
- `apscheduler>=3.10.0`: 定时任务
- `tqdm>=4.60.0`: 进度条
- `sqlalchemy>=2.0.0`: 数据库ORM

## ⚠️ 注意事项

1. **网络环境**: 需要稳定的网络连接获取财经数据
2. **交易时间**: 系统会在交易日15:30后执行数据采集
3. **数据时效**: 建议在交易日使用，节假日可能无数据
4. **虚拟环境**: 务必使用虚拟环境，避免污染系统Python

## 🔍 故障排除

### 常见问题

1. **依赖安装失败**
   ```bash
   # 升级pip
   pip install --upgrade pip
   # 重新安装
   pip install -r requirements.txt
   ```

2. **数据库初始化失败**
   ```bash
   # 检查文件权限
   ls -la db_schema.sql
   # 手动初始化
   sqlite3 ai_investment.db < db_schema.sql
   ```

3. **数据采集失败**
   - 检查网络连接
   - 查看 `system.log` 日志文件
   - 确认akshare版本兼容性

4. **定时任务不执行**
   - 检查系统时间设置
   - 确认时区设置（北京时间15:30）
   - 查看日志确认任务状态

## 📝 日志查看

```bash
# 查看系统日志
tail -f system.log

# 查看最近的分析报告
ls -la *.md | tail -5
cat $(ls -t *.md | head -1)
```

## 🔄 更新维护

```bash
# 更新依赖
source venv/bin/activate
pip install --upgrade -r requirements.txt

# 重新初始化数据库（会清空数据）
rm ai_investment.db
python scheduler.py --init
```

## 📊 输出示例

系统会生成类似以下格式的分析报告：

```markdown
# A股AI投资分析报告

> 报告生成时间: 2026-02-09 22:10:43

## 📊 市场情绪分析
**市场情绪**: 震荡市
**情绪得分**: 53.0/100

## 🔄 板块轮动分析
**资金流向**: 上游硬件
**硬件板块平均涨幅**: 2.50%
**应用板块平均涨幅**: 0.00%

## 📈 个股筛选结果
**筛选策略**: Balanced
| 股票代码 | 股票名称 | 最新价 | 涨跌幅 | 换手率 | MA5 | MA20 | 状态 |
|---------|---------|-------|-------|-------|-----|------|-----|
| 000001 | 平安银行 | 10.50 | 1.5% | 2.3% | 10.2 | 10.0 | 🔥强势 |
```

---

**🎯 投资建议**: 本系统仅供学习参考，不构成投资建议。投资有风险，入市需谨慎。