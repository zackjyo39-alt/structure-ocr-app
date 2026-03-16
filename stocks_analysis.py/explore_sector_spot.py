#!/usr/bin/env python3
"""Explore stock_sector_spot data structure"""

import sys
sys.path.insert(0, '/Users/rock.xu/github/projects/ai-ml/stocks_analysis.py')

import akshare as ak
import pandas as pd

def explore_sector_spot():
    """Explore the structure of stock_sector_spot()"""

    print("=" * 80)
    print("Exploring stock_sector_spot() Data Structure")
    print("=" * 80)

    # Get sector spot data
    df = ak.stock_sector_spot()

    print(f"\nFull DataFrame shape: {df.shape}")
    print(f"\nAll columns ({len(df.columns)}):")
    for i, col in enumerate(df.columns):
        print(f"  {i+1}. {col}")

    print("\n" + "=" * 80)
    print("First sector (full data):")
    print("=" * 80)
    first_sector = df.iloc[0]
    print(first_sector)

    # Check if there are individual stock codes in the data
    print("\n" + "=" * 80)
    print("Checking individual stock data embedded in sector data...")
    print("=" * 80)

    for idx in range(min(3, len(df))):
        sector = df.iloc[idx]
        print(f"\nSector {idx+1}: {sector['板块']}")
        print(f"  Company count: {sector['公司家数']}")

        # Check what's in the individual stock columns
        stock_data_cols = ['股票代码', '股票名称', '个股-当前价', '个股-涨跌幅']
        found_any = False
        for col in stock_data_cols:
            if col in sector.index:
                val = sector[col]
                print(f"  {col}: {val}")
                found_any = True

        if not found_any:
            print("  (No individual stock columns found)")

    # Expand: Look for multiple stocks per sector
    print("\n" + "=" * 80)
    print("Let's see if we can get stock-specific data by sector...")
    print("=" * 80)

    # Try getting stocks for a specific label
    print("Looking for specific sectors (e.g., tech-related)...")
    tech_keywords = ['科技', '电子', '计算机', '通信', '软件']
    matching_sectors = df[df['板块'].str.contains('|'.join(tech_keywords), na=False)]
    print(f"Found {len(matching_sectors)} tech-related sectors:")
    for _, row in matching_sectors.head(5).iterrows():
        print(f"  - {row['板块']}: {row['公司家数']} companies")

if __name__ == "__main__":
    explore_sector_spot()
