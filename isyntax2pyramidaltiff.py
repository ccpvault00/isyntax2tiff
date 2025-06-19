#!/usr/bin/env python3
"""
isyntax2pyramidaltiff - Direct iSyntax to Pyramidal TIFF converter

This tool converts Philips iSyntax whole slide images directly to pyramidal TIFF format,
bypassing the traditional iSyntax → Zarr → OME-TIFF → Pyramidal TIFF pipeline.

Based on isyntax2raw by Glencoe Software, with pyvips for pyramidal TIFF generation.

Copyright (c) 2025
"""

import argparse
import logging
import math
import numpy as np
import pyvips
import pixelengine
import softwarerendercontext
import softwarerenderbackend
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from threading import BoundedSemaphore
from datetime import datetime
from dateutil.parser import parse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s [%(name)16s] (%(thread)10s) %(message)s"
)
log = logging.getLogger(__name__)

class MaxQueuePool(object):
    """Bounded queue thread pool executor from isyntax2raw"""
    def __init__(self, executor, max_queue_size, max_workers=None):
        if max_workers is None:
            max_workers = max_queue_size
        self.pool = executor(max_workers=max_workers)
        self.pool_queue = BoundedSemaphore(max_queue_size)

    def submit(self, function, *args, **kwargs):
        self.pool_queue.acquire()
        future = self.pool.submit(function, *args, **kwargs)
        future.add_done_callback(self.pool_queue_callback)
        return future

    def pool_queue_callback(self, _):
        self.pool_queue.release()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.pool.__exit__(exception_type, exception_value, traceback)


