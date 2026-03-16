#!/usr/bin/env python3
"""Test THS info functions"""

import sys
sys.path.insert(0, '/Users/rock.xu/github/projects/ai-ml/stocks_analysis.py')

import akshare as ak
import pandas as pd

def test_info_functions():
    """Test THS info functions"""

    print("=" * 80)
    print("Testing THS Info Functions")
    print("=" * 80)

    # Get concept boards
    print("\n1. Getting concept boards...")
    concept_df = ak.stock_board_concept_name_ths()
    print(f"Found {len(concept_df)} concept boards")

    # Test the info function for a couple of boards
    test_boards = ["AI", "半导体", "算力"]
    for board_name in test_boards[:3]:
        # Find the actual board name
        matching = concept_df[concept_df['name'].str.contains(board_name)]
        if not matching.empty:
            actual_name = matching.iloc[0]['name']
            board_code = matching.iloc[0]['code']

            print(f"\n2. Testing info for: {actual_name} (code: {board_code})")

            try:
                info_df = ak.stock_board_concept_info_ths(symbol=board_code)
                print(f"  ✓ Success - Columns: {list(info_df.columns)}")
                print(f"  Shape: {info_df.shape}")
                print(f"  Sample:\n{info_df.head(2)}")
            except Exception as e:
                print(f"  ✗ Error: {type(e).__name__}: {e}")

    # Get industry boards
    print("\n" + "=" * 80)
    print("3. Getting industry boards...")
    industry_df = ak.stock_board_industry_name_ths()
    print(f"Found {len(industry_df)} industry boards")

    # Test info for semiconductor
    matching = industry_df[industry_df['name'].str.contains('半导体')]
    if not matching.empty:
        actual_name = matching.iloc[0]['name']
        board_code = matching.iloc[0]['code']

        print(f"\n4. Testing info for: {actual_name} (code: {board_code})")

        try:
            info_df = ak.stock_board_industry_info_ths(symbol=board_code)
            print(f"  ✓ Success - Columns: {list(info_df.columns)}")
            print(f"  Shape: {info_df.shape}")
            print(f"  Sample:\n{info_df.head(2)}")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {e}")

    # Test summary function which might have stock data
    print("\n" + "=" * 80)
    print("5. Testing concept summary function...")
    try:
        summary_df = ak.stock_board_concept_summary_ths()
        print(f"  ✓ Success - Columns: {list(summary_df.columns)}")
        print(f"  Shape: {summary_df.shape}")
        print(f"  Sample:\n{summary_df.head(3)}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_info_functions()
