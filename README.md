# iSyntax2TIFF Converter

A tool for converting Philips iSyntax whole slide images to pyramidal TIFF format, with support for both direct conversion and pipeline processing.

## Overview

This tool provides two conversion approaches:

###  **Direct Conversion**
- **`isyntax2pyramidaltiff.py`** - Single-step conversion: iSyntax → Pyramidal TIFF
- **Eliminates 40GB+ intermediate files** (no zarr/OME-TIFF storage)
- **QuPath/OpenSlide compatible** - Aperio TIFF format with proper macro/label detection
- **Proper metadata** with accurate pixel size resolution and XML embedding
- **Dual pyramid support** (1024x1024 and 512x512 tile options)

###  **Traditional Pipeline**
1. Convert iSyntax (.isyntax/.i2syntax) files to Zarr format
2. Convert Zarr to OME-TIFF format  
3. Generate pyramidal TIFF files from OME-TIFF
4. Process files locally or in batch using SLURM workload manager

## Setup Options

### Option 1: Local Setup (Recommended for Individual Use)

For running on a local Ubuntu 24.04 system without SLURM:

**Quick Setup:**
```bash
# 1. Clone repository with submodules
git clone --recursive https://github.com/your-username/isyntax2tiff.git
cd isyntax2tiff

# 2. Create conda environment
mamba create -n isyntax2tiff python=3.8 -y
mamba activate isyntax2tiff

# 3. Install dependencies
mamba install -c conda-forge libvips pyvips blosc tinyxml openssl=1.1.1 pillow -y
mamba install -c ome raw2ometiff -y

# 4. Install isyntax2raw from submodule
cd isyntax2raw && pip install . && cd ..
```

**Prerequisites:**
- Ubuntu 24.04 (or similar Linux distribution)
- Miniforge/Miniconda/Anaconda
- Philips PathologySDK (downloaded from Philips Knowledge Center)

**Note for existing repositories:**
If you already cloned the repository, initialize the submodule:
```bash
git submodule update --init --recursive
```

**Detailed Setup:**
See [`local_setup_files_for_ubuntu24.04/setup_philipsSDK_locally.md`](./local_setup_files_for_ubuntu24.04/setup_philipsSDK_locally.md) for complete installation instructions including PathologySDK setup.

### Option 2: HPC Cluster Setup (Original OSC Setup)

For running on HPC systems with SLURM:

