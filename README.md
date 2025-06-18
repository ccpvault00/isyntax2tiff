# iSyntax2TIFF Converter

A tool for converting Philips iSyntax whole slide images to TIFF format, with support for both HPC cluster processing and local execution.

## Overview

This tool provides functionality to:
1. Convert iSyntax (.isyntax/.i2syntax) files to OME-TIFF format
2. Generate pyramidal TIFF files from OME-TIFF
3. Process files locally or in batch using SLURM workload manager

## Setup Options

### Option 1: Local Setup (Recommended for Individual Use)

For running on a local Ubuntu 24.04 system without SLURM:

**Quick Setup:**
```bash
# 1. Create conda environment
mamba create -n isyntax2tiff python=3.8 -y
mamba activate isyntax2tiff

# 2. Install dependencies
mamba install -c conda-forge libvips pyvips blosc tinyxml openssl=1.1.1 pillow -y
mamba install -c ome raw2ometiff -y

# 3. Install isyntax2raw
git clone https://github.com/glencoesoftware/isyntax2raw.git
cd isyntax2raw && pip install .
```

**Prerequisites:**
- Ubuntu 24.04 (or similar Linux distribution)
- Miniforge/Miniconda/Anaconda
- Philips PathologySDK (downloaded from Philips Knowledge Center)

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

### Local Usage (Single File Processing)

Process individual files using the local conversion script:

```bash
# Activate your environment
mamba activate isyntax2tiff

# Convert a single file
./local_convert.sh /path/to/your/file.isyntax
```

This will create three output files in the `outputs/` directory:
- `filename.zarr` - Raw tile data
- `filename.ome.tiff` - OME-TIFF format
- `filename.tiff` - Pyramidal TIFF for viewers

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

### Local Setup Files
- `local_convert.sh` - Local conversion script (non-SLURM)
- `ome2pyramidaltiff.py` - Pyramidal TIFF conversion utility
- `local_setup_files_for_ubuntu24.04/` - Local setup documentation and scripts

### HPC Setup Files
- `batchrun.sh` - SLURM script for iSyntax to OME-TIFF conversion
- `batchrun_ome2pyramidal.sh` - SLURM script for OME-TIFF to pyramidal TIFF conversion
- `environment_installment/` - HPC environment setup instructions and scripts

## Contributing

Feel free to submit issues and enhancement requests.

## License

[Specify your license here]