#!/usr/bin/env python3
"""Test alternative akshare interfaces for data collector replacement"""

import sys
sys.path.insert(0, '/Users/rock.xu/github/projects/ai-ml/stocks_analysis.py')

import akshare as ak
from tqdm import tqdm
import pandas as pd

def test_interface(name, func, *args, **kwargs):
    """Test a single akshare interface"""
    try:
        print(f"\nTesting: {name}")
        result = func(*args, **kwargs)
        if result is not None and not result.empty:
            print(f"✓ SUCCESS - Columns: {list(result.columns)[:5]}...")
            print(f"  Shape: {result.shape}, Sample data:\n{result.head(2)}")
            return True, result
        else:
            print(f"✗ FAILED - No data returned")
            return False, None
    except Exception as e:
        print(f"✗ ERROR: {type(e).__name__}: {e}")
        return False, None

def main():
    print("=" * 80)
    print("Testing Alternative akshare Interfaces")
    print("=" * 80)

    results = {}

    # 1. MACRO DATA ALTERNATIVES
    print("\n" + "=" * 80)
    print("1. MACRO DATA (Index Data Sources)")
    print("=" * 80)

    # Test 1.1: SSE/Shenzhen official summaries (known working)
    success, df = test_interface(
        "SSE Summary",
        ak.stock_sse_summary
    )
    results['sse_summary'] = (success, df)

    success, df = test_interface(
        "SZSE Summary",
        ak.stock_szse_summary
    )
    results['szse_summary'] = (success, df)

    # Test 1.2: Individual index info
    success, df = test_interface(
        "Index info (SSE)",
        ak.stock_individual_info_em,
        symbol="000001"
    )
    results['index_info_sse'] = (success, df)

    # Test 1.3: Sina stock API (index data) - skip for now
    # success, df = test_interface(
    #     "Index Daily (Sina)",
    #     ak.zh_index_daily,
    #     symbol="sh000001"
    # )
    # results['index_daily_sina'] = (success, df)

    # Test 1.4: Spot index from various sources - skip for now
    # success, df = test_interface(
    #     "Index Spot (Baidu)",
    #     ak.stock_zh_index_spot,
    #     symbol="000001"
    # )
    # results['index_spot_baidu'] = (success, df)

    # Test 1.5: US index data
    success, df = test_interface(
        "US Index Spot",
        ak.stock_us_spot_em
    )
    results['us_index_spot'] = (success, df)

    # 2. SECTOR DATA ALTERNATIVES
    print("\n" + "=" * 80)
    print("2. SECTOR DATA (Board/Concept Sources)")
    print("=" * 80)

    # Test 2.1: Concept board via Tonghuashun (THS) - known working
    success, df = test_interface(
        "Concept Boards (THS)",
        ak.stock_board_concept_name_ths
    )
    results['concept_ths'] = (success, df)

    # Test 2.2: Industry board via Tonghuashun
    success, df = test_interface(
        "Industry Boards (THS)",
        ak.stock_board_industry_name_ths
    )
    results['industry_ths'] = (success, df)

    # Test 2.3: Sectors via Sina
    success, df = test_interface(
        "Sector List (Sina)",
        ak.stock_sector_spot
    )
    results['sector_sina'] = (success, df)

    # Test 2.4: Concept stocks per board (THS)
    if results.get('concept_ths') and results['concept_ths'][0]:
        print("\n  Testing concept stocks for first board from THS...")
        first_board = results['concept_ths'][1].iloc[0]
        if '板块名称' in first_board.index:
            board_name = first_board['板块名称']
            print(f"  Board: {board_name}")
            success, df = test_interface(
                f"Concept Stocks: {board_name} (THS)",
                ak.stock_board_concept_cons_ths,
                symbol=board_name
            )
            results['concept_cons_ths'] = (success, df)

    # Test 2.5: Industry stocks per board (THS)
    if results.get('industry_ths') and results['industry_ths'][0]:
        print("\n  Testing industry stocks for first board from THS...")
        first_board = results['industry_ths'][1].iloc[0]
        if '板块名称' in first_board.index:
            board_name = first_board['板块名称']
            print(f"  Board: {board_name}")
            success, df = test_interface(
                f"Industry Stocks: {board_name} (THS)",
                ak.stock_board_industry_cons_ths,
                symbol=board_name
            )
            results['industry_cons_ths'] = (success, df)

    # Test 2.6: Board summary (alternative)
    success, df = test_interface(
        "Industry Board Summary (THS)",
        ak.stock_board_industry_summary_ths
    )
    results['industry_summary_ths'] = (success, df)

    # 3. STOCK DATA ALTERNATIVES
    print("\n" + "=" * 80)
    print("3. STOCK DATA (Stock Quotes Sources)")
    print("=" * 80)

    # Test 3.1: Individual stock info
    for stock_code in ["000001", "300001"]:
        success, df = test_interface(
            f"Stock Info: {stock_code}",
            ak.stock_individual_info_em,
            symbol=stock_code
        )
        results[f'stock_info_{stock_code}'] = (success, df)

        success, df = test_interface(
            f"Stock Bid/Ask: {stock_code}",
            ak.stock_bid_ask_em,
            symbol=stock_code
        )
        results[f'stock_bidask_{stock_code}'] = (success, df)

    # Test 3.2: Stock list
    success, df = test_interface(
        "A-Stock List",
        ak.stock_info_a_code_name
    )
    results['stock_list'] = (success, df)

    # Test 3.3: Stock daily data
    success, df = test_interface(
        "Stock Daily (000001)",
        ak.stock_zh_a_hist,
        symbol="000001",
        period="daily",
        adjust="qfq"
    )
    results['stock_daily'] = (success, df)

    # Test 3.4: Sina real-time quotes - skip for now
    # success, df = test_interface(
    #     "Stock Szse Spot (Sina)",
    #     ak.stock_szse_spot_description
    # )
    # results['stock_sina'] = (success, df)

    # Test 3.5: Baidu stock data - skip for now
    # success, df = test_interface(
    #     "Stock Realtime (Baidu)",
    #     ak.stock_zh_a_spot
    # )
    # results['stock_baidu'] = (success, df)

    # SUMMARY
    print("\n" + "=" * 80)
    print("SUMMARY - Working Interfaces")
    print("=" * 80)

    working = {k: v for k, v in results.items() if v[0]}
    failed = {k: v for k, v in results.items() if not v[0]}

    print(f"\nWorking interfaces ({len(working)}):")
    for name, (success, df) in working.items():
        print(f"  ✓ {name}")

    print(f"\nFailed interfaces ({len(failed)}):")
    for name, (success, df) in failed.items():
        print(f"  ✗ {name}")

    # Recommendation summary
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS FOR DATA_COLLECTOR.PY")
    print("=" * 80)

    print("\n1. Macro Data Replacements:")
    if 'index_spot_baidu' in working:
        print("  - Use ak.stock_zh_index_spot() for index data")
    if 'daily_sina' in working:
        print("  - Use ak.zh_index_daily() for historical index data")
    if 'index_info_sse' in working:
        print("  - Use ak.stock_individual_info_em() for individual index info")

    print("\n2. Sector Data Replacements:")
    if 'concept_ths' in working:
        print("  - Use ak.stock_board_concept_name_ths() for concept boards")
    if 'industry_ths' in working:
        print("  - Use ak.stock_board_industry_name_ths() for industry boards")
    if 'concept_cons_ths' in working:
        print("  - Use ak.stock_board_concept_cons_ths() for concept constituents")
    if 'industry_cons_ths' in working:
        print("  - Use ak.stock_board_industry_cons_ths() for industry constituents")
    if 'industry_summary_ths' in working:
        print("  - Use ak.stock_board_industry_summary_ths() for board summary")

    print("\n3. Stock Data Replacements:")
    if 'stock_info_000001' in working:
        print("  - Use ak.stock_individual_info_em() for stock info")
    if 'stock_daily' in working:
        print("  - Use ak.stock_zh_a_hist() for historical data")
    if 'stock_baidu' in working:
        print("  - Use ak.stock_zh_a_spot() for real-time quotes")
    if 'stock_list' in working:
        print("  - Use ak.stock_info_a_code_name() for stock list")

if __name__ == "__main__":
    main()
