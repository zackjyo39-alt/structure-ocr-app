# AIInvest — 工程实践完全手册 v2.0

> **版本**: 3.0.0（全面重构版）
> **日期**: 2026-02-25
> **定位**: 个人MVP · A股/基金AI辅助投资研究系统
> **基础设施**: 前端 Lovable 免费层 · 后端小型 VPS · 逐步迭代
> **视角**: AI架构师 × 量化分析师 × A股交易员 × 全栈工程师 × 测试工程师

---

## 📋 目录

```
Part 0   — 项目定位、边界与核心约束
Part I   — A股领域建模：市场特有概念精确建模
Part II  — 数据架构：数据源选型 · 缓存策略 · 韧性设计
Part III — 系统架构：MVP技术选型与目录结构
Part IV  — SOLID原则在A股金融领域的具体落地
Part V   — 设计模式目录（已用 + 建议引入）
Part VI  — 命名规范：领域驱动 + Python/TypeScript双标准
Part VII — Git最佳实践：分支策略 · Commit规范 · Tag策略
Part VIII — AI辅助开发工作流（AI Skills for Developers）
Part IX  — 代码质量门禁与自动化流水线
Part X   — MVP迭代路线：从0到可用
另外，必须要求系统可观测性，要求作为系统管理员，可以清晰看到调用链路+系统瓶颈等，未来可形成自愈系统。
附录     — CLAUDE.md模板 · ADR记录 · 工具速查手册
```

---

# Part 0 — 项目定位、边界与核心约束

> **先把边界说清楚，才能让AI生成正确的代码。** 这部分是整个项目的"北极星"，每次AI coding前必须确保AI读取了这份定义。

## 0.1 系统定位（精确描述）

| 维度 | 描述 |
|------|------|
| **是什么** | 个人使用的AI辅助A股/基金投资**研究与决策**工具 |
| **核心价值** | 用AI加速信息收集与综合分析，提升投资决策质量 |
| **用户规模** | 5个用户左右，多租户架构 |
| **部署形态** | 前端Lovable托管，后端VPS（2-4GB RAM） |
| **不做的事** | 自动交易执行、信号对外发布、策略产品销售 |

## 0.2 MVP阶段定义

```
Phase 0（当前）：基础研究框架
├── A股基础行情查询（AKShare）
├── 单股AI综合分析报告
├── 多股/美股/东京股市对比分析（有时候，美股/东京股市能提取预警中国股市，基金等）
├── LLM多模型切换（DeepSeek/Ollama/Nvidia NIM/Gemini等）
└── 分析历史记录与重放


Phase 1（1-2个月）：数据丰富化
├── 技术指标计算（MA/MACD/RSI/KDJ/布林带）
├── 基本面数据（财务报表核心指标）
├── 实时资金流向（主力资金/北向资金）
├── 追踪名人/投资人实时观点/采访/发表的意见等（Elon Mask等）
└── 板块/概念联动分析

Phase 2（3-4个月）：深度分析
├── 市场情绪分析
├── 历史回测框架（策略验证）（历史总是惊人的相似，虽不同但押韵）
├── 基金持仓分析（重仓股/持仓变化）
├── 模拟投资交易（AI通过真实数据，模拟买入卖出，计算实时/每天投资组合收益）
└── 自选股组合管理

Phase 3（持续迭代）：智能化提升
├── RAG知识库（研报/新闻/财报/名人投资哲学理论/历史事件/市场情绪/资金流向等）
├── 情绪分析（新闻情感/市场热度）
└── 多因子打分模型
```

## 0.3 技术硬约束（AI编码时必须遵守）

```python
# CLAUDE.md 核心约束 — 每次AI coding session必须读取

HARD_CONSTRAINTS = {
    # 基础设施约束
    "server_ram":        "2-4GB",             # VPS内存上限
    "frontend":          "Lovable (React)",    # 不能引入复杂构建工具
    "db_primary":        "SQLite (WAL模式)",   # 任务状态/历史记录
    "db_analytics":      "DuckDB (嵌入式)",    # 行情时序查询（替代Parquet手动管理）
    "vector_db":         "ChromaDB embedded",  # 无需独立进程
    "workers":           1,                    # SQLite WAL下只能单worker

    # 数据约束
    "primary_data_source":   "AKShare",        # 免费，覆盖全面，无需token
    "secondary_data_source": "Tushare free",   # 财务数据补充
    "ticker_format":         "ts_code",        # 000001.SZ / 600000.SH

    # 异步约束
    "io_rule": "全程async，禁止在async context中调用sync I/O",
    "akshare_rule": "AKShare是同步库，必须用run_in_executor包装",

    # LLM约束
    "default_llm":     "DeepSeek-chat",        # 低成本，中文优秀
    "llm_interface":   "LLMAdapter",           # 必须通过适配器，禁止直接调用
    "max_context_tokens": 8000,

    # 命名约束（关键！）
    "color_system": "A股红涨绿跌，与美股相反",
    "price_unit":   "Decimal，禁止float（金融计算精度要求）",
    "amount_display": "万元/亿元，不用元",
}
```

---

# Part I — A股领域建模：市场特有概念精确建模

> **这是原文档最大的盲点。** 照搬通用金融模型在A股会产生严重错误——涨跌停、T+1、ST机制等都需要特殊处理。AI生成的代码如果没有这些约束，会产生错误的分析结论。

## 1.1 股票标识符：`TsCode`（强类型，替代裸`str`）

```python
# domain/stock.py

from dataclasses import dataclass
import re

@dataclass(frozen=True)
class TsCode:
    """
    Tushare标准股票代码（强类型封装）。

    格式：{6位数字}.{交易所后缀}
      000001.SZ  — 平安银行（深交所主板）
      600000.SH  — 浦发银行（上交所主板）
      300750.SZ  — 宁德时代（创业板）
      688001.SH  — 华兴源创（科创板）
      430047.BJ  — 诺思兰德（北交所）
      510300.SH  — 沪深300ETF（上交所ETF）
      001234.OF  — 场外基金

    为什么用TsCode而不是裸str：
    - 在编译期/运行期阻断格式错误
    - 避免"000001"和"000001.SZ"混用导致的Bug
    - 携带市场类型信息，无需额外查表
    """
    code: str

    def __post_init__(self):
        pattern = r'^\d{6}\.(SZ|SH|BJ|OF)$'
        if not re.match(pattern, self.code):
            raise ValueError(
                f"无效TsCode格式: '{self.code}'。"
                f"正确格式示例: '000001.SZ'"
            )

    @property
    def exchange(self) -> str:
        """交易所代码：SH/SZ/BJ/OF"""
        return self.code.split('.')[1]

    @property
    def numeric_code(self) -> str:
        """6位数字代码"""
        return self.code.split('.')[0]

    @property
    def market_type(self) -> str:
        """
        市场类型判断。
        注意：这是启发式判断，极少数边界情况可能需要补充数据库校验。
        """
        num = self.numeric_code
        exch = self.exchange
        if exch == 'SH' and num.startswith('688'):
            return 'STAR_MARKET'      # 科创板
        if exch == 'SH' and num.startswith('6'):
            return 'SSE_MAIN'         # 上交所主板
        if exch == 'SZ' and num.startswith('300'):
            return 'CHI_NEXT'         # 创业板
        if exch == 'SZ' and (num.startswith('0') or num.startswith('2')):
            return 'SZSE_MAIN'        # 深交所主板
        if exch == 'BJ':
            return 'BSE'              # 北交所
        if exch == 'OF':
            return 'FUND_OTC'         # 场外基金
        return 'UNKNOWN'

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"TsCode('{self.code}')"
```

## 1.2 A股价格限制机制（`PriceLimitRule`）

```python
# domain/price_limit.py

from decimal import Decimal
from enum import Enum

class PriceLimitType(str, Enum):
    """A股涨跌停类型"""
    NORMAL        = "normal"        # 普通股票 ±10%
    ST            = "st"            # ST股票 ±5%
    STAR_MARKET   = "star_market"   # 科创板 ±20%
    CHI_NEXT      = "chi_next"      # 创业板注册制 ±20%
    NEW_IPO_5D    = "new_ipo_5d"    # 新股上市前5日：无涨跌停（IPO新规）


class PriceLimitRule:
    """
    A股涨跌停规则。

    这是A股独有的市场机制，影响：
    1. 每日最大价格波动区间
    2. 回测中是否触发流动性不足（无法成交）
    3. 分析时是否处于连续涨/跌停状态（重要的技术信号）
    """

    def __init__(
        self,
        limit_type: PriceLimitType,
        up_pct: Decimal,
        down_pct: Decimal,
    ):
        self.limit_type = limit_type
        self.up_pct = up_pct          # 如 Decimal('10') 表示 +10%
        self.down_pct = down_pct      # 如 Decimal('10') 表示 -10%

    @classmethod
    def for_stock(cls, ts_code: TsCode, is_st: bool = False) -> "PriceLimitRule":
        """根据股票所属市场和ST状态返回对应规则"""
        if is_st:
            return cls(PriceLimitType.ST, Decimal('5'), Decimal('5'))
        if ts_code.market_type in ('STAR_MARKET', 'CHI_NEXT'):
            return cls(PriceLimitType.STAR_MARKET, Decimal('20'), Decimal('20'))
        return cls(PriceLimitType.NORMAL, Decimal('10'), Decimal('10'))

    def calc_up_limit_price(self, prev_close: Decimal) -> Decimal:
        """计算涨停价（精确到分）"""
        raw = prev_close * (1 + self.up_pct / 100)
        return raw.quantize(Decimal('0.01'))

    def calc_down_limit_price(self, prev_close: Decimal) -> Decimal:
        """计算跌停价"""
        raw = prev_close * (1 - self.down_pct / 100)
        return raw.quantize(Decimal('0.01'))

    def is_limit_up(self, price: Decimal, prev_close: Decimal) -> bool:
        return price >= self.calc_up_limit_price(prev_close)

    def is_limit_down(self, price: Decimal, prev_close: Decimal) -> bool:
        return price <= self.calc_down_limit_price(prev_close)
```

## 1.3 核心领域枚举

```python
# domain/enums.py

from enum import Enum

class StockStatus(str, Enum):
    """股票当前状态"""
    NORMAL    = "normal"     # 正常交易
    ST        = "st"         # 特别处理（ST）
    STAR_ST   = "star_st"    # 退市风险警示（*ST）
    SUSPENDED = "suspended"  # 停牌
    DELISTED  = "delisted"   # 已退市

class AnalysisDepth(str, Enum):
    """分析深度（决定调用工具数量和LLM token消耗）"""
    QUICK    = "quick"     # 快速：行情+均线，目标≤15s
    STANDARD = "standard"  # 标准：+MACD+RSI+资金流，目标≤45s
    DEEP     = "deep"      # 深度：+基本面+北向+RAG，目标≤120s

class SignalDirection(str, Enum):
    """
    技术/基本面信号方向。
    使用研究性语言（看多/看空），不用强决策性语言（买入/卖出）。
    """
    HIGHLY_BULLISH = "highly_bullish"  # 强烈看多
    BULLISH        = "bullish"          # 偏多
    NEUTRAL        = "neutral"          # 中性
    BEARISH        = "bearish"          # 偏空
    HIGHLY_BEARISH = "highly_bearish"  # 强烈看空

class TechnicalSignal(str, Enum):
    """技术分析信号（A股常用）"""
    MA_GOLDEN_CROSS    = "ma_golden_cross"   # 均线金叉
    MA_DEATH_CROSS     = "ma_death_cross"    # 均线死叉
    MACD_GOLDEN_CROSS  = "macd_golden_cross" # MACD金叉
    MACD_DEATH_CROSS   = "macd_death_cross"  # MACD死叉
    VOLUME_BREAKOUT    = "volume_breakout"   # 放量突破
    HIGH_VOLUME_LIMIT  = "high_volume_limit" # 涨停（高关注度）
    CONSECUTIVE_LIMITS = "consecutive_limits"# 连板（游资/情绪关注）
    RSI_OVERBOUGHT     = "rsi_overbought"    # RSI超买（>80）
    RSI_OVERSOLD       = "rsi_oversold"      # RSI超卖（<20）
    BOLL_UPPER_TOUCH   = "boll_upper_touch"  # 触碰布林上轨
    BOLL_LOWER_TOUCH   = "boll_lower_touch"  # 触碰布林下轨

class FundamentalQuality(str, Enum):
    """基本面质量评级（AI分析输出）"""
    EXCELLENT = "excellent"  # 优
    GOOD      = "good"       # 良
    AVERAGE   = "average"    # 中
    POOR      = "poor"       # 差
    PENDING   = "pending"    # 待评估（数据不足）
```

## 1.4 核心数据模型

