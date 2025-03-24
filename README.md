# Isyntax2tiff

## Set up

Check [environment_installment](./environment_installment/) folder.

## Generate txt file for isyntax list
    find <isyntax folder> -maxdepth 1 -type f -name "*.i2syntax" | sort > input_list.txt

## Batch run isyntax2ometiff:
Change file number in the `batchrun.sh` in line 10:

    sbatch batchrun.sh

## Batch run ome to pyramidal tiff (TO BE INTEGRADTED WITH PREVIOUS SCRIPT):
    sbatch batchrun_ome2pyramidal.sh