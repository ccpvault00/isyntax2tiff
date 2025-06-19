#!/usr/bin/env python3
"""
Batch Direct iSyntax to Pyramidal TIFF Converter

This script processes multiple iSyntax files in parallel using the direct conversion approach.
It automatically discovers iSyntax files in a directory and processes them efficiently.

Features:
- Parallel processing of multiple files
- Progress tracking and logging
- Error handling and recovery
- Configurable conversion parameters
- Resume capability for interrupted batches
"""

import argparse
import concurrent.futures
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Import the direct converter
from isyntax2pyramidaltiff import ISyntax2PyramidalTIFF

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s [%(name)16s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_conversion.log')
    ]
)
log = logging.getLogger(__name__)


def find_isyntax_files(input_dir: Path, extensions: List[str] = None) -> List[Path]:
    """Find all iSyntax files in the input directory"""
    if extensions is None:
        extensions = ['.isyntax', '.i2syntax']
    
    isyntax_files = []
    for ext in extensions:
        pattern = f"*{ext}"
        files = list(input_dir.glob(pattern))
        isyntax_files.extend(files)
    
    return sorted(isyntax_files)


def generate_output_path(input_file: Path, output_dir: Path, suffix: str = "") -> Path:
    """Generate output path for converted file"""
    # Clean filename to avoid issues with special characters
    clean_stem = input_file.stem
    
    # Replace problematic characters that might cause file system issues
    # Note: The original filename S114-99047-A-PAX8(MRQ50) becomes S114-99047-A-PAX8_MRQ50_
    problematic_chars = ['(', ')', '[', ']', '{', '}', '<', '>', '|', '&', ';', '*', '?', '"', "'", ' ']
    for char in problematic_chars:
        clean_stem = clean_stem.replace(char, '_')
    
    # Remove multiple consecutive underscores
    import re
    clean_stem = re.sub(r'_+', '_', clean_stem)
    clean_stem = clean_stem.strip('_')
    
    output_name = clean_stem + suffix + ".tiff"
    return output_dir / output_name


def convert_single_file(
    input_file: Path,
    output_file: Path,
    tile_size: int = 1024,
    max_workers: int = 4,
    batch_size: int = 250,
    compression: str = "jpeg",
    quality: int = 75,
    pyramid_512: bool = False,
    skip_existing: bool = True
) -> Tuple[bool, str, float]:
    """
    Convert a single iSyntax file to pyramidal TIFF
    
    Returns:
        Tuple of (success, message, duration_seconds)
    """
    start_time = time.time()
    
    try:
        # Check if output already exists
        if skip_existing and output_file.exists():
            duration = time.time() - start_time
            return True, f"Skipped (already exists): {output_file.name}", duration
        
        # Create output directory if needed
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert the file
        try:
            with ISyntax2PyramidalTIFF(
                str(input_file), str(output_file),
                tile_size=tile_size,
                max_workers=max_workers,
                batch_size=batch_size,
                compression=compression,
                quality=quality,
                pyramid_512=pyramid_512
            ) as converter:
                converter.convert()
        except Exception as e:
            # Re-raise the exception to be handled by the caller
            raise RuntimeError(f"Conversion failed for {input_file.name}: {str(e)}") from e
        
        duration = time.time() - start_time
        return True, f"Converted successfully: {output_file.name}", duration
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Failed to convert {input_file.name}: {str(e)}"
        return False, error_msg, duration


def process_file_wrapper(args):
    """Wrapper function for multiprocessing"""
    input_file, output_file, config = args
    
    log.info(f"Starting conversion: {input_file.name}")
    success, message, duration = convert_single_file(
        input_file, output_file, **config
    )
    
    if success:
        log.info(f"✅ {message} ({duration:.1f}s)")
    else:
        log.error(f"❌ {message} ({duration:.1f}s)")
    
    return {
        'input_file': input_file,
        'output_file': output_file,
        'success': success,
        'message': message,
        'duration': duration
    }


