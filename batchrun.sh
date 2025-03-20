#!/bin/bash
#SBATCH --account PAS2942
#SBATCH --job-name isyntax2tiff_batchrun
#SBATCH --array=1-153%4          # Adjust 50 to the number of images in your input_list.txt
#SBATCH --nodes=1              # Use 1 node per job (adjust as needed)
#SBATCH --ntasks=1             # 1 task per job
#SBATCH --cpus-per-task=4      # Adjust based on required CPU cores
#SBATCH --mem=24G              # Adjust memory per job
#SBATCH --time=08:00:00        # Adjust max runtime
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --partition=nextgen # Can also explicitly specify which cluster to submit the job to. Or, log in to the node and submit the job.

# Load necessary modules (if required)
module use $HOME/local/share/lmodfiles
module load pathologysdk/2.0-L1
module load miniconda3
source activate philips

# Define the input folder and output directory
OUTPUT_DIR=./outputs

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Get the image filename from the input list
IMAGE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" input_list.txt)

# Safety check: if empty, exit gracefully
if [ -z "$IMAGE" ]; then
    echo "No image found for task ID ${SLURM_ARRAY_TASK_ID}"
    exit 1
fi

# Get the basename without extension
BASENAME=$(basename "$IMAGE" .i2syntax)

echo "Processing image: $BASENAME"

# # Step 1: Convert iSyntax to Zarr
isyntax2raw write_tiles "$IMAGE" "$OUTPUT_DIR/${BASENAME}.zarr" --tile_width 1024 --tile_height 1024

echo "Finished writing Zarr file for $BASENAME"

# Step 2: Convert Zarr to OME-TIFF
raw2ometiff "$OUTPUT_DIR/${BASENAME}.zarr" "$OUTPUT_DIR/${BASENAME}.ome.tiff" --rgb

echo "Done converting $BASENAME to OME-TIFF"