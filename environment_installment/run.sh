#!/bin/bash
#SBATCH --account PAS2942
#SBATCH --job-name isyntax2tiff_singlerun
#SBATCH --nodes=1              # Use 1 node per job (adjust as needed)
#SBATCH --ntasks=1             # 1 task per job
#SBATCH --cpus-per-task=4      # Adjust based on required CPU cores
#SBATCH --mem=24G              # Adjust memory per job
#SBATCH --time=02:00:00        # Adjust max runtime
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --cluster=ascend # Can also explicitly specify which cluster to submit the job to. Or, log in to the node and submit the job.


# Load necessary modules (if required)
module use $HOME/local/share/lmodfiles
module load pathologysdk/2.0-L1
module load miniconda3
source activate philips

BASENAME="IHC_DR0004"

echo "Processing image: $BASENAME"

# # Step 1: Convert iSyntax to Zarr
isyntax2raw write_tiles ./isyntaxsamples/$IMAGE ./outputs/${BASENAME}.zarr --tile_width 1024 --tile_height 1024

echo "Finished writing Zarr file for $BASENAME"

# Step 2: Convert Zarr to OME-TIFF
raw2ometiff ./outputs/${BASENAME}.zarr ./outputs/${BASENAME}.ome.tiff --rgb

echo "Done converting $BASENAME to OME-TIFF"