**Prerequisites:**
- SLURM workload management system
- Required environment dependencies (see [Environment Setup](#hpc-environment-setup))

**Setup:**
Please follow the installation instructions in the [`environment_installment`](./environment_installment/) folder to set up all required dependencies.

## Usage

### Direct Conversion 

Convert iSyntax files directly to pyramidal TIFF with a single command:

```bash
# Activate your environment
mamba activate isyntax2tiff

# Basic conversion
python isyntax2pyramidaltiff.py input.isyntax output.tiff

# High-performance conversion with optimal settings
python isyntax2pyramidaltiff.py input.isyntax output.tiff \
    --tile-size 1024 \
    --max-workers 8 \
    --compression jpeg \
    --quality 75

# Generate both 1024x1024 and 512x512 tiled pyramids
python isyntax2pyramidaltiff.py input.isyntax output.tiff \
    --pyramid-512 \
    --max-workers 8
```

**Features:**
- ✅ **Single output file**: `output.tiff` (pyramidal TIFF ready for viewers)
- ✅ **Correct metadata**: Accurate pixel size resolution embedded
- ✅ **Fast processing**: ~5 minutes for typical whole slide images
- ✅ **Memory efficient**: Processes large images without excessive RAM usage
- ✅ **Configurable**: Adjustable compression, quality, tile sizes, and parallelization

### Batch Direct Conversion

Process multiple iSyntax files efficiently with parallel processing:

```bash
# Basic batch conversion (1-step direct)
./batchrun_local_1step.sh /path/to/isyntax/directory /path/to/output/directory

# High-performance batch conversion
./batchrun_local_1step.sh /path/to/isyntax/files /path/to/output \
    --file-workers 4 \
    --workers 8 \
    --pyramid-512

# Advanced Python interface
python batch_direct_convert.py /path/to/isyntax /path/to/output \
    --file-workers 2 \
    --conversion-workers 8 \
    --tile-size 1024 \
    --compression jpeg \
    --quality 75 \
    --pyramid-512
```

**Batch Features:**
- ✅ **Parallel file processing**: Process multiple files simultaneously
- ✅ **Progress tracking**: Real-time progress and logging
- ✅ **Resume capability**: Skip already converted files
- ✅ **Error handling**: Continue processing if individual files fail
- ✅ **Performance optimization**: Configurable parallelization levels
- ✅ **Comprehensive logging**: Detailed conversion logs and statistics

### Traditional Pipeline

Process files using the traditional 3-step conversion:

```bash
# Activate your environment
mamba activate isyntax2tiff

# Single file conversion (3-step pipeline)
./batchrun_local.sh /path/to/your/file.isyntax

# Batch directory conversion (3-step pipeline with parallelization)
./batchrun_local.sh /path/to/isyntax/directory /path/to/output 4

# Full usage: input, output_dir, parallel_jobs
./batchrun_local.sh /path/to/isyntax/files ./outputs 8
```

**Features:**
- ✅ **Flexible input**: Single files or directories
- ✅ **Configurable parallelization**: Default 4 jobs, customizable
- ✅ **Progress tracking**: Timestamped logging
- ✅ **Error handling**: Per-file error reporting

This creates three output files per input:
- `filename.zarr` - Raw tile data (25GB)
- `filename.ome.tiff` - OME-TIFF format (15GB)  
- `filename.tiff` - Pyramidal TIFF for viewers (2.8GB)

### HPC Usage (Batch Processing)

#### 1. Generate Input File List

Create a list of iSyntax files to process:

```bash
find /path/to/isyntax/folder -maxdepth 1 -type f -name "*.i2syntax" | sort > input_list.txt
```

Replace `/path/to/isyntax/folder` with the actual path to your iSyntax files.

#### 2. Convert iSyntax to OME-TIFF

1. Open `batchrun.sh` and adjust the array job parameters in line 10 to match your number of files
2. Submit the batch job:
   ```bash
   sbatch batchrun.sh
   ```

#### 3. Convert OME-TIFF to Pyramidal TIFF

Submit the conversion job:
```bash
sbatch batchrun_ome2pyramidal.sh
```

Note: Integration of steps 2 and 3 into a single workflow is planned for future updates.

## File Structure

### Core Conversion Tools
- **`isyntax2pyramidaltiff.py`** - 🚀 **Direct converter** (single-step iSyntax → Pyramidal TIFF)
- **`batch_direct_convert.py`** - 🚀 **Batch direct converter** (parallel processing of multiple files)  
- **`batchrun_local_1step.sh`** - 🚀 **Batch converter wrapper** (easy-to-use shell interface for direct conversion)
- `ome2pyramidaltiff.py` - Pyramidal TIFF conversion utility (optimized for traditional pipeline)

### Local Batch Processing
- **`batchrun_local.sh`** - 3-step pipeline with parallelization (iSyntax → Zarr → OME-TIFF → Pyramidal TIFF)

### Dependencies
- `isyntax2raw/` - Git submodule linking to official Glencoe Software repository

### Setup Files
- `local_setup_files_for_ubuntu24.04/` - Local setup documentation and scripts
- `environment_installment/` - HPC environment setup instructions and scripts

### HPC Batch Processing
- `batchrun.sh` - SLURM script for iSyntax to OME-TIFF conversion (2-step pipeline)
- `batchrun_ome2pyramidal.sh` - SLURM script for OME-TIFF to pyramidal TIFF conversion
- `batchrun_deprecated.sh` - **DEPRECATED** older SLURM script (do not use)
- `run.sh` - Single file SLURM processing example

## Command Line Options

### `isyntax2pyramidaltiff.py` Options

```
usage: isyntax2pyramidaltiff.py [-h] [--tile-size TILE_SIZE] [--max-workers MAX_WORKERS]
                                [--batch-size BATCH_SIZE] [--fill-color FILL_COLOR]
                                [--compression {jpeg,lzw,deflate,none}] [--quality QUALITY]
                                [--pyramid-512] [--debug]
                                input output

positional arguments:
  input                 Input iSyntax file path
  output                Output pyramidal TIFF file path

optional arguments:
  --tile-size TILE_SIZE     Tile size for processing (default: 1024)
  --max-workers MAX_WORKERS Maximum number of worker threads (default: 4)
  --batch-size BATCH_SIZE   Number of patches per batch (default: 250)
  --fill-color FILL_COLOR   Background color for missing tiles (default: 0)
  --compression {jpeg,lzw,deflate,none}
                           TIFF compression type (default: jpeg)
  --quality QUALITY        JPEG quality 1-100 (default: 75)
  --pyramid-512           Generate additional 512x512 tiled pyramid
  --debug                 Enable debug logging
```

### `batch_direct_convert.py` Options

```
usage: batch_direct_convert.py [-h] [--file-workers FILE_WORKERS]
                               [--conversion-workers CONVERSION_WORKERS]
                               [--tile-size TILE_SIZE] [--batch-size BATCH_SIZE]
                               [--compression {jpeg,lzw,deflate,none}] [--quality QUALITY]
                               [--pyramid-512] [--extensions EXTENSIONS [EXTENSIONS ...]]
                               [--no-skip-existing] [--debug]
                               input_dir output_dir

positional arguments:
  input_dir             Input directory containing iSyntax files
  output_dir            Output directory for pyramidal TIFF files

optional arguments:
  --file-workers FILE_WORKERS    Number of files to process in parallel (default: 2)
  --conversion-workers CONVERSION_WORKERS
                                Number of worker threads per file (default: 4)
  --tile-size TILE_SIZE         Tile size for processing (default: 1024)
  --batch-size BATCH_SIZE       Number of patches per batch (default: 250)
  --compression {jpeg,lzw,deflate,none}
                                TIFF compression type (default: jpeg)
  --quality QUALITY             JPEG quality 1-100 (default: 75)
  --pyramid-512                Generate additional 512x512 tiled pyramid
  --extensions EXTENSIONS       File extensions to process (default: .isyntax .i2syntax)
  --no-skip-existing           Process files even if output already exists
  --debug                      Enable debug logging
```

### `batchrun_local_1step.sh` Options

```
Usage: batchrun_local_1step.sh INPUT_DIR OUTPUT_DIR [OPTIONS]

Options:
  -j, --file-workers N   Number of files to process in parallel (default: 2)
  -w, --workers N        Number of worker threads per file (default: 8)
  -t, --tile-size N      Tile size for processing (default: 1024)
  -c, --compression TYPE Compression: jpeg,lzw,deflate,none (default: jpeg)
  -q, --quality N        JPEG quality 1-100 (default: 75)
  --pyramid-512          Generate additional 512x512 tiled pyramid
  --no-skip-existing     Process files even if output exists
  --debug                Enable debug logging
  -h, --help             Show help message
```

### `batchrun_local.sh` Options

```
Usage: batchrun_local.sh <input_dir_or_file> [output_dir] [parallel_jobs]

Arguments:
  input_dir_or_file  : Path to .isyntax file or directory containing .isyntax files
  output_dir         : Output directory (default: ./outputs)
  parallel_jobs      : Number of parallel jobs (default: 4)

Examples:
  batchrun_local.sh input.isyntax
  batchrun_local.sh ./input_dir
  batchrun_local.sh ./input_dir ./my_outputs
  batchrun_local.sh ./input_dir ./my_outputs 8
```

## Contributing

Feel free to submit issues and enhancement requests.
