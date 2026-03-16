#!/usr/bin/env python3
"""Test functions that might give stock-constituent relationships"""

import sys
sys.path.insert(0, '/Users/rock.xu/github/projects/ai-ml/stocks_analysis.py')

import akshare as ak
import pandas as pd

def test_stock_constituent_functions():
    """Test various functions for getting stock-constituent data"""

    print("=" * 80)
    print("Testing Stock-Constituent Relationship Functions")
    print("=" * 80)

    # 1. Get stock list - this works
    print("\n1. Stock list (ak.stock_info_a_code_name):")
    try:
        stock_list_df = ak.stock_info_a_code_name()
        print(f"  ✓ Success - {len(stock_list_df)} stocks")
        print(f"  Columns: {list(stock_list_df.columns)}")
        print(f"  Sample:\n{stock_list_df.sample(5)}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    # 2. Try to get sector classification for each stock
    print("\n2. Looking at THS functions for stock info...")

    # Try stock_fhps_detail_ths - might contain industry info
    print("\n3. Testing ak.stock_fhps_detail_ths (might have industry/board data):")
    try:
        df = ak.stock_fhps_detail_ths(symbol="000001")
        print(f"  ✓ Success - Columns: {list(df.columns)[:15]}...")
        print(f"  Shape: {df.shape}")
        if not df.empty:
            print(f"  Sample:\n{df.head(2)}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")

    # Try searching for board functions that work
    print("\n4. Finding board-related functions (excluding 'em' and 'cons'):...")
    board_funcs = [f for f in dir(ak) if 'board' in f.lower() and 'em' not in f.lower()]
    for func in sorted(board_funcs)[:15]:
        print(f"  - ak.{func}")

    # 5. Test individual THS info functions that might work
    print("\n5. Testing ak.stock_a_lg_indicator...")
    try:
        df = ak.stock_a_lg_indicator()
        print(f"  ✓ Success - Columns: {list(df.columns)[:10]}...")
        print(f"  Shape: {df.shape}")
        print(f"  Sample:\n{df.head(2)}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")

    # 6. Get more functions from akshare
    print("\n6. Finding individual stock functions...")
    stock_funcs = [f for f in dir(ak) if 'stock' in f.lower() and 'spot' in f.lower()]
    print(f"  Found {len(stock_funcs)} spot functions:")
    for func in sorted(stock_funcs):
        print(f"    - ak.{func}")

if __name__ == "__main__":
    test_stock_constituent_functions()