def batch_convert(
    input_dir: Path,
    output_dir: Path,
    file_workers: int = 2,
    tile_size: int = 1024,
    conversion_workers: int = 4,
    batch_size: int = 250,
    compression: str = "jpeg",
    quality: int = 75,
    pyramid_512: bool = False,
    skip_existing: bool = True,
    extensions: List[str] = None
):
    """
    Batch convert multiple iSyntax files to pyramidal TIFF
    
    Args:
        input_dir: Directory containing iSyntax files
        output_dir: Directory for output TIFF files
        file_workers: Number of files to process in parallel
        tile_size: Tile size for processing
        conversion_workers: Number of worker threads per file conversion
        batch_size: Number of patches per batch
        compression: TIFF compression type
        quality: JPEG quality (1-100)
        pyramid_512: Generate additional 512x512 pyramid
        skip_existing: Skip files that already exist in output
        extensions: List of file extensions to process
    """
    
    log.info("=" * 60)
    log.info("BATCH DIRECT iSYNTAX TO PYRAMIDAL TIFF CONVERSION")
    log.info("=" * 60)
    
    # Find input files
    log.info(f"Scanning input directory: {input_dir}")
    isyntax_files = find_isyntax_files(input_dir, extensions)
    
    if not isyntax_files:
        log.error(f"No iSyntax files found in {input_dir}")
        return
    
    log.info(f"Found {len(isyntax_files)} iSyntax files to process")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Output directory: {output_dir}")
    
    # Prepare conversion tasks
    conversion_config = {
        'tile_size': tile_size,
        'max_workers': conversion_workers,
        'batch_size': batch_size,
        'compression': compression,
        'quality': quality,
        'pyramid_512': pyramid_512,
        'skip_existing': skip_existing
    }
    
    tasks = []
    for input_file in isyntax_files:
        output_file = generate_output_path(input_file, output_dir)
        tasks.append((input_file, output_file, conversion_config))
    
    log.info(f"Configuration:")
    log.info(f"  File workers: {file_workers}")
    log.info(f"  Conversion workers per file: {conversion_workers}")
    log.info(f"  Tile size: {tile_size}x{tile_size}")
    log.info(f"  Compression: {compression} (quality: {quality})")
    log.info(f"  512x512 pyramid: {pyramid_512}")
    log.info(f"  Skip existing: {skip_existing}")
    
    # Process files
    start_time = time.time()
    results = []
    
    log.info(f"Starting batch conversion of {len(tasks)} files...")
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=file_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(process_file_wrapper, task): task 
            for task in tasks
        }
        
        # Process completed tasks
        for future in concurrent.futures.as_completed(future_to_task):
            try:
                result = future.result()
                results.append(result)
                
                completed = len(results)
                total = len(tasks)
                progress = (completed / total) * 100
                
                log.info(f"Progress: {completed}/{total} ({progress:.1f}%)")
                
            except Exception as e:
                task = future_to_task[future]
                input_file = task[0]
                log.error(f"Task failed for {input_file.name}: {e}")
                
                results.append({
                    'input_file': input_file,
                    'output_file': task[1],
                    'success': False,
                    'message': f"Task execution failed: {e}",
                    'duration': 0
                })
    
    # Summary
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    total_conversion_time = sum(r['duration'] for r in results)
    
    log.info("=" * 60)
    log.info("BATCH CONVERSION SUMMARY")
    log.info("=" * 60)
    log.info(f"Total files processed: {len(results)}")
    log.info(f"Successful conversions: {successful}")
    log.info(f"Failed conversions: {failed}")
    log.info(f"Total wall time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    log.info(f"Total conversion time: {total_conversion_time:.1f}s ({total_conversion_time/60:.1f} minutes)")
    log.info(f"Average time per file: {total_conversion_time/len(results):.1f}s")
    log.info(f"Efficiency: {(total_conversion_time/total_time)*100:.1f}% (parallel speedup)")
    
    if failed > 0:
        log.info("\nFailed conversions:")
        for result in results:
            if not result['success']:
                log.info(f"  ❌ {result['input_file'].name}: {result['message']}")
    
    log.info(f"\nLog file: batch_conversion.log")
    log.info("Batch conversion completed!")


def main():
    parser = argparse.ArgumentParser(
        description='Batch convert iSyntax files directly to pyramidal TIFF',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Required arguments
    parser.add_argument('input_dir', type=Path,
                       help='Input directory containing iSyntax files')
    parser.add_argument('output_dir', type=Path,
                       help='Output directory for pyramidal TIFF files')
    
    # Processing options
    parser.add_argument('--file-workers', type=int, default=2,
                       help='Number of files to process in parallel')
    parser.add_argument('--conversion-workers', type=int, default=4,
                       help='Number of worker threads per file conversion')
    
    # Conversion options
    parser.add_argument('--tile-size', type=int, default=1024,
                       help='Tile size for processing')
    parser.add_argument('--batch-size', type=int, default=250,
                       help='Number of patches per batch')
    parser.add_argument('--compression', choices=['jpeg', 'lzw', 'deflate', 'none'],
                       default='jpeg', help='TIFF compression type')
    parser.add_argument('--quality', type=int, default=75,
                       help='JPEG quality 1-100')
    parser.add_argument('--pyramid-512', action='store_true',
                       help='Generate additional 512x512 tiled pyramid')
    
    # Processing options
    parser.add_argument('--extensions', nargs='+', default=['.isyntax', '.i2syntax'],
                       help='File extensions to process')
    parser.add_argument('--no-skip-existing', action='store_true',
                       help='Process files even if output already exists')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate input directory
    if not args.input_dir.exists():
        log.error(f"Input directory does not exist: {args.input_dir}")
        sys.exit(1)
    
    if not args.input_dir.is_dir():
        log.error(f"Input path is not a directory: {args.input_dir}")
        sys.exit(1)
    
    # Run batch conversion
    batch_convert(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        file_workers=args.file_workers,
        tile_size=args.tile_size,
        conversion_workers=args.conversion_workers,
        batch_size=args.batch_size,
        compression=args.compression,
        quality=args.quality,
        pyramid_512=args.pyramid_512,
        skip_existing=not args.no_skip_existing,
        extensions=args.extensions
    )


if __name__ == '__main__':
    main()