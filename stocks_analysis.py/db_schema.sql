-- A股AI投资分析系统 - Database Schema
-- sqlite initializetion script

CREATE TABLE IF NOT EXISTS macro_indicators (
    date TEXT PRIMARY KEY,
    us_sp500 REAL,
    us_nasdaq REAL,
    cn_sh REAL,
    cn_sz REAL,
    vix REAL,
    market_score REAL
);

CREATE TABLE IF NOT EXISTS sector_performance (
    date TEXT,
    sector_name TEXT,
    change_pct REAL,
    momentum_score REAL,
    amount REAL,
    trend_status TEXT,
    PRIMARY KEY (date, sector_name)
);

CREATE TABLE IF NOT EXISTS stock_technical (
    date TEXT,
    stock_code TEXT,
    name TEXT,
    price REAL,
    change_pct REAL,
    volume REAL,
    turnover REAL,
    ma5 REAL,
    ma20 REAL,
    PRIMARY KEY (date, stock_code)
);

CREATE TABLE IF NOT EXISTS ai_reports (
    date TEXT PRIMARY KEY,
    content_md TEXT,
    ai_signal TEXT
);

-- 索引 for frequent queries
CREATE INDEX IF NOT EXISTS idx_sector_date ON sector_performance(date);
CREATE INDEX IF NOT EXISTS idx_sector_change_pct ON sector_performance(change_pct);
CREATE INDEX IF NOT EXISTS idx_sector_momentum_score ON sector_performance(momentum_score);

CREATE INDEX IF NOT EXISTS idx_stock_date ON stock_technical(date);
CREATE INDEX IF NOT EXISTS idx_stock_change_pct ON stock_technical(change_pct);

CREATE INDEX IF NOT EXISTS idx_macro_date ON macro_indicators(date);