```python
# domain/models.py

from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from datetime import date, datetime
from typing import List

class CnDailyQuote(BaseModel):
    """
    A股日线行情数据。

    字段命名遵循Tushare标准，便于与数据源直接对接。
    金额类字段统一用Decimal，避免浮点精度问题。
    """
    ts_code:          str
    trade_date:       date
    open_price:       Decimal      # 开盘价
    high_price:       Decimal      # 最高价
    low_price:        Decimal      # 最低价
    close_price:      Decimal      # 收盘价
    pre_close:        Decimal      # 昨收价（计算涨跌幅的基准）
    change_amount:    Decimal      # 涨跌额
    pct_change:       Decimal      # 涨跌幅(%)
    volume:           int          # 成交量（手，1手=100股）
    turnover_amount:  Decimal      # 成交额（元）
    turnover_rate:    Decimal | None = None  # 换手率(%)
    volume_ratio:     Decimal | None = None  # 量比
    is_limit_up:      bool = False
    is_limit_down:    bool = False

    @property
    def turnover_amount_wan(self) -> Decimal:
        """成交额（万元）"""
        return (self.turnover_amount / 10000).quantize(Decimal('0.01'))

    @property
    def turnover_amount_yi(self) -> Decimal:
        """成交额（亿元）"""
        return (self.turnover_amount / 100_000_000).quantize(Decimal('0.0001'))


class TechnicalIndicators(BaseModel):
    """技术指标计算结果"""
    ts_code:    str
    calc_date:  date

    # 均线（A股主流周期：5/10/20/60/120/250）
    ma5:   Decimal | None = None
    ma10:  Decimal | None = None
    ma20:  Decimal | None = None   # 月线，重要支撑/压力位
    ma60:  Decimal | None = None   # 季线
    ma120: Decimal | None = None   # 半年线
    ma250: Decimal | None = None   # 年线

    # MACD（EMA12/EMA26/Signal9）
    macd_dif: Decimal | None = None   # 快线
    macd_dea: Decimal | None = None   # 慢线
    macd_bar: Decimal | None = None   # 柱状（BAR = 2*(DIF-DEA)）

    # RSI（6/12/24日）
    rsi6:  Decimal | None = None
    rsi12: Decimal | None = None
    rsi24: Decimal | None = None

    # KDJ（9,3,3）
    kdj_k: Decimal | None = None
    kdj_d: Decimal | None = None
    kdj_j: Decimal | None = None

    # 布林带（20,2）
    boll_upper:     Decimal | None = None
    boll_mid:       Decimal | None = None
    boll_lower:     Decimal | None = None
    boll_bandwidth: Decimal | None = None  # 带宽（上下轨距离/中轨）

    # 信号列表
    signals: List[TechnicalSignal] = []


class StockResearchRequest(BaseModel):
    """
    股票研究请求。

    改进说明：
    - 原文档 query: str 太模糊，改为结构化字段
    - 添加 analysis_depth 控制工具调用范围
    - 添加各维度开关，节省API调用
    """
    ts_code:             str
    analysis_depth:      AnalysisDepth = AnalysisDepth.STANDARD
    trade_date:          date | None = None    # None=最新，否则分析指定日期

    # 分析维度开关（Phase 0只开前两个）
    include_technical:   bool = True
    include_fundamental: bool = True
    include_capital_flow: bool = False         # Phase 1启用
    include_northbound:  bool = False          # Phase 1启用
    include_rag:         bool = False          # Phase 2启用（需向量库）

    user_context: str = ""  # 用户补充的分析背景，注入LLM提示词

    @field_validator('ts_code')
    @classmethod
    def validate_ts_code(cls, v: str) -> str:
        TsCode(v)  # 触发格式校验
        return v


class StockResearchReport(BaseModel):
    """
    股票研究报告（AI生成输出）。

    命名改进对照：
      decision            → 删除（研究工具不应有"决策"字段）
      confidence          → model_certainty（AI自身把握度，非价格预测置信度）
      risk_warnings: list → risk_disclaimer: str（通用声明）
    """
    report_id:       str
    ts_code:         str
    report_date:     date
    generated_at:    datetime

    # 核心输出
    analysis_summary:      str                   # AI综合分析文本（主要展示内容）
    technical_outlook:     SignalDirection | None = None
    fundamental_quality:   FundamentalQuality | None = None
    capital_flow_signal:   SignalDirection | None = None

    # A股特有警示
    is_st_warning:         bool = False          # ST股提示
    is_limit_up_detected:  bool = False          # 涨停检测
    is_limit_down_detected: bool = False         # 跌停检测

    # 模型元数据
    model_certainty: float = Field(default=0.5, ge=0.0, le=1.0)
    # 含义：0.5=AI对本次分析的把握度适中，数据充分时接近1.0
    llm_provider:    str = ""
    llm_model:       str = ""
    data_sources:    List[str] = []

    # 风险声明（必填）
    risk_disclaimer: str = "本报告由AI辅助生成，仅供个人研究参考。"
```

---

# Part II — 数据架构：数据源选型 · 缓存策略 · 韧性设计

> **原文档完全缺失数据层设计。** A股数据获取是最脆弱的环节——免费API有频率限制、数据质量参差不齐、节假日停市等边界情况繁多，必须有明确的韧性设计。

## 2.1 数据源分层策略

```
┌─────────────────────────────────────────────────────────────────┐
│  层级1：免费实时数据（优先使用）                                      │
│  AKShare ─── 主力数据源                                            │
│    · 完全免费，无需token                                            │
│    · 覆盖：日线/分钟线/资金流/北向/基本面/财报                         │
│    · 限制：同步库（需executor包装），约1req/秒频率上限                  │
├─────────────────────────────────────────────────────────────────┤
│  层级2：专业免费数据（补充财务数据）                                    │
│  Tushare 免费积分 ─── 财务报表/基本信息                               │
│    · 免费积分有限，优先用于历史财务数据                                  │
│    · 不依赖Tushare做行情（AKShare覆盖更好）                            │
├─────────────────────────────────────────────────────────────────┤
│  层级3：本地缓存（节省API调用，提升响应速度）                             │
│  DuckDB ─── 行情时序数据（日线/分钟线）                                │
│    · 列存储，时间范围查询极快                                           │
│    · 嵌入式，无需独立进程                                              │
│  SQLite ─── 元数据 + 任务状态 + 分析历史                              │
│    · 股票基本信息/交易日历/研究报告                                     │
└─────────────────────────────────────────────────────────────────┘
```

## 2.2 Circuit Breaker（熔断器）

A股免费API频繁出现限速或临时故障，熔断器防止级联失败：

```python
# market_data/circuit_breaker.py

import time
import logging
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class BreakerState(str, Enum):
    CLOSED    = "closed"     # 正常，请求直通
    OPEN      = "open"       # 熔断，快速失败
    HALF_OPEN = "half_open"  # 试探恢复


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int   = 5     # 连续失败N次后熔断
    recovery_timeout:  float = 60.0  # 熔断后等待N秒试探
    half_open_max:     int   = 2     # 半开状态最多测试N次


class CircuitBreaker:
    """
    熔断器：防止外部数据源故障导致系统雪崩。

    状态机：CLOSED → (N次失败) → OPEN → (超时) → HALF_OPEN → (成功) → CLOSED
                                                              → (失败) → OPEN
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self._cfg = config or CircuitBreakerConfig()
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_ts: float = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> BreakerState:
        if self._state == BreakerState.OPEN:
            if time.time() - self._last_failure_ts >= self._cfg.recovery_timeout:
                self._state = BreakerState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def can_attempt(self) -> bool:
        s = self.state
        if s == BreakerState.CLOSED:
            return True
        if s == BreakerState.HALF_OPEN:
            return self._half_open_calls < self._cfg.half_open_max
        return False  # OPEN：快速失败

    def record_success(self):
        self._failure_count = 0
        self._state = BreakerState.CLOSED
        logger.debug(f"[CircuitBreaker:{self.name}] Success → CLOSED")

    def record_failure(self, error: Exception):
        self._failure_count += 1
        self._last_failure_ts = time.time()
        if self._failure_count >= self._cfg.failure_threshold:
            self._state = BreakerState.OPEN
            logger.warning(
                f"[CircuitBreaker:{self.name}] OPEN after {self._failure_count} failures. "
                f"Last error: {error}"
            )
```

## 2.3 数据网关接口（含降级设计）

```python
# market_data/interfaces.py

from abc import ABC, abstractmethod
from datetime import date
from typing import List

class MarketDataGateway(ABC):
    """
    市场数据网关接口。

    所有数据获取必须通过此接口，不得在业务层直接调用AKShare/Tushare。
    原因：方便Mock测试、支持数据源切换、统一熔断降级。
    """

    @abstractmethod
    async def get_daily_quotes(
        self,
        ts_code: str,
        start_date: date,
        end_date: date,
    ) -> List[CnDailyQuote]:
        """
        获取日线行情。
        LSP契约：
        - 成功：返回列表（可为空[]，无数据时返回[]而非None）
        - 异常时：返回[]并记录日志，不向上传播（通过熔断器处理）
        - 数据按trade_date升序排列
        """
        ...

    @abstractmethod
    async def get_latest_quote(self, ts_code: str) -> CnDailyQuote | None:
        """获取最新行情（盘中实时/收盘价均可）"""
        ...

    @abstractmethod
    async def get_fundamentals(
        self,
        ts_code: str,
        period: str | None = None,  # None=最新，"20241231"=指定报告期
    ) -> "CnFundamentals | None":
        ...

    @abstractmethod
    async def get_capital_flow(
        self,
        ts_code: str,
        trade_date: date,
    ) -> "CnCapitalFlow | None":
        ...

    @abstractmethod
    async def search_stocks(self, keyword: str) -> List[dict]:
        """按股票名称或代码关键词搜索"""
        ...


class FallbackGateway(MarketDataGateway):
    """
    带自动降级的数据网关。
    主数据源失败时自动切换到备用数据源。
    """

    def __init__(self, primary: MarketDataGateway, fallback: MarketDataGateway):
        self._primary = primary
        self._fallback = fallback

    async def get_daily_quotes(self, ts_code, start_date, end_date):
        result = await self._primary.get_daily_quotes(ts_code, start_date, end_date)
        if not result:
            logger.info(f"Primary empty for {ts_code}, trying fallback")
            result = await self._fallback.get_daily_quotes(ts_code, start_date, end_date)
        return result

    # ... 其他方法同理
```

## 2.4 AKShare适配器（核心实现）

```python
# market_data/akshare_gateway.py

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class AKShareGateway(MarketDataGateway):
    """
    AKShare数据网关。

    关键注意：
    1. AKShare全部是同步阻塞调用，必须放在asyncio.run_in_executor中
    2. 频率限制：大多数接口约0.5-1秒/请求，用Semaphore控制并发
    3. 列名是中文，解析时按AKShare文档硬编码列名
    """

    def __init__(
        self,
        db: "DatabaseConnection",
        circuit_breaker_config: CircuitBreakerConfig | None = None,
        max_concurrent: int = 2,   # 最大并发数（AKShare不支持高并发）
    ):
        self._db = db
        self._cb_quotes = CircuitBreaker("akshare_quotes", circuit_breaker_config)
        self._cb_fundamental = CircuitBreaker("akshare_fundamental", circuit_breaker_config)
        self._sem = asyncio.Semaphore(max_concurrent)

    async def get_daily_quotes(
        self,
        ts_code: str,
        start_date: date,
        end_date: date,
    ) -> List[CnDailyQuote]:
        if not self._cb_quotes.can_attempt():
            logger.warning(f"Circuit OPEN for quotes: {ts_code}")
            return []

        async with self._sem:
            try:
                import akshare as ak
                numeric = ts_code.split('.')[0]
                loop = asyncio.get_event_loop()

                df = await loop.run_in_executor(
                    None,
                    lambda: ak.stock_zh_a_hist(
                        symbol=numeric,
                        period="daily",
                        start_date=start_date.strftime("%Y%m%d"),
                        end_date=end_date.strftime("%Y%m%d"),
                        adjust="qfq",   # 前复权（除权除息调整）
                    )
                )

                quotes = self._parse_hist_df(df, ts_code)
                self._cb_quotes.record_success()
                return quotes

            except Exception as e:
                self._cb_quotes.record_failure(e)
                logger.error(f"AKShare get_daily_quotes failed [{ts_code}]: {e}")
                return []

    def _parse_hist_df(self, df, ts_code: str) -> List[CnDailyQuote]:
        """解析AKShare stock_zh_a_hist返回的DataFrame"""
        quotes = []
        for _, row in df.iterrows():
            try:
                pct = Decimal(str(row.get('涨跌幅', '0') or '0'))
                quotes.append(CnDailyQuote(
                    ts_code=ts_code,
                    trade_date=date.fromisoformat(str(row['日期'])),
                    open_price=Decimal(str(row['开盘'])),
                    high_price=Decimal(str(row['最高'])),
                    low_price=Decimal(str(row['最低'])),
                    close_price=Decimal(str(row['收盘'])),
                    pre_close=Decimal(str(row.get('昨收', row['收盘']))),
                    change_amount=Decimal(str(row.get('涨跌额', '0') or '0')),
                    pct_change=pct,
                    volume=int(row['成交量']),
                    turnover_amount=Decimal(str(row['成交额'])),
                    turnover_rate=(
                        Decimal(str(row['换手率']))
                        if '换手率' in row and row['换手率'] is not None
                        else None
                    ),
                    is_limit_up=pct >= Decimal('9.5'),
                    is_limit_down=pct <= Decimal('-9.5'),
                ))
            except Exception as e:
                logger.warning(f"Skip malformed row: {e}")
        return quotes

    async def get_latest_quote(self, ts_code: str) -> CnDailyQuote | None:
        """获取最新一条行情（取最近交易日）"""
        today = date.today()
        start = today - timedelta(days=10)  # 往前取10天确保覆盖节假日
        quotes = await self.get_daily_quotes(ts_code, start, today)
        return quotes[-1] if quotes else None

    async def search_stocks(self, keyword: str) -> List[dict]:
        """按名称或代码搜索股票"""
        # 使用本地股票列表（从SQLite缓存）
        rows = await self._db.fetchall(
            """
            SELECT ts_code, name, industry, market, status
            FROM stock_info
            WHERE name LIKE ? OR ts_code LIKE ?
            LIMIT 20
            """,
            (f"%{keyword}%", f"%{keyword}%"),
        )
        return [dict(r) for r in rows]
```

