import pandas as pd

df=pd.read_csv('data/1610612759_2023_rs.csv')
df.sort_values(by=['game_id','period', 'clock','actionNumber'],inplace=True)
print(df.head(30))
print(df.head(30)[['teamId']])
print(df.columns)