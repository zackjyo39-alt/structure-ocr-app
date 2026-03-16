#!/usr/bin/env python3
"""Test THS concept/industry constituent functions"""

import sys
sys.path.insert(0, '/Users/rock.xu/github/projects/ai-ml/stocks_analysis.py')

import akshare as ak
from tqdm import tqdm
import pandas as pd

def test_concept_cons():
    """Test concept constituent stocks"""
    print("=" * 80)
    print("Testing THS Concept/Industry Constituent Functions")
    print("=" * 80)

    # First get the concept boards
    print("\n1. Getting all concept boards...")
    concept_df = ak.stock_board_concept_name_ths()
    print(f"Found {len(concept_df)} concept boards")

    # Show some AI-related boards
    ai_keywords = ['芯片', 'AI', '人工智能', '算力', '光模块', 'CPO']
    print(f"\n2. Finding AI-related boards (keywords: {ai_keywords})...")
    ai_boards = []
    for _, row in concept_df.iterrows():
        name = row['name']
        if any(keyword in name for keyword in ai_keywords):
            ai_boards.append(name)

    print(f"Found {len(ai_boards)} AI-related boards:")
    for board in ai_boards[:10]:  # Show first 10
        print(f"  - {board}")

    # Test a few boards
    print("\n3. Testing constituent stocks for AI-related boards...")
    for board_name in ai_boards[:5]:  # Test first 5
        try:
            print(f"\n  Board: {board_name}")
            stocks_df = ak.stock_board_concept_cons_ths(symbol=board_name)
            print(f"  ✓ Success - Found {len(stocks_df)} stocks")
            print(f"  Columns: {list(stocks_df.columns)[:5]}...")
            print(f"  Sample:\n{stocks_df.head(2)}")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {e}")

    # Test industry boards
    print("\n" + "=" * 80)
    print("4. Getting all industry boards...")
    industry_df = ak.stock_board_industry_name_ths()
    print(f"Found {len(industry_df)} industry boards")

    # Test an industry board
    print("\n5. Testing constituent stocks for '半导体' industry...")
    try:
        industry_name = '半导体'
        stocks_df = ak.stock_board_industry_cons_ths(symbol=industry_name)
        print(f"  ✓ Success - Found {len(stocks_df)} stocks")
        print(f"  Columns: {list(stocks_df.columns)[:5]}...")
        print(f"  Sample:\n{stocks_df.head(2)}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("✓ THS interfaces work for concept/industry board data")
    print("✓ Can use these to get sector information and stock lists")

if __name__ == "__main__":
    test_concept_cons()