## 2.5 交易日历服务

```python
# market_data/trading_calendar.py

import asyncio
from datetime import date, timedelta
from typing import Set

class CnTradingCalendar:
    """
    中国A股交易日历。

    A股交易日历的复杂性：
    - 不是简单"排除周末"，春节/国庆等长假需要额外处理
    - 节假日调休会导致周六上班（该日为交易日）
    - 临时休市（极少见，如2020年疫情初期延迟开市）

    实现策略：从AKShare拉取官方交易日历并缓存在SQLite中
    """

    def __init__(self, db: "DatabaseConnection"):
        self._db = db
        self._cache: Set[date] = set()
        self._cached_years: Set[int] = set()

    async def is_trading_day(self, d: date) -> bool:
        await self._ensure_loaded(d.year)
        return d in self._cache

    async def get_prev_trading_day(self, d: date, n: int = 1) -> date:
        """获取d之前（不含d）的第n个交易日"""
        current = d - timedelta(days=1)
        found = 0
        while found < n:
            await self._ensure_loaded(current.year)
            if current in self._cache:
                found += 1
                if found == n:
                    break
            current -= timedelta(days=1)
        return current

    async def get_next_trading_day(self, d: date, n: int = 1) -> date:
        """获取d之后（不含d）的第n个交易日"""
        current = d + timedelta(days=1)
        found = 0
        while found < n:
            await self._ensure_loaded(current.year)
            if current in self._cache:
                found += 1
                if found == n:
                    break
            current += timedelta(days=1)
        return current

    async def _ensure_loaded(self, year: int):
        if year in self._cached_years:
            return
        rows = await self._db.fetchall(
            "SELECT trade_date FROM trading_calendar WHERE year = ? AND is_open = 1",
            (year,),
        )
        if rows:
            for row in rows:
                self._cache.add(date.fromisoformat(row['trade_date']))
            self._cached_years.add(year)
        else:
            await self._refresh_from_akshare(year)

    async def _refresh_from_akshare(self, year: int):
        import akshare as ak
        loop = asyncio.get_event_loop()
        try:
            df = await loop.run_in_executor(
                None,
                ak.tool_trade_date_hist_sina,
            )
            year_dates = [
                str(d) for d in df['trade_date'].tolist()
                if str(d).startswith(str(year))
            ]
            await self._db.execute_many(
                "INSERT OR IGNORE INTO trading_calendar(trade_date, year, is_open) VALUES(?,?,1)",
                [(d, year) for d in year_dates],
            )
            for d_str in year_dates:
                self._cache.add(date.fromisoformat(d_str))
            self._cached_years.add(year)
        except Exception as e:
            logger.error(f"Failed to refresh trading calendar for {year}: {e}")
```

## 2.6 数据库Schema（SQLite）

```sql
-- db/schema.sql
-- 设计原则：行情数据存DuckDB，元数据+状态+报告存SQLite

PRAGMA journal_mode = WAL;      -- 支持并发读
PRAGMA busy_timeout = 5000;     -- 写冲突等待5秒
PRAGMA foreign_keys = ON;

-- 股票基本信息（定期从AKShare同步）
CREATE TABLE IF NOT EXISTS stock_info (
    ts_code     TEXT PRIMARY KEY,       -- '000001.SZ'
    name        TEXT NOT NULL,          -- '平安银行'
    industry    TEXT,                   -- 行业
    area        TEXT,                   -- 地区
    market      TEXT,                   -- 'main'/'gem'/'star'/'bse'
    list_date   TEXT,                   -- 上市日期 '20121101'
    status      TEXT DEFAULT 'normal',  -- StockStatus枚举值
    updated_at  TEXT NOT NULL
);

-- 交易日历
CREATE TABLE IF NOT EXISTS trading_calendar (
    trade_date  TEXT PRIMARY KEY,       -- '2024-01-02'
    year        INTEGER NOT NULL,
    is_open     INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_calendar_year ON trading_calendar(year);

-- 研究任务（异步任务状态追踪）
CREATE TABLE IF NOT EXISTS research_tasks (
    task_id         TEXT PRIMARY KEY,   -- UUID
    ts_code         TEXT NOT NULL,
    analysis_depth  TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',  -- pending/running/completed/failed
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    completed_at    TEXT,
    error_message   TEXT,
    current_step    INTEGER DEFAULT 0,
    total_steps     INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tasks_ts_code ON research_tasks(ts_code);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON research_tasks(status);

-- 研究报告
CREATE TABLE IF NOT EXISTS research_reports (
    report_id           TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL,
    ts_code             TEXT NOT NULL,
    report_date         TEXT NOT NULL,
    analysis_summary    TEXT NOT NULL,
    technical_outlook   TEXT,
    fundamental_quality TEXT,
    capital_flow_signal TEXT,
    model_certainty     REAL DEFAULT 0.5,
    llm_provider        TEXT,
    llm_model           TEXT,
    is_st_warning       INTEGER DEFAULT 0,
    is_limit_up         INTEGER DEFAULT 0,
    risk_disclaimer     TEXT NOT NULL,
    data_sources        TEXT DEFAULT '[]',  -- JSON数组
    created_at          TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
);
CREATE INDEX IF NOT EXISTS idx_reports_ts_code ON research_reports(ts_code);
CREATE INDEX IF NOT EXISTS idx_reports_date   ON research_reports(report_date);

-- 自选股
CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL UNIQUE,
    added_at    TEXT NOT NULL,
    note        TEXT DEFAULT '',
    tags        TEXT DEFAULT '[]'  -- JSON数组
);

-- 分析缓存（短期内重复分析直接返回）
CREATE TABLE IF NOT EXISTS analysis_cache (
    cache_key   TEXT PRIMARY KEY,   -- ts_code + date + depth hash
    report_id   TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    FOREIGN KEY (report_id) REFERENCES research_reports(report_id)
);
```

---

# Part III — 系统架构：MVP技术选型与目录结构

## 3.1 整体架构

```
┌────────────────────────────────────────────────────────────────┐
│                  Lovable（前端，CDN托管）                         │
│   React + Tailwind + Shadcn/UI                                 │
│   StockSearchBar | CnStockQuoteCard | ResearchPanel            │
│   TechnicalIndicatorChart | WatchlistTable                     │
└───────────────────────┬────────────────────────────────────────┘
                        │ HTTPS REST + SSE
                        ▼
┌────────────────────────────────────────────────────────────────┐
│               小型VPS（2-4GB RAM）                               │
│               Nginx反向代理 + SSL（Let's Encrypt）               │
├────────────────────────────────────────────────────────────────┤
│   FastAPI Backend（workers=1，SQLite WAL约束）                   │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  API Routes      Agent            Services              │  │
│   │  /stocks     → ResearchAgent  → LLMService             │  │
│   │  /research   → ToolOrchestrate→ MarketDataGateway       │  │
│   │  /events(SSE)→ AgentEventBus  → TechnicalIndicatorSvc  │  │
│   └─────────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────┤
│   Data Layer                                                   │
│   SQLite(WAL)      DuckDB(embedded)      ChromaDB(embedded)   │
│   任务/报告/自选股   行情时序数据            研报/新闻向量(Phase2)  │
├────────────────────────────────────────────────────────────────┤
│   External APIs                                                │
│   AKShare(免费主力)  Tushare(free财务)   DeepSeek/Ollama(LLM)  │
└────────────────────────────────────────────────────────────────┘
```

## 3.2 后端目录结构

```
aiinvest-backend/
├── main.py                      # FastAPI入口：配置、注册路由、启动
├── pyproject.toml               # 工具统一配置
├── requirements.txt
├── .env.example
├── CLAUDE.md                    # AI编码上下文（每次session必读）
│
├── app/                         # FastAPI应用层
│   ├── config.py                # Settings（pydantic-settings）
│   ├── dependencies.py          # FastAPI DI（统一注入管理）
│   └── api/
│       ├── stocks.py            # GET /stocks/search, /stocks/{ts_code}
│       ├── research.py          # POST /research, GET /research/{id}
│       ├── events.py            # GET /events（SSE）
│       ├── watchlist.py         # CRUD /watchlist
│       └── health.py            # GET /health
│
├── domain/                      # 领域模型（纯Python，零框架依赖）
│   ├── stock.py                 # TsCode, CnDailyQuote, PriceLimitRule
│   ├── analysis.py              # StockResearchRequest, StockResearchReport
│   ├── indicators.py            # TechnicalIndicators
│   └── enums.py                 # StockStatus, AnalysisDepth, SignalDirection等
│
├── market_data/                 # 数据获取层
│   ├── interfaces.py            # MarketDataGateway ABC
│   ├── akshare_gateway.py       # AKShare实现（主力）
│   ├── tushare_gateway.py       # Tushare实现（财务补充）
│   ├── circuit_breaker.py       # 熔断器
│   ├── trading_calendar.py      # 交易日历服务
│   └── fallback_gateway.py      # 降级网关
│
├── agent/                       # LangGraph Agent层
│   ├── research_agent.py        # 主Agent（LangGraph图定义）
│   ├── state.py                 # CnStockResearchState
│   ├── nodes/
│   │   ├── data_collector.py    # 数据收集节点
│   │   ├── tech_analyzer.py     # 技术指标分析节点
│   │   ├── capital_analyzer.py  # 资金流向分析节点（Phase 1）
│   │   ├── synthesizer.py       # LLM综合分析节点
│   │   └── report_builder.py    # 报告构建节点
│   └── events.py                # AgentEventBus（SSE事件推送）
│
├── llm/                         # LLM适配层
│   ├── interfaces.py            # LLMAdapter Protocol
│   ├── adapters/
│   │   ├── deepseek.py          # DeepSeek（推荐：低成本，中文优秀）
│   │   ├── ollama.py            # Ollama本地（离线场景）
│   │   └── openai_compat.py     # OpenAI兼容接口通用适配
│   ├── factory.py               # LLMFactoryRegistry
│   └── prompts/
│       ├── cn_stock_analysis.py # A股综合分析主Prompt
│       ├── technical_summary.py # 技术面Prompt
│       └── fundamental_prompt.py# 基本面Prompt
│
├── services/                    # 业务服务层
│   ├── research_service.py      # 研究任务生命周期管理
│   ├── technical_service.py     # 技术指标计算
│   └── watchlist_service.py     # 自选股CRUD
│
├── db/                          # 数据持久层
│   ├── connection.py            # aiosqlite连接管理
│   ├── schema.sql               # 建表脚本
│   └── migrations/
│       └── 001_initial.sql
│
└── tests/
    ├── unit/
    │   ├── domain/              # 领域对象测试（无外部依赖）
    │   ├── market_data/         # 数据网关Mock测试
    │   └── agent/               # Agent节点测试
    ├── integration/             # 集成测试（需真实API，标记@slow）
    └── fixtures/
        ├── quotes/              # 典型A股行情数据（涨停/跌停/停牌等）
        └── fundamentals/        # 典型财务数据
```

---

# Part IV — SOLID原则在A股金融领域的具体落地

> 保留原文档的SOLID框架，全面替换为A股业务场景，并修正原文档中的若干问题。

## S — 单一职责原则

