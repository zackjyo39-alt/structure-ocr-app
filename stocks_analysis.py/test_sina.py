#!/usr/bin/env python3
"""Test Sina-based stock data functions"""

import sys
sys.path.insert(0, '/Users/rock.xu/github/projects/ai-ml/stocks_analysis.py')

import akshare as ak
import pandas as pd

def test_sina_functions():
    """Test Sina-based stock data functions"""

    print("=" * 80)
    print("Testing Sina-Based Stock Data Functions")
    print("=" * 80)

    # 1. Test sector spot (we know this worked)
    print("\n1. Testing sector_spot...")
    try:
        df = ak.stock_sector_spot()
        print(f"  ✓ Success - Shape: {df.shape}")
        print(f"  Columns: {list(df.columns)[:10]}...")
        print(f"  Sample:\n{df.head(3)}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")

    # 2. Test individual stock data via Sina
    print("\n2. Testing stock_szse_spot...")
    try:
        df = ak.stock_szse_spot()
        print(f"  ✓ Success - Shape: {df.shape}")
        print(f"  Columns: {list(df.columns)[:10]}...")
        print(f"  Sample:\n{df.head(3)}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")

    # 3. Test various Sina interfaces
    print("\n3. Finding all 'szse' related functions...")
    szse_funcs = [f for f in dir(ak) if 'szse' in f.lower()]
    print(f"  Found {len(szse_funcs)} functions:")
    for func in sorted(szse_funcs):
        print(f"    - ak.{func}")

    # 4. Test SSE spot
    print("\n4. Testing stock_sse_spot...")
    try:
        df = ak.stock_sse_spot()
        print(f"  ✓ Success - Shape: {df.shape}")
        print(f"  Columns: {list(df.columns)[:10]}...")
        print(f"  Sample:\n{df.head(3)}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")

    # 5. Test individual stock functions
    print("\n5. Testing stock_individual_info_em for multiple stocks...")
    stock_codes = ["000001", "000002", "600000"]
    for code in stock_codes:
        try:
            df = ak.stock_individual_info_em(symbol=code)
            print(f"  {code}: ✓ Success - {df.shape}, latest: {df[df['item']=='最新']['value'].values}")
        except Exception as e:
            print(f"  {code}: ✗ Error - {type(e).__name__}")

if __name__ == "__main__":
    test_sina_functions()
