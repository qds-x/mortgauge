# Snippets

## print dataframe with all rows/columns
```python
print(f"Total Interest Paid: {total_interest_paid}")
with pd.option_context('display.max_rows', None, 'display.max_columns', None):  # more options can be specified
    print(df.to_string(index=False))
```