```python
# ❌ 违例：A股分析"上帝节点"（原文档executor.py的A股版）
class StockAnalysisNode:
    async def analyze(self, state: dict) -> dict:
        ts_code = state["ts_code"]
        # 职责1：获取行情数据
        df = ak.stock_zh_a_hist(symbol=ts_code.split('.')[0])
        # 职责2：计算技术指标
        df['ma20'] = df['收盘'].rolling(20).mean()
        # 职责3：判断涨跌停
        is_limit_up = float(df['涨跌幅'].iloc[-1]) >= 9.9
        # 职责4：构建LLM提示词
        prompt = f"分析{ts_code}，MA20={df['ma20'].iloc[-1]:.2f}..."
        # 职责5：调用LLM
        result = await self.llm.ainvoke([{"role": "user", "content": prompt}])
        # 职责6：写入数据库
        await self.db.execute("INSERT INTO research_reports VALUES ...")
        # 6个职责 → 测试困难，任何一处变化影响全局
        return {**state, "report": result}


# ✅ 正例：每个节点只有一个变化的理由

class DataCollectorNode:
    """职责：从数据网关获取原始行情和基本面，填充state的raw_data字段"""
    def __init__(self, gateway: MarketDataGateway):
        self._gw = gateway

    async def __call__(self, state: "CnStockResearchState") -> "CnStockResearchState":
        ts_code = state["ts_code"]
        end_date = state.get("analysis_date") or date.today()
        start_date = end_date - timedelta(days=365)
        quotes = await self._gw.get_daily_quotes(ts_code, start_date, end_date)
        return {**state, "raw_quotes": quotes}


class TechnicalAnalyzerNode:
    """职责：基于raw_quotes计算技术指标，不调用任何外部API"""
    def __init__(self, tech_svc: "TechnicalIndicatorService"):
        self._svc = tech_svc

    async def __call__(self, state: "CnStockResearchState") -> "CnStockResearchState":
        quotes = state.get("raw_quotes", [])
        if not quotes:
            return {**state, "tech_indicators": None, "tech_signals": []}
        indicators = self._svc.calculate(quotes)
        signals = self._svc.detect_signals(indicators, quotes)
        return {**state, "tech_indicators": indicators, "tech_signals": signals}


class SynthesizerNode:
    """职责：构建提示词并调用LLM，返回分析文本"""
    def __init__(self, llm: "LLMAdapter", prompt_builder: "CnStockPromptBuilder"):
        self._llm = llm
        self._pb = prompt_builder

    async def __call__(self, state: "CnStockResearchState") -> "CnStockResearchState":
        messages = self._pb.build(state)
        text = await self._llm.ainvoke(messages)
        return {**state, "analysis_text": text}


class ReportBuilderNode:
    """职责：从state组装最终StockResearchReport，不做任何分析计算"""
    def __call__(self, state: "CnStockResearchState") -> "CnStockResearchState":
        report = StockResearchReport(
            report_id=str(uuid4()),
            ts_code=state["ts_code"],
            report_date=state.get("analysis_date") or date.today(),
            generated_at=datetime.now(),
            analysis_summary=state["analysis_text"],
            technical_outlook=state.get("tech_outlook"),
            is_limit_up_detected=state.get("is_limit_up", False),
            is_st_warning=state.get("is_st", False),
            risk_disclaimer="本报告由AI辅助生成，仅供个人研究参考。",
        )
        return {**state, "final_report": report}
```

**SRP检查清单：**

| 模块 | 当前职责数 | 目标职责数 | 优先级 |
|------|---------|---------|--------|
| `DataCollectorNode` | 获取+解析+缓存 | 1（仅获取，解析在Gateway） | 🔴 高 |
| `SynthesizerNode` | 提示词+LLM调用 | 可接受（同一关注点） | 🟢 低 |
| `AKShareGateway` | 调用+解析+熔断 | 可接受（Gateway职责） | 🟢 低 |
| `app/api/research.py` | 路由+业务逻辑 | 1（路由层委托Service） | 🟡 中 |

---

## O — 开闭原则：在数据源层的应用

```python
# ❌ 违例：新增数据源需修改已有代码
class DataService:
    async def get_quotes(self, ts_code: str, source: str):
        if source == "akshare":
            return await self._akshare_fetch(ts_code)
        elif source == "tushare":
            return await self._tushare_fetch(ts_code)
        elif source == "wind":          # 新增时必须修改这里
            return await self._wind_fetch(ts_code)
        # 每次新增数据源，这个函数都要被触碰 → 违反OCP


# ✅ 正例：注册式数据源工厂，新增无需改已有代码

class MarketDataGatewayRegistry:
    """数据网关注册表（对修改关闭）"""
    _gateways: dict[str, MarketDataGateway] = {}

    @classmethod
    def register(cls, name: str, gateway: MarketDataGateway):
        """注册新数据源，不触碰任何已有代码"""
        cls._gateways[name] = gateway

    @classmethod
    def get(cls, name: str) -> MarketDataGateway:
        if name not in cls._gateways:
            raise ValueError(
                f"Unknown data source: '{name}'. "
                f"Registered: {list(cls._gateways.keys())}"
            )
        return cls._gateways[name]

    @classmethod
    def get_with_fallback(cls, primary: str, fallback: str) -> FallbackGateway:
        return FallbackGateway(cls.get(primary), cls.get(fallback))


# 各数据源实现（对扩展开放）
class AKShareGateway(MarketDataGateway):
    """主力数据源：AKShare（免费）"""
    # ... 已在Part II完整实现

class TushareGateway(MarketDataGateway):
    """补充数据源：Tushare（财务数据）"""
    def __init__(self, token: str):
        import tushare as ts
        ts.set_token(token)
        self._pro = ts.pro_api()
    # ...

# 启动时注册（main.py）
MarketDataGatewayRegistry.register("akshare", AKShareGateway(db=db))
MarketDataGatewayRegistry.register("tushare", TushareGateway(token=settings.tushare_token))
# 未来新增Wind：只注册，不修改任何已有代码
# MarketDataGatewayRegistry.register("wind", WindGateway(...))


# OCP同样适用于LLM提供商（原文档已有，此处补充A股特化的工具注册）
class ResearchToolRegistry:
    """研究工具注册表（对修改关闭，对扩展开放）"""
    _tools: dict[str, "ResearchTool"] = {}

    @classmethod
    def register(cls, tool: "ResearchTool"):
        cls._tools[tool.name] = tool

    @classmethod
    def get_enabled_for_depth(cls, depth: AnalysisDepth) -> List["ResearchTool"]:
        """根据分析深度返回对应工具集"""
        return [t for t in cls._tools.values() if t.is_enabled_for(depth)]


def register_tool(registry: ResearchToolRegistry):
    """工具注册装饰器：新增工具只需新建文件+装饰器"""
    def decorator(cls):
        registry.register(cls())
        return cls
    return decorator


@register_tool(tool_registry)
class CnCapitalFlowTool:
    """A股资金流向工具（Phase 1引入）"""
    name = "cn_capital_flow"
    enabled_depths = [AnalysisDepth.STANDARD, AnalysisDepth.DEEP]

    def is_enabled_for(self, depth: AnalysisDepth) -> bool:
        return depth in self.enabled_depths

    async def execute(self, ts_code: str, trade_date: date) -> ToolResult:
        ...


@register_tool(tool_registry)
class NorthboundFlowTool:
    """北向资金工具（Phase 1引入）"""
    name = "northbound_flow"
    enabled_depths = [AnalysisDepth.DEEP]

    def is_enabled_for(self, depth: AnalysisDepth) -> bool:
        return depth in self.enabled_depths
    # ...
```

---

## L — 里氏替换原则

```python
# LLM适配器的LSP实现（原文档良好，补充数据网关契约）

class LLMAdapter(ABC):
    @abstractmethod
    async def ainvoke(self, messages: list[dict]) -> str:
        """
        LSP契约：
        - 必须返回非空字符串
        - 任何错误（网络/超时/API限流）统一抛出 LLMServiceError
        - 不修改输入messages
        - 超时必须在config.llm_timeout_seconds内响应
        """
        ...

# ❌ LSP违例：改变契约
class BrokenDeepSeekAdapter(LLMAdapter):
    async def ainvoke(self, messages: list[dict]) -> str:
        resp = await self._client.chat(messages)
        return resp.content   # 可能是None或空字符串 → 违反"非空"契约

# ✅ 正确实现：统一所有异常为LLMServiceError
class DeepSeekAdapter(LLMAdapter):
    def __init__(self, api_key: str, model: str = "deepseek-chat", timeout: float = 60.0):
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )
        self._model = model
        self._timeout = timeout

    async def ainvoke(self, messages: list[dict]) -> str:
        try:
            resp = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                ),
                timeout=self._timeout,
            )
            content = resp.choices[0].message.content
            if not content:
                raise LLMServiceError("DeepSeek returned empty response")
            return content
        except asyncio.TimeoutError:
            raise LLMServiceError(f"DeepSeek timeout after {self._timeout}s")
        except Exception as e:
            raise LLMServiceError(f"DeepSeek error: {e}") from e

    async def astream(self, messages: list[dict]):
        """流式输出（用于实时显示分析过程）"""
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                yield delta or ""  # 保证yield str，不yield None
        except Exception as e:
            raise LLMServiceError(f"DeepSeek stream error: {e}") from e


# LSP的测试验证套件
def verify_llm_adapter_lsp(adapter: LLMAdapter):
    """
    所有LLMAdapter实现必须通过此测试套件（pytest参数化）。
    确保任意适配器可无缝替换。
    """
    import pytest

    @pytest.mark.asyncio
    async def test_returns_non_empty_string():
        result = await adapter.ainvoke([{"role": "user", "content": "hello"}])
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_raises_llm_service_error_on_failure():
        with pytest.raises(LLMServiceError):
            await adapter.ainvoke([])  # 空消息触发错误
```

---

## I — 接口隔离原则

```python
# ❌ 违例：臃肿的数据网关接口（Phase 0的Agent被迫依赖未来功能）
class FullMarketDataGateway(ABC):
    async def get_daily_quotes(self, ...): ...     # Phase 0需要
    async def get_fundamentals(self, ...): ...    # Phase 1需要
    async def get_capital_flow(self, ...): ...    # Phase 1需要
    async def get_northbound(self, ...): ...      # Phase 1需要
    async def screen_stocks(self, ...): ...       # Phase 2需要
    async def get_announcements(self, ...): ...   # Phase 2需要
    # Phase 0 Agent被迫实现或依赖所有这些


# ✅ 正例：按使用角色和Phase拆分接口
from typing import Protocol, runtime_checkable

@runtime_checkable
class QuoteProvider(Protocol):
    """Phase 0基础分析需要"""
    async def get_daily_quotes(
        self, ts_code: str, start_date: date, end_date: date
    ) -> List[CnDailyQuote]: ...

    async def get_latest_quote(self, ts_code: str) -> CnDailyQuote | None: ...

    async def search_stocks(self, keyword: str) -> List[dict]: ...


@runtime_checkable
class FundamentalProvider(Protocol):
    """Phase 1深度分析需要"""
    async def get_fundamentals(
        self, ts_code: str, period: str | None = None
    ) -> "CnFundamentals | None": ...


@runtime_checkable
class CapitalFlowProvider(Protocol):
    """Phase 1资金分析需要"""
    async def get_capital_flow(
        self, ts_code: str, trade_date: date
    ) -> "CnCapitalFlow | None": ...

    async def get_northbound_flow(
        self, trade_date: date
    ) -> "NorthboundFlow | None": ...


# AKShareGateway实现全部接口（但Agent只注入它需要的）
class AKShareGateway(QuoteProvider, FundamentalProvider, CapitalFlowProvider):
    ...

# Phase 0 Agent只依赖QuoteProvider
class QuickStockAnalyzer:
    def __init__(
        self,
        quote_provider: QuoteProvider,   # 只知道行情接口
        llm: LLMAdapter,
    ):
        self._quotes = quote_provider
        self._llm = llm
    # 对CapitalFlowProvider一无所知，保持纯粹

# Phase 1 Agent增加资金流依赖
class StandardStockAnalyzer:
    def __init__(
        self,
        quote_provider: QuoteProvider,
        capital_provider: CapitalFlowProvider,  # 按需注入
        llm: LLMAdapter,
    ):
        ...
```

---

## D — 依赖倒置原则

