#!/bin/bash

# Local conversion script (non-SLURM version)
# Usage: ./local_convert.sh input.isyntax

if [ $# -eq 0 ]; then
    echo "Usage: $0 <input.isyntax>"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_DIR="./outputs"
BASENAME=$(basename "$INPUT_FILE" .isyntax)

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Processing: $BASENAME"

# Step 1: Convert iSyntax to Zarr
echo "Step 1: Converting iSyntax to Zarr..."
isyntax2raw write_tiles "$INPUT_FILE" "$OUTPUT_DIR/${BASENAME}.zarr" --tile_width 1024 --tile_height 1024

# Step 2: Convert Zarr to OME-TIFF
echo "Step 2: Converting Zarr to OME-TIFF..."
raw2ometiff "$OUTPUT_DIR/${BASENAME}.zarr" "$OUTPUT_DIR/${BASENAME}.ome.tiff" --rgb

# Step 3: Convert OME-TIFF to Pyramidal TIFF
echo "Step 3: Converting OME-TIFF to Pyramidal TIFF..."
python ome2pyramidaltiff.py --path "$OUTPUT_DIR/${BASENAME}.ome.tiff" --output "$OUTPUT_DIR/${BASENAME}.tiff"

echo "Conversion complete! Output files:"
echo "  - $OUTPUT_DIR/${BASENAME}.zarr"
echo "  - $OUTPUT_DIR/${BASENAME}.ome.tiff"
echo "  - $OUTPUT_DIR/${BASENAME}.tiff"
