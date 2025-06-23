#!/usr/bin/bash

# Batch Direct iSyntax to Pyramidal TIFF Converter
# Simple wrapper script for batch_direct_convert.py

# Default settings optimized for performance
DEFAULT_FILE_WORKERS=2
DEFAULT_CONVERSION_WORKERS=8
DEFAULT_TILE_SIZE=1024
DEFAULT_COMPRESSION="jpeg"
DEFAULT_QUALITY=90

# Usage function
usage() {
    echo "Usage: $0 INPUT_DIR OUTPUT_DIR [OPTIONS]"
    echo ""
    echo "Batch convert iSyntax files directly to pyramidal TIFF format"
    echo ""
    echo "Arguments:"
    echo "  INPUT_DIR              Directory containing .isyntax/.i2syntax files"
    echo "  OUTPUT_DIR             Directory for output .tiff files"
    echo ""
    echo "Options:"
    echo "  -j, --file-workers N   Number of files to process in parallel (default: $DEFAULT_FILE_WORKERS)"
    echo "  -w, --workers N        Number of worker threads per file (default: $DEFAULT_CONVERSION_WORKERS)"
    echo "  -t, --tile-size N      Tile size for processing (default: $DEFAULT_TILE_SIZE)"
    echo "  -c, --compression TYPE Compression: jpeg,lzw,deflate,none (default: $DEFAULT_COMPRESSION)"
    echo "  -q, --quality N        JPEG quality 1-100 (default: $DEFAULT_QUALITY)"
    echo "  --pyramid-512          Generate additional 512x512 tiled pyramid"
    echo "  --no-skip-existing     Process files even if output exists"
    echo "  --debug                Enable debug logging"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Basic batch conversion"
    echo "  $0 /path/to/isyntax/files /path/to/output"
    echo ""
    echo "  # High-performance conversion with 4 parallel files"
    echo "  $0 /path/to/isyntax/files /path/to/output --file-workers 4 --workers 8"
    echo ""
    echo "  # Generate both 1024 and 512 pyramids"
    echo "  $0 /path/to/isyntax/files /path/to/output --pyramid-512"
    echo ""
    echo "Performance Tips:"
    echo "  - Use --file-workers based on available CPU cores and memory"
    echo "  - Increase --workers for faster per-file processing"
    echo "  - Use SSD storage for input/output directories"
    echo "  - Monitor system resources during conversion"
}

# Check for required arguments
if [ $# -lt 2 ]; then
    echo "Error: Missing required arguments"
    echo ""
    usage
    exit 1
fi

# Parse arguments
INPUT_DIR="$1"
OUTPUT_DIR="$2"
shift 2

# Default options
FILE_WORKERS=$DEFAULT_FILE_WORKERS
CONVERSION_WORKERS=$DEFAULT_CONVERSION_WORKERS
TILE_SIZE=$DEFAULT_TILE_SIZE
COMPRESSION=$DEFAULT_COMPRESSION
QUALITY=$DEFAULT_QUALITY
PYRAMID_512=""
NO_SKIP_EXISTING=""
DEBUG=""

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        -j|--file-workers)
            FILE_WORKERS="$2"
            shift 2
            ;;
        -w|--workers)
            CONVERSION_WORKERS="$2"
            shift 2
            ;;
        -t|--tile-size)
            TILE_SIZE="$2"
            shift 2
            ;;
        -c|--compression)
            COMPRESSION="$2"
            shift 2
            ;;
        -q|--quality)
            QUALITY="$2"
            shift 2
            ;;
        --pyramid-512)
            PYRAMID_512="--pyramid-512"
            shift
            ;;
        --no-skip-existing)
            NO_SKIP_EXISTING="--no-skip-existing"
            shift
            ;;
        --debug)
            DEBUG="--debug"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option $1"
            echo ""
            usage
            exit 1
            ;;
    esac
done

# Validate input directory
if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: Input directory does not exist: $INPUT_DIR"
    exit 1
fi

# Count iSyntax files
ISYNTAX_COUNT=$(find "$INPUT_DIR" -maxdepth 1 -name "*.isyntax" -o -name "*.i2syntax" | wc -l)
if [ $ISYNTAX_COUNT -eq 0 ]; then
    echo "Error: No iSyntax files found in $INPUT_DIR"
    exit 1
fi

# Show configuration
echo "========================================================"
echo "BATCH DIRECT iSYNTAX TO PYRAMIDAL TIFF CONVERSION"
echo "========================================================"
echo "Input directory:     $INPUT_DIR"
echo "Output directory:    $OUTPUT_DIR"
echo "Files to process:    $ISYNTAX_COUNT"
echo "File workers:        $FILE_WORKERS"
echo "Conversion workers:  $CONVERSION_WORKERS"
echo "Tile size:           ${TILE_SIZE}x${TILE_SIZE}"
echo "Compression:         $COMPRESSION (quality: $QUALITY)"
echo "512x512 pyramid:     $([ -n "$PYRAMID_512" ] && echo "Yes" || echo "No")"
echo "Skip existing:       $([ -n "$NO_SKIP_EXISTING" ] && echo "No" || echo "Yes")"
echo "========================================================"
echo ""

# Confirm before starting
read -p "Start batch conversion? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Conversion cancelled."
    exit 0
fi

# Record start time
START_TIME=$(date +%s)

# Run the batch conversion
python batch_direct_convert.py \
    "$INPUT_DIR" \
    "$OUTPUT_DIR" \
    --file-workers "$FILE_WORKERS" \
    --conversion-workers "$CONVERSION_WORKERS" \
    --tile-size "$TILE_SIZE" \
    --compression "$COMPRESSION" \
    --quality "$QUALITY" \
    $PYRAMID_512 \
    $NO_SKIP_EXISTING \
    $DEBUG

# Calculate total time
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))
TOTAL_MINUTES=$((TOTAL_TIME / 60))

echo ""
echo "========================================================"
echo "BATCH CONVERSION COMPLETED"
echo "========================================================"
echo "Total time: ${TOTAL_TIME}s (${TOTAL_MINUTES} minutes)"
echo "Output directory: $OUTPUT_DIR"
echo "Log file: batch_conversion.log"
echo "========================================================"