```python
# app/dependencies.py — 统一依赖注入管理

from functools import lru_cache
from fastapi import Depends

@lru_cache
def get_settings() -> Settings:
    return Settings()

@lru_cache
def get_trading_calendar(
    db=Depends(get_db_connection)
) -> CnTradingCalendar:
    return CnTradingCalendar(db)

@lru_cache
def get_market_data_gateway(
    settings: Settings = Depends(get_settings),
) -> MarketDataGateway:
    akshare_gw = AKShareGateway(db=get_db_connection())
    # 若有Tushare token则配置降级
    if settings.tushare_token:
        tushare_gw = TushareGateway(settings.tushare_token)
        return FallbackGateway(akshare_gw, tushare_gw)
    return akshare_gw

@lru_cache
def get_llm_adapter(settings: Settings = Depends(get_settings)) -> LLMAdapter:
    config = LLMConfig(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
    )
    return LLMFactoryRegistry.create(config)

# API路由只依赖抽象，不知道具体实现细节
@router.post("/api/v1/research")
async def trigger_research(
    request: StockResearchRequest,
    background_tasks: BackgroundTasks,
    gateway: MarketDataGateway = Depends(get_market_data_gateway),  # 抽象接口
    llm: LLMAdapter = Depends(get_llm_adapter),                      # 抽象接口
    calendar: CnTradingCalendar = Depends(get_trading_calendar),
    db=Depends(get_db_connection),
):
    task_id = str(uuid4())
    background_tasks.add_task(
        run_research_in_background,
        task_id=task_id,
        request=request,
        gateway=gateway,
        llm=llm,
        calendar=calendar,
        db=db,
    )
    return {"task_id": task_id, "sse_url": f"/api/v1/events?task_id={task_id}"}


# DIP的核心收益：测试极其简单
# tests/unit/agent/test_synthesizer_node.py
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_llm():
    llm = AsyncMock(spec=LLMAdapter)
    llm.ainvoke.return_value = "技术面分析：该股20日均线支撑有效，MACD金叉形成..."
    return llm

@pytest.mark.asyncio
async def test_synthesizer_generates_report(mock_llm):
    """完全不需要真实LLM，测试秒级完成"""
    node = SynthesizerNode(llm=mock_llm, prompt_builder=CnStockPromptBuilder())
    state = {
        "ts_code": "000001.SZ",
        "raw_quotes": [mock_quote(pct=1.5)],
        "tech_indicators": mock_indicators(),
    }
    result = await node(state)

    assert "analysis_text" in result
    assert len(result["analysis_text"]) > 0
    mock_llm.ainvoke.assert_called_once()
```

---

# Part V — 设计模式目录

## 5.1 已使用的模式

### Pattern 1：Singleton — LLMConfigManager

```python
# llm/config_manager.py
import threading

class LLMConfigManager:
    """
    全局唯一的LLM配置管理器。
    确保运行期LLM配置变更能即时生效，无需重启服务。
    线程安全：双重检查锁（Python GIL下threading.Lock足够）。
    """
    _instance: "LLMConfigManager | None" = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._config: "LLMConfig | None" = None
        self._adapter: LLMAdapter | None = None
        self._initialized = True

    async def get_adapter(self) -> LLMAdapter:
        if self._adapter is None:
            await self._load_from_db()
        return self._adapter

    async def update_config(self, config: "LLMConfig"):
        self._config = config
        self._adapter = None  # 懒加载：下次get_adapter时重建
        await self._persist_to_db(config)

    @classmethod
    def reset_for_testing(cls):
        """测试用：重置Singleton，防止测试间状态污染"""
        cls._instance = None
```

### Pattern 2：Factory Method — LLM提供商

```python
# llm/factory.py

class LLMProviderFactory(ABC):
    @abstractmethod
    def create(self, config: "LLMConfig") -> LLMAdapter: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...


class LLMFactoryRegistry:
    _factories: dict[str, LLMProviderFactory] = {}

    @classmethod
    def register(cls, factory: LLMProviderFactory):
        cls._factories[factory.provider_name] = factory

    @classmethod
    def create(cls, config: "LLMConfig") -> LLMAdapter:
        factory = cls._factories.get(config.provider)
        if not factory:
            raise ValueError(
                f"未知LLM提供商: '{config.provider}'。"
                f"已注册: {list(cls._factories.keys())}"
            )
        return factory.create(config)


class DeepSeekFactory(LLMProviderFactory):
    """DeepSeek：推荐首选，中文能力强，成本低"""
    provider_name = "deepseek"

    def create(self, config: "LLMConfig") -> LLMAdapter:
        return DeepSeekAdapter(
            api_key=config.api_key,
            model=config.model or "deepseek-chat",
        )


class OllamaFactory(LLMProviderFactory):
    """Ollama：本地部署，零API成本，适合离线开发"""
    provider_name = "ollama"

    def create(self, config: "LLMConfig") -> LLMAdapter:
        from langchain_ollama import ChatOllama
        return LangChainLLMAdapter(
            ChatOllama(model=config.model, base_url=config.base_url)
        )


# 启动时注册
LLMFactoryRegistry.register(DeepSeekFactory())
LLMFactoryRegistry.register(OllamaFactory())
# 新增提供商：只需新建Factory类并注册，不修改已有任何代码
```

### Pattern 3：Strategy — 技术指标分析策略

```python
# services/technical_service.py

class TechnicalStrategy(Protocol):
    def analyze(self, quotes: List[CnDailyQuote]) -> dict: ...


class MaTrendStrategy:
    """均线趋势策略（A股最核心技术分析）"""

    def analyze(self, quotes: List[CnDailyQuote]) -> dict:
        prices = [float(q.close_price) for q in quotes]

        def ma(n):
            if len(prices) < n:
                return None
            return round(sum(prices[-n:]) / n, 3)

        ma5, ma10, ma20, ma60 = ma(5), ma(10), ma(20), ma(60)
        latest = prices[-1] if prices else None

        return {
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
            # 均线多头排列（short > mid > long，趋势向上的核心判断）
            "is_bull_ma_alignment": (
                latest and ma5 and ma10 and ma20
                and latest > ma5 > ma10 > ma20
            ),
            "is_above_ma20": bool(latest and ma20 and latest > ma20),
        }


class MacdStrategy:
    """MACD策略（判断趋势动能）"""

    def analyze(self, quotes: List[CnDailyQuote]) -> dict:
        prices = [float(q.close_price) for q in quotes]
        if len(prices) < 26:
            return {"macd_dif": None, "macd_dea": None, "macd_bar": None}

        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        dif = ema12 - ema26
        # DEA = 9日EMA(DIF)，简化为最近9个DIF的EMA
        dea = dif * 0.2 + dif * 0.8  # 简化版，实际需要历史DEA
        bar = 2 * (dif - dea)

        return {
            "macd_dif": round(dif, 4),
            "macd_dea": round(dea, 4),
            "macd_bar": round(bar, 4),
            "macd_golden_cross": dif > dea and dif > 0,
            "macd_death_cross": dif < dea and dif < 0,
        }

    @staticmethod
    def _ema(prices: list, n: int) -> float:
        k = 2 / (n + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = p * k + ema * (1 - k)
        return ema


class VolumeStrategy:
    """成交量分析策略（A股量价关系是核心）"""

    def analyze(self, quotes: List[CnDailyQuote]) -> dict:
        volumes = [q.volume for q in quotes]
        if len(volumes) < 6:
            return {"volume_ratio": None}

        avg5 = sum(volumes[-6:-1]) / 5
        current = volumes[-1]
        ratio = round(current / avg5, 2) if avg5 > 0 else 1.0

        return {
            "volume_ratio": ratio,
            "is_high_volume": ratio > 2.0,    # 量比>2：放量，关注
            "is_shrink_volume": ratio < 0.5,  # 量比<0.5：缩量，谨慎
        }


class TechnicalIndicatorService:
    """组合多个策略，提供统一的技术分析入口"""

    def __init__(self, strategies: List[TechnicalStrategy]):
        self._strategies = strategies

    def calculate(self, quotes: List[CnDailyQuote]) -> dict:
        result = {}
        for strategy in self._strategies:
            result.update(strategy.analyze(quotes))
        return result

    def detect_signals(self, indicators: dict, quotes: List[CnDailyQuote]) -> List[TechnicalSignal]:
        signals = []
        if indicators.get("macd_golden_cross"):
            signals.append(TechnicalSignal.MACD_GOLDEN_CROSS)
        if indicators.get("macd_death_cross"):
            signals.append(TechnicalSignal.MACD_DEATH_CROSS)
        if indicators.get("is_high_volume") and indicators.get("is_bull_ma_alignment"):
            signals.append(TechnicalSignal.VOLUME_BREAKOUT)
        # 检测涨停
        if quotes and quotes[-1].is_limit_up:
            signals.append(TechnicalSignal.HIGH_VOLUME_LIMIT)
        return signals

    @classmethod
    def for_quick(cls) -> "TechnicalIndicatorService":
        return cls([MaTrendStrategy(), VolumeStrategy()])

    @classmethod
    def for_standard(cls) -> "TechnicalIndicatorService":
        return cls([MaTrendStrategy(), MacdStrategy(), VolumeStrategy()])
```

### Pattern 4：Observer — SSE进度推送

```python
# agent/events.py

import asyncio
from typing import Callable, Awaitable
from pydantic import BaseModel, Field

EventHandler = Callable[["AgentEvent"], Awaitable[None]]


class AgentEvent(BaseModel):
    event_type:  AgentEventType
    task_id:     str
    step_no:     int = 0
    total_steps: int = 0
    data:        dict = {}
    ts:          str = Field(default_factory=lambda: datetime.now().isoformat())

    def to_sse_line(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class AgentEventBus:
    """事件总线：解耦Agent执行逻辑与SSE推送"""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, task_id: str, handler: EventHandler):
        self._handlers.setdefault(task_id, []).append(handler)

    def unsubscribe(self, task_id: str, handler: EventHandler):
        handlers = self._handlers.get(task_id, [])
        if handler in handlers:
            handlers.remove(handler)
        if not handlers:
            self._handlers.pop(task_id, None)

    async def emit(self, event: AgentEvent):
        for handler in self._handlers.get(event.task_id, []):
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"EventBus handler error: {e}")


# SSE端点（app/api/events.py）
@router.get("/api/v1/events")
async def sse_stream(
    task_id: str,
    request: Request,
    bus: AgentEventBus = Depends(get_event_bus),
) -> StreamingResponse:
    """
    SSE进度推送端点。
    前端收到 analysis_ready 事件后，再调用 GET /research/{report_id} 取完整报告。
    """
    queue: asyncio.Queue[AgentEvent] = asyncio.Queue()

    async def on_event(event: AgentEvent):
        await queue.put(event)

    bus.subscribe(task_id, on_event)

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield event.to_sse_line()
                    if event.event_type == AgentEventType.ANALYSIS_READY:
                        break
                    if event.event_type == AgentEventType.ERROR:
                        break
                except asyncio.TimeoutError:
                    yield 'data: {"event_type":"heartbeat"}\n\n'
        finally:
            bus.unsubscribe(task_id, on_event)

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Pattern 5：Chain of Responsibility — 输出后处理管道

```python
# agent/output_pipeline.py

class OutputProcessor(ABC):
    def __init__(self):
        self._next: "OutputProcessor | None" = None

    def set_next(self, processor: "OutputProcessor") -> "OutputProcessor":
        self._next = processor
        return processor

    @abstractmethod
    async def process(self, report: StockResearchReport) -> StockResearchReport: ...

    async def _forward(self, report: StockResearchReport) -> StockResearchReport:
        return await self._next.process(report) if self._next else report


class StWarningProcessor(OutputProcessor):
    """检测ST股并在报告中添加警示"""
    def __init__(self, db: "DatabaseConnection"):
        super().__init__()
        self._db = db

    async def process(self, report: StockResearchReport) -> StockResearchReport:
        row = await self._db.fetchone(
            "SELECT status FROM stock_info WHERE ts_code = ?",
            (report.ts_code,),
        )
        if row and row['status'] in ('st', 'star_st'):
            report = report.model_copy(update={"is_st_warning": True})
        return await self._forward(report)


class DisclaimerEnforcer(OutputProcessor):
    """确保风险声明存在且符合规范"""
    async def process(self, report: StockResearchReport) -> StockResearchReport:
        if not report.risk_disclaimer:
            report = report.model_copy(
                update={"risk_disclaimer": "本报告由AI辅助生成，仅供个人研究参考。"}
            )
        return await self._forward(report)


class ModelCertaintyCalibrator(OutputProcessor):
    """校准model_certainty：数据越充分，certainty越高"""
    async def process(self, report: StockResearchReport) -> StockResearchReport:
        certainty = 0.5
        if report.technical_outlook:
            certainty += 0.15
        if report.fundamental_quality:
            certainty += 0.15
        if report.capital_flow_signal:
            certainty += 0.1
        certainty = min(certainty, 0.9)  # 上限0.9，保留不确定性
        report = report.model_copy(update={"model_certainty": certainty})
        return await self._forward(report)


def build_output_pipeline(db: "DatabaseConnection") -> OutputProcessor:
    """构建报告后处理链"""
    head = StWarningProcessor(db)
    head.set_next(DisclaimerEnforcer()) \
        .set_next(ModelCertaintyCalibrator())
    return head
```

## 5.2 建议引入的模式

### Pattern 6：Template Method — A股分析骨架

```python
# agent/base_analyzer.py

