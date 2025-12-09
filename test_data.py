import pandas as pd

df=pd.read_parquet('data/1610612759_2023_rs.parquet')
print(df.columns)