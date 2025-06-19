# iSyntax2TIFF Converter

A high-performance tool for converting Philips iSyntax whole slide images to pyramidal TIFF format, with support for both direct conversion and traditional pipeline processing.

## Overview

This tool provides two conversion approaches:

### 🚀 **Direct Conversion (Recommended)**
- **`isyntax2pyramidaltiff.py`** - Single-step conversion: iSyntax → Pyramidal TIFF
- **8x faster** than traditional pipeline (~5 minutes vs 45+ minutes)
- **Eliminates 40GB+ intermediate files** (no zarr/OME-TIFF storage)
- **Proper metadata** with accurate pixel size resolution
- **Dual pyramid support** (1024x1024 and 512x512 tile options)

### 📁 **Traditional Pipeline**
1. Convert iSyntax (.isyntax/.i2syntax) files to OME-TIFF format
2. Generate pyramidal TIFF files from OME-TIFF  
3. Process files locally or in batch using SLURM workload manager

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

### 🚀 Direct Conversion (Recommended)

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

### 📁 Traditional Pipeline (Legacy)

Process individual files using the traditional 3-step conversion:

```bash
# Activate your environment
mamba activate isyntax2tiff

# Convert using traditional pipeline
./local_convert.sh /path/to/your/file.isyntax
```

This creates three output files in the `outputs/` directory:
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
- `ome2pyramidaltiff.py` - Pyramidal TIFF conversion utility (optimized for traditional pipeline)

### Traditional Pipeline
- `local_convert.sh` - Traditional 3-step conversion script

### Setup Files
- `local_setup_files_for_ubuntu24.04/` - Local setup documentation and scripts
- `environment_installment/` - HPC environment setup instructions and scripts

### HPC Batch Processing
- `batchrun.sh` - SLURM script for iSyntax to OME-TIFF conversion
- `batchrun_ome2pyramidal.sh` - SLURM script for OME-TIFF to pyramidal TIFF conversion

## Performance Comparison

| Method | Time | Intermediate Files | Output Quality | Recommended |
|--------|------|-------------------|----------------|-------------|
| **Direct Conversion** | ~5 min | None | Excellent | ✅ **Yes** |
| Traditional Pipeline | ~45+ min | 40GB+ (zarr + OME-TIFF) | Good | ❌ Legacy only |

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

## Contributing

Feel free to submit issues and enhancement requests.

## License

[Specify your license here]