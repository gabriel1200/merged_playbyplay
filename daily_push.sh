git add --all
git commit -m 'daily'
git push 
#!/bin/bash

# ensure destination directory exists
mkdir -p ../prob_merge/data

# copy all CSV files containing 2026 in the filename
cp data/*2026*.csv ../prob_merge/data/
