# Isyntax2tiff

## Generate txt file for isyntax list
    find <isyntax folder> -maxdepth 1 -type f -name "*.i2syntax" | sort > input_list.txt

## Batch run:
Change file number in the `batchrun.sh` in line 10:

    sbatch batchrun.sh