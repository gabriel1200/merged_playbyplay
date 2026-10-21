[ -n "$NBA_SEASON_YEAR" ] || source ~/basketball/season.sh  # season config when run standalone
git add --all
git commit -m 'daily'
git push 
#!/bin/bash

# ensure destination directory exists
mkdir -p ../prob_merge/data

# copy all CSV files containing the season year in the filename
cp data/*${NBA_SEASON_YEAR}*.csv ../prob_merge/data/