class ISyntax2PyramidalTIFF:
    """Direct iSyntax to Pyramidal TIFF converter"""
    
    def __init__(self, input_path, output_path, tile_size=1024, max_workers=4, 
                 batch_size=250, fill_color=0, compression="jpeg", quality=80):
        """
        Initialize the converter
        
        Args:
            input_path: Path to input iSyntax file
            output_path: Path to output pyramidal TIFF file
            tile_size: Tile size for processing (default: 1024)
            max_workers: Maximum number of worker threads (default: 4)
            batch_size: Number of patches per batch (default: 250)
            fill_color: Background color for missing tiles (default: 0)
            compression: TIFF compression type (default: "jpeg")
            quality: JPEG quality 1-100 (default: 75)
        """
        self.input_path = input_path
        self.output_path = output_path
        self.tile_size = tile_size
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.fill_color = fill_color
        self.compression = compression
        self.quality = quality
        
        # Initialize Philips PixelEngine
        render_context = softwarerendercontext.SoftwareRenderContext()
        render_backend = softwarerenderbackend.SoftwareRenderBackend()
        
        self.pixel_engine = pixelengine.PixelEngine(render_backend, render_context)
        self.pixel_engine["in"].open(input_path, "ficom")
        self.sdk_v1 = hasattr(self.pixel_engine["in"], "BARCODE")
        
        log.info(f"Initialized PixelEngine for: {input_path}")
        log.info(f"SDK Version: {'v1' if self.sdk_v1 else 'v2'}")

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.pixel_engine["in"].close()

    def find_image_type(self, image_type):
        """Find image of specified type (WSI, LABELIMAGE, MACROIMAGE)"""
        pe_in = self.pixel_engine["in"]
        for index in range(self.num_images()):
            if image_type == self.image_type(index):
                return pe_in[index]
        return None

    def image_type(self, image_no):
        """Get image type for given image number"""
        pe_in = self.pixel_engine["in"]
        if self.sdk_v1:
            return pe_in[image_no].IMAGE_TYPE
        else:
            return pe_in[image_no].image_type

    def num_images(self):
        """Get total number of images in the file"""
        pe_in = self.pixel_engine["in"]
        if self.sdk_v1:
            return pe_in.numImages()
        else:
            return pe_in.num_images

    def num_derived_levels(self, image):
        """Get number of pyramid levels"""
        pe_in = self.pixel_engine["in"]
        if self.sdk_v1:
            return pe_in.numLevels()
        else:
            return image.source_view.num_derived_levels

    def dimension_ranges(self, image, resolution):
        """Get dimension ranges for specified resolution level"""
        pe_in = self.pixel_engine["in"]
        if self.sdk_v1:
            return pe_in.SourceView().dimensionRanges(resolution)
        else:
            return image.source_view.dimension_ranges(resolution)

    def data_envelopes(self, image, resolution):
        """Get data envelopes (scanned areas) for specified resolution"""
        pe_in = self.pixel_engine["in"]
        if self.sdk_v1:
            return pe_in.SourceView().dataEnvelopes(resolution)
        else:
            return image.source_view.data_envelopes(resolution)

    def wait_any(self, regions):
        """Wait for any regions to be ready"""
        if self.sdk_v1:
            return self.pixel_engine.waitAny(regions)
        else:
            return self.pixel_engine.wait_any(regions)

    def get_size(self, dim_range):
        """Calculate the length in pixels of a dimension"""
        v = (dim_range[2] - dim_range[0]) / dim_range[1]
        if not v.is_integer():
            raise ValueError(
                f'({dim_range[2]} - {dim_range[0]}) / {dim_range[1]} results in remainder!'
            )
        return int(v)

    def get_image_metadata(self):
        """Get metadata for WSI image"""
        image = self.find_image_type("WSI")
        if image is None:
            raise ValueError("No WSI image found in file")
            
        if self.sdk_v1:
            view = self.pixel_engine["in"].SourceView()
            dim_ranges = view.dimensionRanges(0)
        else:
            view = image.source_view
            dim_ranges = view.dimension_ranges(0)
            
        self.size_x = self.get_size(dim_ranges[0])
        self.size_y = self.get_size(dim_ranges[1])
        self.num_levels = self.num_derived_levels(image)
        
        if self.sdk_v1:
            scale_factor = image.IMAGE_SCALE_FACTOR
        else:
            scale_factor = view.scale
            
        self.pixel_size_x = scale_factor[0]
        self.pixel_size_y = scale_factor[1]
        
        log.info(f"Image dimensions: {self.size_x} x {self.size_y}")
        log.info(f"Pyramid levels: {self.num_levels}")
        log.info(f"Pixel size: {self.pixel_size_x} x {self.pixel_size_y} µm")
        
        return {
            'width': self.size_x,
            'height': self.size_y,
            'levels': self.num_levels,
            'pixel_size_x': self.pixel_size_x,
            'pixel_size_y': self.pixel_size_y
        }

    def make_planar(self, pixels, tile_width, tile_height):
        """Convert interleaved RGB to planar RGB format"""
        r = pixels[0::3]
        g = pixels[1::3]
        b = pixels[2::3]
        for v in (r, g, b):
            v.shape = (tile_height, tile_width)
        return np.array([r, g, b])

    def convert(self):
        """Convert iSyntax file to pyramidal TIFF"""
        log.info("Starting iSyntax to Pyramidal TIFF conversion...")
        
        # Get image metadata
        metadata = self.get_image_metadata()
        image = self.find_image_type("WSI")
        
        # Extract all tiles from full resolution (level 0)
        log.info("Extracting tiles from full resolution image...")
        image_array = self.extract_full_resolution_tiles(image)
        
        # Create pyvips image
        log.info("Creating pyvips image...")
        vips_image = self.create_vips_image(image_array)
        
        # Save as pyramidal TIFF
        log.info(f"Saving pyramidal TIFF: {self.output_path}")
        self.save_pyramidal_tiff(vips_image)
        
        log.info("Conversion completed successfully!")

    def extract_full_resolution_tiles(self, image):
        """Extract all tiles from full resolution level and assemble into single array"""
        
        # Get level 0 dimensions
        dim_ranges = self.dimension_ranges(image, 0)
        resolution_x_size = self.get_size(dim_ranges[0])
        resolution_y_size = self.get_size(dim_ranges[1])
        scale_x = dim_ranges[0][1]
        scale_y = dim_ranges[1][1]
        
        log.info(f"Full resolution: {resolution_x_size} x {resolution_y_size}")
        log.info(f"Scale factors: {scale_x} x {scale_y}")
        
        # Calculate number of tiles
        x_tiles = math.ceil(resolution_x_size / self.tile_size)
        y_tiles = math.ceil(resolution_y_size / self.tile_size)
        
        log.info(f"Processing {x_tiles} x {y_tiles} = {x_tiles * y_tiles} tiles")
        
        # Create output array
        output_array = np.zeros((resolution_y_size, resolution_x_size, 3), dtype=np.uint8)
        
        # Create patches for extraction
        patches, patch_ids = self.create_patch_list(
            dim_ranges, [x_tiles, y_tiles], [self.tile_size, self.tile_size]
        )
        
        envelopes = self.data_envelopes(image, 0)
        pe_in = self.pixel_engine["in"]
        
        # Process tiles in batches
        jobs = []
        with MaxQueuePool(ThreadPoolExecutor, self.max_workers) as pool:
            for i in range(0, len(patches), self.batch_size):
                batch_patches = patches[i:i + self.batch_size]
                batch_patch_ids = patch_ids[i:i + self.batch_size]
                
                if self.sdk_v1:
                    request_regions = pe_in.SourceView().requestRegions
                else:
                    request_regions = image.source_view.request_regions
                    
                regions = request_regions(
                    batch_patches, envelopes, True, [self.fill_color] * 3
                )
                
                while regions:
                    regions_ready = self.wait_any(regions)
                    
                    for region_index, region in enumerate(regions_ready):
                        view_range = region.range
                        x_start, x_end, y_start, y_end, level = view_range
                        
                        # Calculate actual tile dimensions
                        width = int(1 + (x_end - x_start) / scale_x)
                        height = int(1 + (y_end - y_start) / scale_y)
                        
                        # Get pixel data
                        pixel_buffer_size = width * height * 3
                        pixels = np.empty(pixel_buffer_size, dtype=np.uint8)
                        region.get(pixels)
                        
                        # Get patch position
                        patch_idx = regions.index(region)
                        patch_id = batch_patch_ids[patch_idx]
                        tile_x, tile_y = patch_id
                        
                        # Submit tile processing job
                        jobs.append(pool.submit(
                            self.process_tile, output_array, pixels, 
                            tile_x, tile_y, width, height, scale_x, scale_y
                        ))
                        
                        regions.remove(region)
                        batch_patch_ids.remove(patch_id)
        
        # Wait for all jobs to complete
        wait(jobs, return_when=ALL_COMPLETED)
        
        log.info("Tile extraction completed")
        return output_array

    def process_tile(self, output_array, pixels, tile_x, tile_y, width, height, scale_x, scale_y):
        """Process a single tile and place it in the output array"""
        try:
            # Convert to planar format and reshape
            planar_pixels = self.make_planar(pixels, width, height)
            
            # Convert to HWC format (Height, Width, Channels)
            tile_data = planar_pixels.transpose(1, 2, 0)
            
            # Calculate position in output array
            y_start = tile_y * self.tile_size
            x_start = tile_x * self.tile_size
            y_end = min(y_start + height, output_array.shape[0])
            x_end = min(x_start + width, output_array.shape[1])
            
            # Place tile in output array
            output_array[y_start:y_end, x_start:x_end, :] = tile_data[:y_end-y_start, :x_end-x_start, :]
            
        except Exception as e:
            log.error(f"Failed to process tile ({tile_x}, {tile_y}): {e}", exc_info=True)

    def create_patch_list(self, dim_ranges, tiles, tile_size):
        """Create list of patches to extract (adapted from isyntax2raw)"""
        resolution_x_end = dim_ranges[0][2]
        resolution_y_end = dim_ranges[1][2]
        origin_x = dim_ranges[0][0]
        origin_y = dim_ranges[1][0]
        tiles_x, tiles_y = tiles
        
        patches = []
        patch_ids = []
        scale_x = dim_ranges[0][1]
        scale_y = dim_ranges[1][1]
        
        level = math.log2(scale_x)
        if scale_x != scale_y or not level.is_integer():
            raise ValueError(f"scale_x={scale_x} scale_y={scale_y} do not match expectations!")
        level = int(level)
        
        tile_size_x = tile_size[0] * scale_x
        tile_size_y = tile_size[1] * scale_y
        
        for y in range(tiles_y):
            y_start = origin_y + (y * tile_size_y)
            y_end = min((y_start + tile_size_y) - scale_y, resolution_y_end - scale_y)
            
            for x in range(tiles_x):
                x_start = origin_x + (x * tile_size_x)
                x_end = min((x_start + tile_size_x) - scale_x, resolution_x_end - scale_x)
                
                patch = [x_start, x_end, y_start, y_end, level]
                patches.append(patch)
                patch_ids.append((x, y))
                
        return patches, patch_ids

    def create_vips_image(self, image_array):
        """Create pyvips image from numpy array"""
        height, width, channels = image_array.shape
        log.info(f"Creating pyvips image: {width} x {height} x {channels}")
        
        # Flatten array for pyvips
        flat_data = image_array.flatten()
        
        # Create pyvips image
        vips_image = pyvips.Image.new_from_memory(
            flat_data.tobytes(),
            width,
            height, 
            channels,
            'uchar'
        )
        
        return vips_image

    def save_pyramidal_tiff(self, vips_image):
        """Save pyvips image as pyramidal TIFF"""
        save_params = {
            'tile': True,
            'tile_width': self.tile_size,
            'tile_height': self.tile_size,
            'pyramid': True,
            'bigtiff': True
        }
        
        if self.compression.lower() == 'jpeg':
            save_params.update({
                'compression': 'jpeg',
                'Q': self.quality
            })
        elif self.compression.lower() == 'lzw':
            save_params.update({'compression': 'lzw'})
        elif self.compression.lower() == 'deflate':
            save_params.update({'compression': 'deflate'})
        else:
            save_params.update({'compression': 'none'})
            
        log.info(f"Saving with compression: {self.compression}")
        log.info(f"Tile size: {self.tile_size}x{self.tile_size}")
        
        vips_image.tiffsave(self.output_path, **save_params)


def main():
    parser = argparse.ArgumentParser(
        description='Convert iSyntax files directly to pyramidal TIFF'
    )
    parser.add_argument('input', help='Input iSyntax file path')
    parser.add_argument('output', help='Output pyramidal TIFF file path')
    parser.add_argument('--tile-size', type=int, default=1024,
                       help='Tile size for processing (default: 1024)')
    parser.add_argument('--max-workers', type=int, default=4,
                       help='Maximum number of worker threads (default: 4)')
    parser.add_argument('--batch-size', type=int, default=250,
                       help='Number of patches per batch (default: 250)')
    parser.add_argument('--fill-color', type=int, default=0,
                       help='Background color for missing tiles (default: 0)')
    parser.add_argument('--compression', choices=['jpeg', 'lzw', 'deflate', 'none'],
                       default='jpeg', help='TIFF compression type (default: jpeg)')
    parser.add_argument('--quality', type=int, default=75,
                       help='JPEG quality 1-100 (default: 75)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Convert the file
    with ISyntax2PyramidalTIFF(
        args.input, args.output,
        tile_size=args.tile_size,
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        fill_color=args.fill_color,
        compression=args.compression,
        quality=args.quality
    ) as converter:
        converter.convert()


if __name__ == '__main__':
    main()