class BaseCnStockAnalyzer(ABC):
    """
    A股研究分析模板方法。
    固定骨架：验证 → 交易日检查 → 数据收集 → 技术分析 → [资金分析] → LLM综合 → 报告构建
    """

    async def analyze(self, state: "CnStockResearchState") -> "CnStockResearchState":
        state = await self._validate_input(state)
        state = await self._adjust_to_trading_day(state)
        state = await self._collect_market_data(state)
        state = await self._run_technical_analysis(state)   # 抽象，必须实现
        state = await self._run_capital_analysis(state)     # 钩子，可选覆盖
        state = await self._llm_synthesize(state)           # 抽象，必须实现
        state = await self._build_report(state)
        return state

    @abstractmethod
    async def _run_technical_analysis(self, state) -> "CnStockResearchState": ...

    @abstractmethod
    async def _llm_synthesize(self, state) -> "CnStockResearchState": ...

    # 默认空实现（子类按需覆盖）
    async def _run_capital_analysis(self, state) -> "CnStockResearchState":
        return state  # Phase 0：默认跳过资金分析

    async def _validate_input(self, state) -> "CnStockResearchState":
        TsCode(state["ts_code"])
        return state

    async def _adjust_to_trading_day(self, state) -> "CnStockResearchState":
        """非交易日自动调整到最近交易日"""
        d = state.get("analysis_date") or date.today()
        if not await self._calendar.is_trading_day(d):
            prev = await self._calendar.get_prev_trading_day(d)
            return {**state, "analysis_date": prev, "_adjusted_date": True}
        return state


class QuickCnStockAnalyzer(BaseCnStockAnalyzer):
    """快速分析：均线+量比+LLM简洁分析，≤15秒"""

    async def _run_technical_analysis(self, state):
        svc = TechnicalIndicatorService.for_quick()
        indicators = svc.calculate(state.get("raw_quotes", [])[-60:])
        return {**state, "tech_indicators": indicators}

    async def _llm_synthesize(self, state):
        prompt = self._pb.build_quick_prompt(state)
        text = await self._llm.ainvoke(prompt)
        return {**state, "analysis_text": text}


class StandardCnStockAnalyzer(BaseCnStockAnalyzer):
    """标准分析：+MACD+RSI+资金流+LLM详细分析，≤45秒"""

    async def _run_technical_analysis(self, state):
        svc = TechnicalIndicatorService.for_standard()
        indicators = svc.calculate(state.get("raw_quotes", [])[-250:])
        signals = svc.detect_signals(indicators, state.get("raw_quotes", []))
        return {**state, "tech_indicators": indicators, "tech_signals": signals}

    async def _run_capital_analysis(self, state):
        """标准分析开启资金流分析"""
        trade_date = state.get("analysis_date") or date.today()
        flow = await self._capital_gw.get_capital_flow(
            state["ts_code"], trade_date
        )
        return {**state, "capital_flow": flow}

    async def _llm_synthesize(self, state):
        prompt = self._pb.build_standard_prompt(state)
        text = await self._llm.ainvoke(prompt)
        return {**state, "analysis_text": text}
```

### Pattern 7：Command — 分析任务支持重放

```python
# services/research_command.py

@dataclass
class StockResearchCommand:
    """
    封装研究请求为可存储、可重放的命令对象。
    用途：历史分析回放、批量分析自选股、调参复现。
    """
    request:          StockResearchRequest
    task_id:          str = field(default_factory=lambda: str(uuid4()))
    created_at:       datetime = field(default_factory=datetime.now)
    result_report_id: str | None = None

    async def execute(self, research_svc: "ResearchService") -> str:
        report_id = await research_svc.run_sync(self.request)
        self.result_report_id = report_id
        return report_id

    def replay_with_latest_data(self) -> "StockResearchCommand":
        """用相同参数、最新数据重新分析"""
        new_req = self.request.model_copy(update={"trade_date": None})
        return StockResearchCommand(request=new_req)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "ts_code": self.request.ts_code,
            "analysis_depth": self.request.analysis_depth,
            "trade_date": (
                self.request.trade_date.isoformat()
                if self.request.trade_date else None
            ),
            "created_at": self.created_at.isoformat(),
            "result_report_id": self.result_report_id,
        }
```

---

# Part VI — 命名规范：领域驱动 + Python/TypeScript双标准

## 6.1 原文档命名问题诊断与修正

| 原命名 | 问题 | 修正后 |
|--------|------|--------|
| `stock_code: str` | 格式不明确（"000001"？"000001.SZ"？） | `ts_code: str` + `TsCode`类型封装 |
| `confidence: float` | 混淆统计学置信度 | `model_certainty: float` |
| `decision` | 研究工具不应有"决策"字段 | 删除，改用`technical_outlook: SignalDirection` |
| `risk_warnings: List[str]` | 硬编码列表，AI重复生成无意义 | `risk_disclaimer: str`（通用声明）|
| `InvestmentResearchState` | 太长，过于通用 | `CnStockResearchState`（加前缀） |
| `rag_core/` | 目录名过技术化 | `agent/`（逻辑层） + `knowledge/`（RAG层） |
| `ResearchRequest` | 不够具体 | `StockResearchRequest` |
| `analysis_summary` | ✓ 保留 | `analysis_summary` |

## 6.2 Python命名规范

```python
# ============================================================
# 类命名：描述性名词，体现A股领域上下文
# ============================================================

# ✅ 推荐
class TsCode: ...                    # A股Tushare格式代码（有类型保证）
class CnDailyQuote: ...              # 中国市场日线行情
class CnTradingCalendar: ...         # 中国A股交易日历（加Cn避免歧义）
class StockResearchRequest: ...      # 股票研究请求（具体）
class StockResearchReport: ...       # 股票研究报告（不是Response）
class PriceLimitRule: ...            # 涨跌停规则
class AKShareGateway: ...            # AKShare数据网关
class TechnicalIndicatorService: ... # 技术指标服务
class CircuitBreaker: ...            # 熔断器（通用组件无需前缀）
class LLMAdapter: ...                # LLM适配器

# ❌ 避免
class StockCodeValidator: ...  # 验证逻辑内聚在TsCode，不单独成类
class DataFetcher: ...         # 太模糊
class AIAnalyzer: ...          # AI是手段，不是命名依据
class InvestmentManager: ...   # Manager易产生God Object


# ============================================================
# 函数/方法命名：动词+名词，意图自文档化
# ============================================================

# ✅ 推荐
async def get_daily_quotes(ts_code: str, ...) -> List[CnDailyQuote]: ...
async def trigger_stock_research(request: StockResearchRequest) -> str: ...
def calc_up_limit_price(prev_close: Decimal) -> Decimal: ...
def detect_ma_golden_cross(quotes: List[CnDailyQuote]) -> bool: ...
async def is_trading_day(d: date) -> bool: ...
def format_amount_as_wan(amount: Decimal) -> str: ...

# ❌ 避免
async def do_analysis(): ...   # do什么
async def process(): ...       # process什么
def check(ts_code): ...        # check什么


# ============================================================
# 变量命名：A股领域术语，语义自解释
# ============================================================

# ✅ 推荐
ts_code          = "000001.SZ"        # Tushare格式代码
pct_change       = Decimal("3.45")    # 涨跌幅(%)，不用pct/change
turnover_amount  = Decimal(...)       # 成交额（元）
main_net_inflow  = Decimal(...)       # 主力净流入
is_limit_up      = False             # 是否涨停（布尔前缀is_）
is_st_stock      = False             # 是否ST股
prev_close       = Decimal("10.50")  # 昨收价（不是last_close）
ma5, ma20, ma60  = ..., ..., ...     # 均线值直接带数字
macd_dif         = Decimal(...)      # MACD快线
volume_ratio     = Decimal("2.3")    # 量比

# ❌ 避免
code   = "000001.SZ"  # 太模糊
pct    = 3.45          # pct of what
flow   = ...           # 哪种flow
result = ...           # 仅可用于短暂临时变量


# ============================================================
# 常量：UPPER_SNAKE，含义注释
# ============================================================
NORMAL_LIMIT_PCT    = Decimal("10")   # 普通股涨跌停幅度
ST_LIMIT_PCT        = Decimal("5")    # ST股涨跌停幅度
STAR_MARKET_LIMIT   = Decimal("20")   # 科创板/创业板涨跌停幅度
HIGH_VOLUME_RATIO   = Decimal("2.0")  # 量比>2视为放量
MARKET_OPEN_TIME    = "09:30"         # 集合竞价结束，连续竞价开始
MARKET_CLOSE_TIME   = "15:00"         # 收盘
```

## 6.3 TypeScript/React命名规范

```typescript
// ============================================================
// 类型接口：与Python后端保持语义一致（驼峰转换）
// ============================================================

// Python ts_code → TypeScript tsCode
// Python pct_change → TypeScript pctChange
interface CnDailyQuote {
  tsCode:          string;
  tradeDate:       string;    // ISO date: "2024-01-15"
  openPrice:       number;
  highPrice:       number;
  lowPrice:        number;
  closePrice:      number;
  preClose:        number;
  pctChange:       number;    // 涨跌幅(%)
  volume:          number;    // 成交量（手）
  turnoverAmount:  number;    // 成交额（元）
  isLimitUp:       boolean;
  isLimitDown:     boolean;
}

interface StockResearchReport {
  reportId:          string;
  tsCode:            string;
  analysisSummary:   string;
  technicalOutlook:  'bullish' | 'bearish' | 'neutral' | 'highly_bullish' | 'highly_bearish' | null;
  fundamentalQuality:'excellent' | 'good' | 'average' | 'poor' | 'pending' | null;
  modelCertainty:    number;    // 0-1
  isStWarning:       boolean;
  isLimitUpDetected: boolean;
  riskDisclaimer:    string;
  llmProvider:       string;
  llmModel:          string;
  generatedAt:       string;
}

type AgentEventType =
  | 'task_started'   | 'step_started'    | 'step_completed'
  | 'quote_fetched'  | 'indicators_ready'| 'capital_analyzed'
  | 'analysis_ready' | 'limit_up_detected'| 'st_warning'
  | 'error'          | 'heartbeat';

interface AgentEvent {
  eventType:   AgentEventType;
  taskId:      string;
  stepNo:      number;
  totalSteps:  number;
  data:        Record<string, unknown>;
  ts:          string;
}


// ============================================================
// 组件命名：功能+名词，带上下文
// ============================================================

// ✅ 推荐
const StockSearchBar        = () => {};
const CnStockQuoteCard      = () => {};   // Cn前缀区分A股特有
const ResearchProgressBar   = () => {};
const TechnicalIndicatorPanel = () => {};
const CapitalFlowChart      = () => {};
const WatchlistTable        = () => {};
const AnalysisReportView    = () => {};

// ❌ 避免
const Card    = () => {};   // 太模糊
const Panel   = () => {};
const Chart   = () => {};


// ============================================================
// Hook命名
// ============================================================
const useStockResearch   = () => {};  // 触发分析+获取报告
const useSSEProgress     = () => {};  // 订阅SSE进度流
const useCnStockQuote    = () => {};  // 获取A股行情
const useWatchlist       = () => {};  // 自选股CRUD
const useTradingCalendar = () => {};  // 查询交易日


// ============================================================
// A股关键工具函数（lib/cn-stock-utils.ts）
// ============================================================

/** 成交额格式化（A股常用：万元/亿元） */
function formatTurnoverAmount(amountYuan: number): string {
  if (amountYuan >= 1e8) return `${(amountYuan / 1e8).toFixed(2)}亿`;
  if (amountYuan >= 1e4) return `${(amountYuan / 1e4).toFixed(2)}万`;
  return `${amountYuan}元`;
}

/** 涨跌幅格式化 */
function formatPctChange(pct: number): string {
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
}

/**
 * 涨跌幅颜色（A股惯例：红涨绿跌，与美股相反！）
 * CRITICAL：AI生成代码时必须使用此函数，勿直接写颜色逻辑
 */
function getPctChangeColor(pct: number): string {
  if (pct > 0) return 'text-red-500';     // 🔴 上涨 = 红色（A股规范）
  if (pct < 0) return 'text-green-500';   // 🟢 下跌 = 绿色（A股规范）
  return 'text-gray-400';
}

/** 判断是否接近涨停价 */
function isNearLimitUp(
  currentPrice: number,
  prevClose: number,
  limitPct: number = 10,
): boolean {
  const limitPrice = prevClose * (1 + limitPct / 100);
  return Math.abs(currentPrice - limitPrice) / limitPrice < 0.005; // 0.5%范围内
}

/** 量比文字描述 */
function describeVolumeRatio(ratio: number): string {
  if (ratio > 5)   return '超级放量';
  if (ratio > 3)   return '大幅放量';
  if (ratio > 2)   return '放量';
  if (ratio > 1.5) return '温和放量';
  if (ratio < 0.3) return '极度缩量';
  if (ratio < 0.5) return '缩量';
  return '量能正常';
}
```

---

# Part VII — Git最佳实践

## 7.1 分支策略（单人MVP简化版）

```
main     ──●────────────────────────────────●──── 稳定可部署版本
            │  tag: v0.1.0                  │  tag: v0.2.0
            │                              │
develop  ───┼────●──●──●──●──●────────────┼──── 集成/开发分支
            │    │               │         │
feature/x ──┘    └──feature/y────┘         │
                                           │
