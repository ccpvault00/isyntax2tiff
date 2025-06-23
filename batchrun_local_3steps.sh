#!/bin/bash

# Local batch conversion script with parallelization
# Usage: ./batchrun_local.sh <input_dir_or_file> [output_dir] [parallel_jobs]
# Examples:
#   ./batchrun_local.sh input.isyntax                    # Single file to ./outputs
#   ./batchrun_local.sh ./input_dir                      # Directory to ./outputs  
#   ./batchrun_local.sh ./input_dir ./my_outputs         # Directory to custom output
#   ./batchrun_local.sh ./input_dir ./my_outputs 8       # Directory with 8 parallel jobs

# Default values
DEFAULT_OUTPUT_DIR="./outputs"  
DEFAULT_PARALLEL_JOBS=4

# Parse arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <input_dir_or_file> [output_dir] [parallel_jobs]"
    echo ""
    echo "Arguments:"
    echo "  input_dir_or_file  : Path to .isyntax file or directory containing .isyntax files"
    echo "  output_dir         : Output directory (default: $DEFAULT_OUTPUT_DIR)"
    echo "  parallel_jobs      : Number of parallel jobs (default: $DEFAULT_PARALLEL_JOBS)"
    echo ""
    echo "Examples:"
    echo "  $0 input.isyntax"
    echo "  $0 ./input_dir"
    echo "  $0 ./input_dir ./my_outputs"
    echo "  $0 ./input_dir ./my_outputs 8"
    exit 1
fi

INPUT_PATH="$1"
OUTPUT_DIR="${2:-$DEFAULT_OUTPUT_DIR}"
PARALLEL_JOBS="${3:-$DEFAULT_PARALLEL_JOBS}"

# Validate input
if [ ! -e "$INPUT_PATH" ]; then
    echo "Error: Input path '$INPUT_PATH' does not exist"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to process a single file
process_file() {
    local input_file="$1"
    local output_dir="$2"
    local basename=$(basename "$input_file" .isyntax)
    
    echo "[$(date '+%H:%M:%S')] Processing: $basename"
    
    # Step 1: Convert iSyntax to Zarr
    echo "[$(date '+%H:%M:%S')] Step 1/3: Converting $basename to Zarr..."
    if ! isyntax2raw write_tiles "$input_file" "$output_dir/${basename}.zarr" --tile_width 1024 --tile_height 1024; then
        echo "[$(date '+%H:%M:%S')] ERROR: Failed to convert $basename to Zarr"
        return 1
    fi
    
    # Step 2: Convert Zarr to OME-TIFF
    echo "[$(date '+%H:%M:%S')] Step 2/3: Converting $basename to OME-TIFF..."
    if ! raw2ometiff "$output_dir/${basename}.zarr" "$output_dir/${basename}.ome.tiff" --rgb; then
        echo "[$(date '+%H:%M:%S')] ERROR: Failed to convert $basename to OME-TIFF"
        return 1
    fi
    
    # Step 3: Convert OME-TIFF to Pyramidal TIFF
    echo "[$(date '+%H:%M:%S')] Step 3/3: Converting $basename to Pyramidal TIFF..."
    if ! python ome2pyramidaltiff.py --path "$output_dir/${basename}.ome.tiff" --output "$output_dir/${basename}.tiff"; then
        echo "[$(date '+%H:%M:%S')] ERROR: Failed to convert $basename to Pyramidal TIFF"
        return 1
    fi
    
    echo "[$(date '+%H:%M:%S')] SUCCESS: Completed $basename -> $output_dir/${basename}.tiff"
    return 0
}

# Export function for parallel execution
export -f process_file

# Collect input files
input_files=()
if [ -f "$INPUT_PATH" ]; then
    # Single file
    if [[ "$INPUT_PATH" == *.isyntax ]]; then
        input_files=("$INPUT_PATH")
    else
        echo "Error: File '$INPUT_PATH' is not a .isyntax file"
        exit 1
    fi
elif [ -d "$INPUT_PATH" ]; then
    # Directory - find all .isyntax files
    while IFS= read -r -d '' file; do
        input_files+=("$file")
    done < <(find "$INPUT_PATH" -name "*.isyntax" -type f -print0)
    
    if [ ${#input_files[@]} -eq 0 ]; then
        echo "Error: No .isyntax files found in directory '$INPUT_PATH'"
        exit 1
    fi
else
    echo "Error: '$INPUT_PATH' is neither a file nor a directory"
    exit 1
fi

echo "Found ${#input_files[@]} .isyntax file(s) to process"
echo "Output directory: $OUTPUT_DIR"
echo "Parallel jobs: $PARALLEL_JOBS"
echo "Starting batch conversion..."
echo ""

# Process files in parallel using GNU parallel or xargs
if command -v parallel >/dev/null 2>&1; then
    # Use GNU parallel if available
    printf '%s\n' "${input_files[@]}" | parallel -j "$PARALLEL_JOBS" process_file {} "$OUTPUT_DIR"
    exit_code=$?
else
    # Fallback to xargs with -P for parallelization
    printf '%s\n' "${input_files[@]}" | xargs -I {} -P "$PARALLEL_JOBS" bash -c 'process_file "$@"' _ {} "$OUTPUT_DIR"
    exit_code=$?
fi

echo ""
echo "Batch conversion completed!"
echo "Processed ${#input_files[@]} files with $PARALLEL_JOBS parallel jobs"
echo "Output files are in: $OUTPUT_DIR"

if [ $exit_code -eq 0 ]; then
    echo "All conversions completed successfully!"
else
    echo "Some conversions may have failed. Check the logs above."
fi

exit $exit_code