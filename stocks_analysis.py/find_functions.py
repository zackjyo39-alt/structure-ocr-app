#!/usr/bin/env python3
"""Find correct akshare function names"""

import sys
sys.path.insert(0, '/Users/rock.xu/github/projects/ai-ml/stocks_analysis.py')

import akshare as ak

# Get all functions related to 'concept'
print("=" * 80)
print("Finding akshare functions for 'concept' and 'cons' (constituent)")
print("=" * 80)

concept_funcs = []
all_funcs = dir(ak)
for func_name in all_funcs:
    if 'concept' in func_name.lower():
        concept_funcs.append(func_name)

print(f"\nFunctions with 'concept': ({len(concept_funcs)})")
for func in sorted(concept_funcs):
    print(f"  - ak.{func}")

# Find 'ths' related functions
print("\n" + "=" * 80)
ths_funcs = []
for func_name in all_funcs:
    if 'ths' in func_name.lower() and 'stock' in func_name.lower():
        ths_funcs.append(func_name)

print(f"\nFunctions with 'ths' and 'stock': ({len(ths_funcs)})")
for func in sorted(ths_funcs)[:20]:
    print(f"  - ak.{func}")

# Find 'industry' related functions
print("\n" + "=" * 80)
ind_funcs = []
for func_name in all_funcs:
    if 'industry' in func_name.lower() and 'cons' in func_name.lower():
        ind_funcs.append(func_name)

print(f"\nFunctions with 'industry' and 'cons': ({len(ind_funcs)})")
for func in sorted(ind_funcs):
    print(f"  - ak.{func}")