hotfix/x ─────────────────────────────────┘
```

**MVP说明**：个人项目不需要严格的GitFlow，但保留develop分支有助于AI coding工作流——始终在develop分支上让AI生成代码，review后合并到main。

## 7.2 分支命名

```bash
# 功能开发
git checkout -b feature/phase0-basic-research
git checkout -b feature/phase1-technical-indicators
git checkout -b feature/phase1-capital-flow
git checkout -b feature/phase2-backtest-framework

# Bug修复
git checkout -b fix/akshare-executor-not-awaited
git checkout -b fix/sse-disconnect-handler
git checkout -b fix/ts-code-validation-regex

# 重构
git checkout -b refactor/extract-data-gateway-layer
git checkout -b refactor/llm-adapter-abstraction

# 热修复
git checkout -b hotfix/circuit-breaker-state-reset

# 数据相关（新增）
git checkout -b data/trading-calendar-refresh
git checkout -b data/stock-info-sync

# 文档
git checkout -b docs/engineering-handbook-v2
```

## 7.3 Commit规范（Conventional Commits）

```
格式：<type>(<scope>): <subject>

type 枚举：
  feat      新功能
  fix       Bug修复
  refactor  重构（不改变外部行为）
  perf      性能优化
  test      测试相关
  docs      文档
  chore     构建/依赖/配置
  ci        CI/CD相关
  data      数据层相关（新增）

scope（本项目）：
  api          FastAPI路由层
  agent        LangGraph Agent
  market_data  数据获取层（含AKShare/Tushare适配）
  domain       领域模型
  llm          LLM适配层
  technical    技术指标计算
  calendar     交易日历
  circuit      熔断器
  db           数据库
  sse          SSE推送
  watchlist    自选股
  frontend     前端（通用）
```

### Commit示例

```bash
# ✅ 好的commit
git commit -m "feat(market_data): add AKShare daily quote gateway with circuit breaker"
git commit -m "feat(domain): add TsCode value object with format validation"
git commit -m "feat(technical): implement MACD/RSI/KDJ calculation for A-share analysis"
git commit -m "fix(akshare): wrap sync calls with run_in_executor to avoid blocking event loop"
git commit -m "fix(domain): correct limit-up threshold for STAR MARKET (10% → 20%)"
git commit -m "refactor(agent): split monolithic AnalysisNode into 4 single-responsibility nodes"
git commit -m "perf(calendar): cache trading calendar in memory after first DB load"
git commit -m "data(calendar): seed 2024-2025 A-share trading calendar from AKShare"
git commit -m "test(domain): add parametrized tests for PriceLimitRule across all market types"

# ❌ 禁止的commit
git commit -m "fix"
git commit -m "update code"
git commit -m "wip"
git commit -m "修改了一些东西"
```

### 多行Commit（重要变更）

```bash
git commit -m "feat(agent): implement LangGraph research agent with 4-node pipeline

Replaces monolithic StockAnalysisNode with composable node pipeline:
- DataCollectorNode: fetches quotes/fundamentals via MarketDataGateway
- TechnicalAnalyzerNode: calculates MA/MACD/RSI/Volume indicators
- SynthesizerNode: builds prompts and invokes LLM
- ReportBuilderNode: assembles final StockResearchReport

Key design decisions:
- Each node receives/returns immutable state dict (LangGraph convention)
- Nodes depend on abstractions (MarketDataGateway, LLMAdapter), not concretions
- Circuit breaker wraps all AKShare calls in DataCollectorNode

Breaking change: API response shape changed
  Before: {decision: ..., confidence: ...}
  After:  {analysis_summary: ..., model_certainty: ..., technical_outlook: ...}

Closes #7
Refs: ADR-003"
```

## 7.4 Tag策略（语义化版本）

```bash
# 里程碑Tag
v0.1.0   Phase 0完成：基础研究流程跑通
v0.2.0   Phase 1完成：技术指标+资金流
v0.3.0   Phase 2完成：回测框架
v1.0.0   生产就绪：稳定运行30天+

# 创建带注释Tag
git tag -a v0.1.0 -m "Phase 0 MVP Release

Features:
- A-share basic quote query via AKShare
- Single-stock AI research report (DeepSeek/Ollama)
- LLM provider switching at runtime
- SSE real-time progress streaming
- Analysis history with replay

Architecture:
- LangGraph 4-node pipeline
- Circuit breaker for AKShare
- SQLite WAL + DuckDB for data

Known limitations:
- Phase 1 technical indicators not yet included
- Single user only
- No fund analysis yet

Tested on: Python 3.12, Lovable frontend"

git push origin v0.1.0
```

## 7.5 .gitignore规范

```gitignore
# .gitignore — AIInvest

# Python
__pycache__/
*.py[cod]
.venv/
venv/
dist/
build/
*.egg-info/

# 数据文件（绝对不入库）
data/
*.db
*.sqlite
*.sqlite3
*.duckdb
chroma_db/

# 日志
logs/
*.log

# 环境配置（绝对不入库，提交.env.example）
.env
.env.local
.env.production

# LLM模型
.ollama/
models/
*.gguf
*.bin

# Node.js
node_modules/
dist/
.vite/
coverage/

# IDE
.vscode/settings.json
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# 测试
.coverage
htmlcov/
.pytest_cache/
```

## 7.6 Git Hooks（本地质量门禁）

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-yaml
      - id: check-merge-conflict
      - id: detect-private-key          # 防止AKShare/DeepSeek API Key入库
      - id: end-of-file-fixer

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

---

# Part VIII — AI辅助开发工作流

## 8.1 CLAUDE.md模板（项目级AI上下文）

```markdown
# AIInvest Backend — Claude上下文文件

## 项目概述
个人AI辅助A股/基金投资研究系统，用于分析股票、辅助投资决策。
单用户，VPS小型服务器（2-4GB RAM），个人MVP。

## 技术栈
- Backend：FastAPI (async) + LangGraph + aiosqlite + DuckDB
- Frontend：React (Lovable托管) + Tailwind + Shadcn/UI
- LLM：DeepSeek-chat（主）/ Ollama（本地备用）
- 数据源：AKShare（主） + Tushare免费积分（补充财务数据）

## 硬约束（违反会导致Bug）
1. AKShare是同步库，必须用 `asyncio.run_in_executor(None, ...)` 包装
2. SQLite WAL模式，`uvicorn workers=1`，不支持多进程写
3. 所有金额字段用 `Decimal`，禁用 `float`（精度问题）
4. 股票代码用 `TsCode` 类型，格式 "000001.SZ"，不是 "000001"
5. LLM调用必须通过 `LLMAdapter` 接口，禁止直接调用langchain
6. A股颜色：红色=上涨，绿色=下跌（与美股相反）

## 关键接口位置
- domain/stock.py：TsCode, CnDailyQuote, PriceLimitRule
- domain/analysis.py：StockResearchRequest, StockResearchReport
- market_data/interfaces.py：MarketDataGateway（数据网关抽象）
- llm/interfaces.py：LLMAdapter（LLM适配器抽象）
- app/dependencies.py：FastAPI依赖注入配置

## 命名规范（关键）
- 股票代码字段：ts_code（Tushare格式）
- 分析输出字段：analysis_summary（不是decision）
- AI把握度字段：model_certainty（不是confidence）
- 涨跌幅字段：pct_change（不是pct/change_pct）
- 成交额字段：turnover_amount（单位：元，显示时转万/亿）
- 昨收价字段：pre_close（不是last_close/yesterday_close）

## 当前Phase
Phase 0：基础研究框架
- [x] AKShare数据网关
- [x] Circuit Breaker
- [ ] LangGraph 4节点Agent
- [ ] DeepSeek LLM适配器
- [ ] SSE进度推送
- [ ] 基础前端（Lovable）
```

## 8.2 CONTEXT-TASK-CONSTRAINT-FORMAT框架

```markdown
# 通用代码提示模板（每次让AI写代码时使用）

## CONTEXT（上下文）
我在开发AIInvest（个人A股AI研究系统）。
当前文件：[文件路径]
该文件职责：[一句话描述]
相关接口/依赖：
```python
[粘贴关键代码片段，如ABC接口定义]
```

## TASK（任务）
实现 [具体功能]，需要：
1. [具体需求1]
2. [具体需求2]

## CONSTRAINT（约束）
- AKShare是同步库，必须用run_in_executor包装
- 金额用Decimal，不用float
- 股票代码格式：000001.SZ（Tushare格式）
- 遵循domain/下已定义的数据模型
- 异常处理：外部API失败返回空列表，不向上传播
- 代码风格：ruff + mypy strict

## FORMAT（输出格式）
1. 完整可运行代码（含import）
2. 关键决策的注释说明
3. 对应的pytest单元测试
4. 可能的边界情况说明（如停牌、ST股、节假日）
```

## 8.3 A股特定场景Prompt示例

```markdown
## 场景1：实现新的数据获取工具

CONTEXT:
market_data/akshare_gateway.py 中已有 get_daily_quotes，
现在需要在同文件中增加 get_capital_flow 方法。
AKShare对应接口是 ak.stock_individual_fund_flow。

TASK:
实现 get_capital_flow(ts_code: str, trade_date: date) -> CnCapitalFlow | None
- 返回指定交易日的主力资金流向数据
- 包含：main_net_inflow, super_large_net, large_net, medium_net, small_net

CONSTRAINT:
- AKShare同步库，必须用run_in_executor包装
- 失败时返回None（不抛异常），通过_cb_capital熔断器管理
- 使用已有的_rate_limit_semaphore控制并发
- AKShare列名是中文，需要正确映射
- CnCapitalFlow在 domain/models.py 中已定义

FORMAT:
1. 完整方法实现代码
2. 单元测试（Mock掉AKShare调用，不依赖真实网络）
3. 说明AKShare该接口的特殊限制（如只提供近N天数据）
```

```markdown
## 场景2：Debug A股特有错误

CONTEXT:
FastAPI + LangGraph，Python 3.12

错误日志：
```
ValueError: Invalid TsCode format: '000001'. Expected format: '000001.SZ'
```
发生在 POST /api/v1/research 接口

TASK:
定位并修复问题，前端传来的是6位纯数字代码 "000001"

CONSTRAINT:
- 不要修改TsCode的格式验证逻辑（这是正确的）
- 修复点应该在API入口层做格式转换
- 深交所股票（0/2/3开头）→ .SZ，上交所（6/9开头）→ .SH，北交所（4/8开头）→ .BJ

FORMAT:
1. 根因分析（1-2句话）
2. 修复代码（最小改动，在API层添加格式转换）
3. 防御性建议（如何防止同类问题）
```

## 8.4 AI辅助TDD（A股场景）

```python
# AI-TDD工作流示例：先让AI生成测试，再实现

# 步骤1：让AI生成测试
"""
提示词：
我要实现 PriceLimitRule.calc_up_limit_price()，
请先帮我写完整的pytest测试（不要写实现），覆盖：
- 普通股票涨停价（+10%）
- ST股涨停价（+5%）
- 科创板涨停价（+20%）
- 创业板涨停价（+20%）
- 精度验证（Decimal精确到0.01）
- 边界值：极低价格（0.01元）、极高价格（1000元）
"""

# AI生成的测试（验收标准）
class TestPriceLimitRule:

    @pytest.mark.parametrize("prev_close,expected_limit_up", [
        (Decimal("10.00"), Decimal("11.00")),  # 普通股 +10%
        (Decimal("10.01"), Decimal("11.01")),  # 精度测试
        (Decimal("100.00"), Decimal("110.00")),
        (Decimal("0.10"), Decimal("0.11")),    # 低价股
    ])
    def test_normal_stock_up_limit(self, prev_close, expected_limit_up):
        rule = PriceLimitRule.for_stock(TsCode("000001.SZ"), is_st=False)
        assert rule.calc_up_limit_price(prev_close) == expected_limit_up

    @pytest.mark.parametrize("prev_close,expected_limit_up", [
        (Decimal("10.00"), Decimal("10.50")),   # ST股 +5%
        (Decimal("20.00"), Decimal("21.00")),
    ])
    def test_st_stock_up_limit(self, prev_close, expected_limit_up):
        rule = PriceLimitRule.for_stock(TsCode("000001.SZ"), is_st=True)
        assert rule.calc_up_limit_price(prev_close) == expected_limit_up

    @pytest.mark.parametrize("ts_code,prev_close,expected_limit_up", [
        ("688001.SH", Decimal("50.00"), Decimal("60.00")),  # 科创板 +20%
        ("300750.SZ", Decimal("100.00"), Decimal("120.00")), # 创业板 +20%
    ])
    def test_star_chinext_up_limit(self, ts_code, prev_close, expected_limit_up):
        rule = PriceLimitRule.for_stock(TsCode(ts_code))
        assert rule.calc_up_limit_price(prev_close) == expected_limit_up

    def test_returns_decimal_type(self):
        rule = PriceLimitRule.for_stock(TsCode("000001.SZ"))
        result = rule.calc_up_limit_price(Decimal("10.00"))
        assert isinstance(result, Decimal)

    def test_price_precision_two_decimal_places(self):
        """涨停价必须精确到分"""
        rule = PriceLimitRule.for_stock(TsCode("000001.SZ"))
        result = rule.calc_up_limit_price(Decimal("1.23"))
        assert result == result.quantize(Decimal("0.01"))
