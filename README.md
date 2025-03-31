# iSyntax2TIFF Converter

A tool for converting Philips iSyntax whole slide images to TIFF format, with support for batch processing and pyramidal TIFF generation.

## Overview

This tool provides functionality to:
1. Convert iSyntax (.i2syntax) files to OME-TIFF format
2. Generate pyramidal TIFF files from OME-TIFF
3. Process multiple files in batch using SLURM workload manager

## Prerequisites

- SLURM workload management system
- Required environment dependencies (see [Environment Setup](#environment-setup))

## Environment Setup

Please follow the installation instructions in the [`environment_installment`](./environment_installment/) folder to set up all required dependencies.

## Usage

### 1. Generate Input File List

Create a list of iSyntax files to process:

```bash
find /path/to/isyntax/folder -maxdepth 1 -type f -name "*.i2syntax" | sort > input_list.txt
```

Replace `/path/to/isyntax/folder` with the actual path to your iSyntax files.

### 2. Convert iSyntax to OME-TIFF

1. Open `batchrun.sh` and adjust the array job parameters in line 10 to match your number of files
2. Submit the batch job:
   ```bash
   sbatch batchrun.sh
   ```

### 3. Convert OME-TIFF to Pyramidal TIFF

Submit the conversion job:
```bash
sbatch batchrun_ome2pyramidal.sh
```

Note: Integration of steps 2 and 3 into a single workflow is planned for future updates.

## File Structure

- `batchrun.sh` - SLURM script for iSyntax to OME-TIFF conversion
- `batchrun_ome2pyramidal.sh` - SLURM script for OME-TIFF to pyramidal TIFF conversion
- `environment_installment/` - Environment setup instructions and scripts

## Contributing

Feel free to submit issues and enhancement requests.

## License

[Specify your license here]