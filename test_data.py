import pandas as pd

df=pd.read_csv('data/ATL_2023_rs.csv')
df.sort_values(by=['game_id','period', 'clock','actionNumber'],inplace=True)
print(df[~df['blockPersonId'].isna()])
print(df.head(30)[['teamId']])
print(df.columns)