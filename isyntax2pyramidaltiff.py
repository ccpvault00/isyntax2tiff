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
                 batch_size=250, fill_color=255, compression="jpeg", quality=80, pyramid_512=False):
        """
        Initialize the converter
        
        Args:
            input_path: Path to input iSyntax file
            output_path: Path to output pyramidal TIFF file
            tile_size: Tile size for processing (default: 1024)
            max_workers: Maximum number of worker threads (default: 4)
            batch_size: Number of patches per batch (default: 250)
            fill_color: Background color for missing tiles (default: 255)
            compression: TIFF compression type (default: "jpeg")
            quality: JPEG quality 1-100 (default: 75)
            pyramid_512: Generate additional 512x512 tiled pyramid (default: False)
        """
        self.input_path = input_path
        self.output_path = output_path
        self.tile_size = tile_size
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.fill_color = fill_color
        self.compression = compression
        self.quality = quality
        self.pyramid_512 = pyramid_512
        
        # Validate input file exists
        import os
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Initialize Philips PixelEngine
        render_context = softwarerendercontext.SoftwareRenderContext()
        render_backend = softwarerenderbackend.SoftwareRenderBackend()
        
        self.pixel_engine = pixelengine.PixelEngine(render_backend, render_context)
        
        try:
            self.pixel_engine["in"].open(input_path, "ficom")
        except Exception as e:
            raise RuntimeError(f"Failed to open iSyntax file '{input_path}': {str(e)}")
            
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

    def extract_macro_image(self):
        """Extract macro image if available"""
        try:
            macro = self.find_image_type("MACROIMAGE")
            if macro is None:
                log.info("No macro image found")
                return None
                
            log.info("Extracting macro image...")
            
            # Get JPEG-compressed image data directly
            if self.sdk_v1:
                jpeg_data = macro.IMAGE_DATA
            else:
                jpeg_data = macro.image_data
            
            # Decompress JPEG data using PIL
            from PIL import Image
            from io import BytesIO
            
            img = Image.open(BytesIO(jpeg_data))
            width = img.width
            height = img.height
            
            log.info(f"Macro image dimensions: {width} x {height}")
            
            # Convert PIL image to numpy array
            img_rgb = img.convert('RGB')
            macro_array = np.array(img_rgb)
            
            # Create pyvips image
            flat_data = macro_array.flatten()
            macro_vips = pyvips.Image.new_from_memory(
                flat_data.tobytes(), width, height, 3, 'uchar'
            )
            
            log.info("Macro image extracted successfully")
            return macro_vips
                    
        except Exception as e:
            log.warning(f"Failed to extract macro image: {e}")
            
        return None

    def extract_label_image(self):
        """Extract label image if available"""
        try:
            label = self.find_image_type("LABELIMAGE")
            if label is None:
                log.info("No label image found")
                return None
                
            log.info("Extracting label image...")
            
            # Get JPEG-compressed image data directly
            if self.sdk_v1:
                jpeg_data = label.IMAGE_DATA
            else:
                jpeg_data = label.image_data
            
            # Decompress JPEG data using PIL
            from PIL import Image
            from io import BytesIO
            
            img = Image.open(BytesIO(jpeg_data))
            width = img.width
            height = img.height
            
            log.info(f"Label image dimensions: {width} x {height}")
            
            # Convert PIL image to numpy array
            img_rgb = img.convert('RGB')
            label_array = np.array(img_rgb)
            
            # Create pyvips image
            flat_data = label_array.flatten()
            label_vips = pyvips.Image.new_from_memory(
                flat_data.tobytes(), width, height, 3, 'uchar'
            )
            
            log.info("Label image extracted successfully")
            return label_vips
                    
        except Exception as e:
            log.warning(f"Failed to extract label image: {e}")
            
        return None

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
        
        # Extract macro and label images
        macro_image = self.extract_macro_image()
        label_image = self.extract_label_image()
        
        # Save as pyramidal TIFF
        log.info(f"Saving pyramidal TIFF: {self.output_path}")
        self.save_pyramidal_tiff(vips_image, macro_image, label_image)
        
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

    def save_pyramidal_tiff(self, vips_image, macro_image=None, label_image=None):
        """Save pyvips image as pyramidal TIFF with proper metadata and associated images"""
        
        # Set resolution metadata (pixels per unit)
        # Convert from micrometers to pixels per cm: 1cm = 10000µm
        pixels_per_cm_x = 10000.0 / self.pixel_size_x if self.pixel_size_x > 0 else 1.0
        pixels_per_cm_y = 10000.0 / self.pixel_size_y if self.pixel_size_y > 0 else 1.0
        
        # Set TIFF resolution metadata
        # pyvips will automatically set resolution metadata when saving TIFF
        # We'll pass it through the save parameters instead
        
        log.info(f"Setting pixel size metadata: {self.pixel_size_x} x {self.pixel_size_y} µm")
        log.info(f"Resolution: {pixels_per_cm_x:.2f} x {pixels_per_cm_y:.2f} pixels/cm")
        
        save_params = {
            'tile': True,
            'tile_width': self.tile_size,
            'tile_height': self.tile_size,
            'pyramid': True,
            'bigtiff': True,
            'xres': pixels_per_cm_x,  # Resolution in pixels/cm
            'yres': pixels_per_cm_y,  # Resolution in pixels/cm
            'resunit': 'cm'  # Resolution unit: centimeters
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
        
        # Prepare images for multi-page TIFF
        images_to_save = [vips_image]
        image_descriptions = ["WSI"]
        
        # Add macro image if available
        if macro_image is not None:
            images_to_save.append(macro_image)
            image_descriptions.append("MACRO")
            log.info("Adding macro image to TIFF")
        
        # Add label image if available
        if label_image is not None:
            images_to_save.append(label_image)
            image_descriptions.append("LABEL")
            log.info("Adding label image to TIFF")
        
        # Create multi-directory TIFF with embedded macro and label images
        if macro_image is not None or label_image is not None:
            log.info("Creating multi-directory TIFF with embedded associated images...")
            self.save_multi_directory_tiff(vips_image, macro_image, label_image, save_params)
        else:
            # Save simple pyramid if no associated images
            vips_image.tiffsave(self.output_path, **save_params)
        
        # Save additional 512x512 tiled pyramid if requested
        if self.pyramid_512:
            if self.output_path.endswith('.tiff'):
                output_512 = self.output_path.replace('.tiff', '_512.tiff')
            elif self.output_path.endswith('.tif'):
                output_512 = self.output_path.replace('.tif', '_512.tif')
            else:
                output_512 = self.output_path + '_512.tiff'
            save_params_512 = save_params.copy()
            save_params_512.update({
                'tile_width': 512,
                'tile_height': 512
            })
            
            log.info(f"Saving additional 512x512 pyramid: {output_512}")
            vips_image.tiffsave(output_512, **save_params_512)

    def save_multi_directory_tiff(self, vips_image, macro_image, label_image, save_params):
        """Save multi-directory TIFF with embedded macro and label images"""
        import tempfile
        import subprocess
        import os
        
        temp_files = []
        try:
            # Save main pyramid to temporary file
            with tempfile.NamedTemporaryFile(suffix='.tiff', delete=False) as tmp:
                main_temp = tmp.name
                temp_files.append(main_temp)
            vips_image.tiffsave(main_temp, **save_params)
            
            # Save macro image to temporary file if present
            macro_temp = None
            if macro_image is not None:
                with tempfile.NamedTemporaryFile(suffix='.tiff', delete=False) as tmp:
                    macro_temp = tmp.name
                    temp_files.append(macro_temp)
                
                # Use strip-based storage for associated images (like original TIFF)
                # Force strip mode by setting page_height to image height
                macro_params = {
                    'compression': 'jpeg',
                    'bigtiff': False,
                    'tile': False,
                    'page_height': macro_image.height,  # This should force strip mode
                    'properties': False  # Don't write properties to avoid extra metadata
                }
                if 'Q' in save_params:
                    macro_params['Q'] = save_params['Q']
                
                macro_image.tiffsave(macro_temp, **macro_params)
            
            # Save label image to temporary file if present
            label_temp = None
            if label_image is not None:
                with tempfile.NamedTemporaryFile(suffix='.tiff', delete=False) as tmp:
                    label_temp = tmp.name
                    temp_files.append(label_temp)
                
                # Use strip-based storage for associated images (like original TIFF)
                # Force strip mode by setting page_height to image height
                label_params = {
                    'compression': 'jpeg',
                    'bigtiff': False,
                    'tile': False,
                    'page_height': label_image.height,  # This should force strip mode
                    'properties': False  # Don't write properties to avoid extra metadata
                }
                if 'Q' in save_params:
                    label_params['Q'] = save_params['Q']
                
                label_image.tiffsave(label_temp, **label_params)
            
            # Use tiffcp to combine into multi-directory TIFF with increased memory limit
            tiffcp_cmd = ['tiffcp', '-m', '0']  # Set unlimited memory
            
            # Add main image first
            tiffcp_cmd.append(main_temp)
            
            # Add macro image if present
            if macro_temp is not None:
                tiffcp_cmd.append(macro_temp)
                log.info("Adding macro image to multi-directory TIFF")
            
            # Add label image if present  
            if label_temp is not None:
                tiffcp_cmd.append(label_temp)
                log.info("Adding label image to multi-directory TIFF")
            
            # Output file
            tiffcp_cmd.append(self.output_path)
            
            log.info(f"Combining with tiffcp: {' '.join(tiffcp_cmd[1:])}")
            result = subprocess.run(tiffcp_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                log.error(f"tiffcp failed: {result.stderr}")
                log.info("Falling back to main image only")
                # Copy main image as fallback
                import shutil
                shutil.copy2(main_temp, self.output_path)
            else:
                log.info("Multi-directory TIFF created successfully")
                
                # Fix Subfile Type for associated images using tiffset
                try:
                    # Count total directories to find associated images
                    tiffinfo_result = subprocess.run(['tiffinfo', self.output_path], 
                                                   capture_output=True, text=True)
                    if tiffinfo_result.returncode == 0:
                        directory_count = tiffinfo_result.stdout.count('TIFF directory')
                        
                        # Set SubfileType=1 (reduced-resolution) and ImageDescription for associated images
                        if macro_image is not None:
                            macro_dir = directory_count - (2 if label_image is not None else 1)
                            # Set SubfileType=1 (reduced-resolution)
                            subprocess.run(['tiffset', '-d', str(macro_dir), '-s', '254', '1', self.output_path],
                                         capture_output=True)
                            
                            # Calculate macro image metadata like the reference
                            # Reference: Macro -offset=(0,0)-pixelsize=(0.0315,0.0315)-rois=((0,0,24000,20998),(56000,0,24390,20000))
                            macro_pixel_size = self.pixel_size_x * (self.size_x / macro_image.width)
                            macro_desc = f"Macro -offset=(0,0)-pixelsize=({macro_pixel_size:.4f},{macro_pixel_size:.4f})-rois=((0,0,{self.size_x},{self.size_y}),({self.size_x},0,{macro_image.width},{macro_image.height}))"
                            
                            # Set ImageDescription for QuPath recognition
                            subprocess.run(['tiffset', '-d', str(macro_dir), '-s', '270', macro_desc, self.output_path],
                                         capture_output=True)
                            log.info(f"Set macro image (directory {macro_dir}) as associated image with metadata")
                            log.info(f"Macro metadata: {macro_desc}")
                        
                        if label_image is not None:
                            label_dir = directory_count - 1
                            # Set SubfileType=1 (reduced-resolution)
                            subprocess.run(['tiffset', '-d', str(label_dir), '-s', '254', '1', self.output_path],
                                         capture_output=True)
                            # Set ImageDescription for QuPath recognition
                            subprocess.run(['tiffset', '-d', str(label_dir), '-s', '270', 'Label', self.output_path],
                                         capture_output=True)
                            log.info(f"Set label image (directory {label_dir}) as associated image")
                
                except Exception as e:
                    log.warning(f"Failed to set Subfile Type tags: {e}")
                
        except Exception as e:
            log.error(f"Failed to create multi-directory TIFF: {e}")
            log.info("Falling back to main image only")
            # Fallback to simple save
            vips_image.tiffsave(self.output_path, **save_params)
            
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except:
                    pass


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
    parser.add_argument('--fill-color', type=int, default=255,
                       help='Background color for missing tiles (default: 255)')
    parser.add_argument('--compression', choices=['jpeg', 'lzw', 'deflate', 'none'],
                       default='jpeg', help='TIFF compression type (default: jpeg)')
    parser.add_argument('--quality', type=int, default=75,
                       help='JPEG quality 1-100 (default: 75)')
    parser.add_argument('--pyramid-512', action='store_true',
                       help='Generate additional 512x512 tiled pyramid')
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
        quality=args.quality,
        pyramid_512=args.pyramid_512
    ) as converter:
        converter.convert()


if __name__ == '__main__':
    main()