```

## 8.5 AI辅助性能优化（A股场景）

```markdown
## 性能分析提示（针对A股数据查询）

"以下数据获取代码在分析自选股列表时很慢，
20支股票的分析需要3分钟，用户体验差。

代码：[粘贴AKShare数据获取代码]

运行环境：
- 单台VPS，4GB RAM
- AKShare接口限速约1req/秒
- 分析20支股票，每支需要行情+基本面+资金流共3个接口

请分析：
1. 串行调用改并发：asyncio.gather()可以并行哪些调用？
   （注意AKShare限速，不能完全并发）
2. 缓存优化：今日已分析过的股票，行情数据可以复用
3. 优先级调度：哪个接口最慢，能否降级跳过？
4. DuckDB预热：是否可以在后台预拉取自选股数据？

对每个优化点给出：
- 预期节省时间
- 代码实现
- 注意事项（如AKShare限速风险）"
```

---

# Part IX — 代码质量门禁与自动化流水线

## 9.1 工具链配置

```toml
# pyproject.toml

[tool.ruff]
line-length = 100
target-version = "py312"
select = [
    "E",     # pycodestyle errors
    "W",     # pycodestyle warnings
    "F",     # pyflakes
    "I",     # isort
    "B",     # flake8-bugbear
    "C4",    # flake8-comprehensions
    "UP",    # pyupgrade
    "ASYNC", # flake8-async（关键：捕获在async上下文中的同步I/O）
    "SIM",   # flake8-simplify
]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # 测试允许assert

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "slow: 慢速测试（需真实网络/API）",
    "integration: 集成测试",
    "unit: 纯单元测试（无外部依赖）",
]
filterwarnings = [
    "error::RuntimeWarning",
]
```

## 9.2 CI/CD流水线

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  quality:
    name: Code Quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3

      - name: Install deps
        run: uv pip install -r requirements.txt

      - name: Lint (ruff)
        run: ruff check backend/ domain/ market_data/ agent/ tests/

      - name: Format check
        run: ruff format --check backend/ domain/ market_data/ agent/

      - name: Type check (mypy)
        run: mypy backend/ domain/ market_data/ agent/ --ignore-missing-imports

  test-unit:
    name: Unit Tests
    runs-on: ubuntu-latest
    needs: quality
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3

      - name: Run unit tests
        run: |
          uv pip install -r requirements.txt
          pytest tests/unit/ -v -m unit \
            --tb=short \
            --timeout=15 \
            --cov=domain \
            --cov=market_data \
            --cov=agent \
            --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4

  test-domain:
    name: Domain Model Tests (A-share specific)
    runs-on: ubuntu-latest
    needs: quality
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3

      - name: Test price limit rules
        run: |
          uv pip install -r requirements.txt
          pytest tests/unit/domain/test_price_limit.py -v
          pytest tests/unit/domain/test_ts_code.py -v

  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Detect API keys
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}

      - name: Dependency audit
        run: |
          pip install pip-audit --break-system-packages
          pip-audit -r requirements.txt
```

## 9.3 PR模板

```markdown
<!-- .github/pull_request_template.md -->

## 概述
<!-- 一句话说明这个PR解决了什么问题 -->

## 变更类型
- [ ] feat：新功能
- [ ] fix：Bug修复
- [ ] refactor：重构
- [ ] data：数据层变更
- [ ] docs：文档更新
- [ ] chore：构建/依赖

## 主要改动
- `domain/`：
- `market_data/`：
- `agent/`：
- `tests/`：

## A股特殊逻辑检查
<!-- 如果涉及以下逻辑，必须填写 -->
- [ ] 无涉及（跳过以下）
- [ ] 涨跌停规则已针对不同市场（主板/科创板/创业板）分别处理
- [ ] 交易日历检查（非交易日是否正确处理）
- [ ] AKShare调用已在run_in_executor中（非阻塞）
- [ ] 金额字段使用Decimal而非float
- [ ] 颜色逻辑：红涨绿跌（A股规范）

## 测试
- [ ] 单元测试覆盖主要逻辑
- [ ] 边界情况测试（ST股/停牌/节假日/涨跌停）
- [ ] Circuit Breaker相关逻辑已测试（如有）
- [ ] 手动测试场景：

## 关联
Closes #
```

---

# Part X — MVP迭代路线：从0到可用

## 10.1 迭代优先级矩阵

```
价值/影响（高→低）
      │
  🔴  │  [A] AKShare网关+熔断器    [B] LangGraph Agent骨架
      │  [C] DeepSeek LLM适配
  🟡  │  [D] SSE进度推送            [E] 技术指标计算
      │  [F] 交易日历服务
  🟢  │  [G] 自选股管理             [H] 分析历史回放
      │
      └────────────────────────────────────────────────►
         简单（1天内）                        复杂（1周+）
```

## 10.2 分阶段实施计划

```
Sprint 0（3-5天）：核心骨架跑通
├── [A] AKShare网关：get_daily_quotes + Circuit Breaker
├── [B] LangGraph：4节点Pipeline（DataCollector→TechAnalyzer→Synthesizer→ReportBuilder）
├── [C] DeepSeek适配器：ainvoke + astream
└── 验收：命令行触发分析600000.SH，能输出文字报告

Sprint 1（1周）：Web接口完整
├── [D] FastAPI接口：POST /research + SSE /events
├── [E] SQLite Schema + 任务状态持久化
├── [F] Lovable前端：搜索框 + 分析进度 + 报告展示
└── 验收：浏览器中输入股票代码，看到实时进度和最终报告

Sprint 2（1-2周）：技术分析丰富化
├── 技术指标全量：MA/MACD/RSI/KDJ/布林带/量比
├── 交易日历服务集成
├── 技术指标可视化（Recharts图表）
└── 自选股管理

Sprint 3（2-3周）：Phase 1数据源扩展
├── 主力资金流向（AKShare capital flow）
├── 北向资金（沪深港通）
├── 基本面数据（财务报表核心指标）
└── 深度分析模式（AnalysisDepth.DEEP）

Sprint 4（持续）：智能化提升
├── RAG知识库（研报/公告）
├── 分析历史回放与对比
└── 批量分析自选股
```

## 10.3 架构决策记录（ADR）

```markdown
# ADR-001: AKShare作为主力数据源

日期：2026-02-25
状态：已接受

背景：
需要免费且覆盖A股全面的数据源。

决策：
使用AKShare作为主力数据源，Tushare免费积分作为财务数据补充。

理由：
- AKShare完全免费，无需token，覆盖行情/资金流/财报/北向资金
- Tushare免费积分每日有上限，不适合高频调用
- 可通过Circuit Breaker处理AKShare偶发的限速/故障

代价：
- AKShare是同步库，需要run_in_executor包装（增加一点复杂性）
- AKShare列名为中文，需要硬编码映射

---

# ADR-002: SQLite WAL + DuckDB双存储

日期：2026-02-25
状态：已接受

背景：
VPS内存有限（2-4GB），需要轻量存储方案。

决策：
- SQLite（WAL模式）：任务状态/报告/自选股（OLTP场景）
- DuckDB（嵌入式）：行情时序数据（OLAP/时间范围查询）

理由：
- SQLite WAL支持并发读，配合workers=1足够个人使用
- DuckDB列存储对时序查询（如"取最近250个交易日数据"）极快
- 两者都是嵌入式，无需独立进程，适合小型VPS

代价：
- 两套存储增加一定认知负担

---

# ADR-003: SSE代替WebSocket用于进度推送

日期：2026-02-25
状态：已接受

背景：
A股分析需要15-120秒，需要实时进度反馈。

决策：
使用SSE（Server-Sent Events），不使用WebSocket。

理由：
- 分析进度是单向推送（服务端→客户端），SSE完全满足
- SSE穿透Nginx反向代理更稳定
- Lovable前端对EventSource支持良好
- WebSocket双向通信在此场景是过度设计

代价：
- SSE不支持客户端→服务端推送（本项目不需要此功能）

---

# ADR-004: DeepSeek作为默认LLM

日期：2026-02-25
状态：已接受

背景：
需要在中文金融分析能力和API成本之间平衡。

决策：
DeepSeek-chat作为默认LLM，Ollama(本地)作为备用。

理由：
- DeepSeek中文能力优秀，A股术语理解准确
- API成本极低（约为GPT-4的1/10）
- Ollama支持离线使用（开发/调试时不消耗API额度）
- 通过LLMAdapter可随时切换，无代码侵入

代价：
- DeepSeek上下文窗口需要关注（deepseek-chat 64K，足够本项目）
```

---

# 附录

## A. .env.example模板

```bash
# .env.example — AIInvest后端配置模板
# 复制为 .env 后填入真实值，.env 绝对不入Git

# ===== 项目信息 =====
PROJECT_NAME="AIInvest"
ENV="development"               # development / production

# ===== LLM配置 =====
LLM_PROVIDER="deepseek"         # deepseek / ollama
LLM_MODEL="deepseek-chat"
LLM_API_KEY=""                  # DeepSeek API Key
LLM_BASE_URL=""                 # Ollama时填 http://localhost:11434
LLM_TIMEOUT_SECONDS=60

# ===== 数据源配置 =====
TUSHARE_TOKEN=""                # Tushare token（可选，用于财务数据补充）
AKSHARE_RATE_LIMIT=1.0          # AKShare请求间隔（秒）

# ===== 数据库配置 =====
SQLITE_PATH="data/aiinvest.db"
DUCKDB_PATH="data/quotes.duckdb"
CHROMA_PATH="data/chroma"       # Phase 2才用

# ===== Circuit Breaker =====
CB_FAILURE_THRESHOLD=5
CB_RECOVERY_TIMEOUT=60.0
CB_HALF_OPEN_MAX=2

# ===== API服务 =====
BACKEND_HOST="0.0.0.0"
BACKEND_PORT=8000
CORS_ORIGINS="https://your-lovable-app.lovable.app,http://localhost:3000"

# ===== 缓存TTL（秒）=====
CACHE_DAILY_QUOTE_SECONDS=3600   # 日线数据缓存1小时
CACHE_FUNDAMENTAL_SECONDS=86400  # 基本面缓存1天
```

## B. 工具速查手册

```bash
# ===== 开发环境启动 =====
uvicorn main:app --reload --workers 1 --port 8000

# ===== 测试命令 =====
# 运行所有单元测试
pytest tests/unit/ -v -m unit

# 运行A股领域模型测试（最重要，不依赖网络）
pytest tests/unit/domain/ -v

# 运行集成测试（需要网络）
pytest tests/integration/ -v -m integration --timeout=60

# 查看覆盖率
pytest tests/unit/ --cov=domain --cov=market_data --cov=agent --cov-report=html
open htmlcov/index.html

# ===== 代码质量 =====
# 检查
ruff check . && ruff format --check . && mypy domain/ market_data/ agent/

# 自动修复
ruff format . && ruff check --fix .

# ===== Git常用 =====
git log --oneline --graph --all
git tag -l "v*" --sort=-version:refname
git stash push -m "WIP: [描述]"
git log --oneline v0.1.0..HEAD  # 本次sprint变更日志

# ===== 数据工具 =====
# 初始化数据库
python -c "from db.connection import init_db; import asyncio; asyncio.run(init_db())"

# 同步股票列表（从AKShare拉取并缓存到SQLite）
python scripts/sync_stock_list.py

# 预加载交易日历（2023-2026）
python scripts/seed_trading_calendar.py --years 2023,2024,2025,2026

# ===== AKShare快速验证 =====
python -c "
import akshare as ak
df = ak.stock_zh_a_hist(symbol='000001', period='daily',
    start_date='20241201', end_date='20241231', adjust='qfq')
print(df.tail(3))
"

# ===== DeepSeek API验证 =====
python -c "
import asyncio
from llm.adapters.deepseek import DeepSeekAdapter
adapter = DeepSeekAdapter(api_key='your-key')
result = asyncio.run(adapter.ainvoke([{'role':'user','content':'分析000001.SZ平安银行一句话'}]))
print(result)
"
```

---

> **核心理念**：这些工程实践不是束缚，而是在项目成长时让你继续快速前进的加速器。
>
> **MVP优先顺序**：先让代码工作（跑通主流程），再让代码正确（边界情况覆盖），最后让代码优雅（重构设计模式）。
>
> **A股系统的关键差异**：在通用工程实践之上，必须深刻理解涨跌停、T+1、交易日历、ST机制等A股特有规则，任何分析逻辑的正确性都建立在此之上。

---

*版本：2.0.0 | 日期：2026-02-25 | 适用：AIInvest个人MVP*