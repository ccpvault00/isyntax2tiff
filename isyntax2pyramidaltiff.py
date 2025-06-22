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
import base64
import os
import tifffile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s [%(name)16s] (%(thread)10s) %(message)s"
)
log = logging.getLogger(__name__)


class PhilipsXMLGenerator:
    """Generate Philips-compatible XML metadata for TIFF files."""
    
    def __init__(self):
        self.scanner_info = {
            "manufacturer": "PHILIPS",
            "device_serial": "FMT0411",
            "software_versions": ["1.8.6824", "20180906_R51", "4.0.3"],
            "rack_number": 11,
            "slot_number": 10,
            "calibration_status": "OK"
        }
        
    def generate_xml(self, 
                    source_filename: str,
                    wsi_info: dict,
                    pyramid_levels: list,
                    macro_image_data: str = None,
                    label_image_data: str = None) -> str:
        """Generate complete Philips XML metadata."""
        
        # Generate timestamps
        now = datetime.now()
        acquisition_datetime = now.strftime("%Y%m%d%H%M%S.%f")
        calibration_date = now.strftime("%Y%m%d")
        calibration_time = now.strftime("%H%M%S")
        
        xml_parts = []
        xml_parts.append('<?xml version="1.0" encoding="UTF-8" ?>')
        xml_parts.append('<DataObject ObjectType="DPUfsImport">')
        
        # Add DICOM header attributes
        xml_parts.extend(self._generate_dicom_header(
            acquisition_datetime, calibration_date, calibration_time
        ))
        
        # Add scanned images array
        xml_parts.append('\t<Attribute Name="PIM_DP_SCANNED_IMAGES" Group="0x301D" Element="0x1003" PMSVR="IDataObjectArray">')
        xml_parts.append('\t\t<Array>')
        
        # Add WSI image
        xml_parts.extend(self._generate_wsi_image(
            source_filename, wsi_info, pyramid_levels
        ))
        
        # Add macro image if provided
        if macro_image_data:
            xml_parts.extend(self._generate_associated_image(
                "MACROIMAGE", macro_image_data
            ))
        
        # Add label image if provided
        if label_image_data:
            xml_parts.extend(self._generate_associated_image(
                "LABELIMAGE", label_image_data
            ))
        
        xml_parts.append('\t\t</Array>')
        xml_parts.append('\t</Attribute>')
        
        # Add footer attributes
        xml_parts.extend(self._generate_footer_attributes())
        
        xml_parts.append('</DataObject>')
        
        return '\n'.join(xml_parts)
    
    def _generate_dicom_header(self, acquisition_datetime: str, 
                             calibration_date: str, calibration_time: str) -> list:
        """Generate DICOM header attributes."""
        return [
            f'\t<Attribute Name="DICOM_ACQUISITION_DATETIME" Group="0x0008" Element="0x002A" PMSVR="IString">{acquisition_datetime}</Attribute>',
            f'\t<Attribute Name="DICOM_DATE_OF_LAST_CALIBRATION" Group="0x0018" Element="0x1200" PMSVR="IStringArray">&quot;{calibration_date}&quot;</Attribute>',
            f'\t<Attribute Name="DICOM_DEVICE_SERIAL_NUMBER" Group="0x0018" Element="0x1000" PMSVR="IString">{self.scanner_info["device_serial"]}</Attribute>',
            f'\t<Attribute Name="DICOM_MANUFACTURER" Group="0x0008" Element="0x0070" PMSVR="IString">{self.scanner_info["manufacturer"]}</Attribute>',
            f'\t<Attribute Name="DICOM_SOFTWARE_VERSIONS" Group="0x0018" Element="0x1020" PMSVR="IStringArray">&quot;{self.scanner_info["software_versions"][0]}&quot; &quot;{self.scanner_info["software_versions"][1]}&quot; &quot;{self.scanner_info["software_versions"][2]}&quot;</Attribute>',
            f'\t<Attribute Name="DICOM_TIME_OF_LAST_CALIBRATION" Group="0x0018" Element="0x1201" PMSVR="IStringArray">&quot;{calibration_time}&quot;</Attribute>',
            f'\t<Attribute Name="PIIM_DP_SCANNER_CALIBRATION_STATUS" Group="0x101D" Element="0x100A" PMSVR="IString">{self.scanner_info["calibration_status"]}</Attribute>',
            f'\t<Attribute Name="PIIM_DP_SCANNER_RACK_NUMBER" Group="0x101D" Element="0x1007" PMSVR="IUInt16">{self.scanner_info["rack_number"]}</Attribute>',
            f'\t<Attribute Name="PIIM_DP_SCANNER_SLOT_NUMBER" Group="0x101D" Element="0x1008" PMSVR="IUInt16">{self.scanner_info["slot_number"]}</Attribute>',
        ]
    
    def _generate_wsi_image(self, source_filename: str, 
                          wsi_info: dict, 
                          pyramid_levels: list) -> list:
        """Generate WSI image XML."""
        
        pixel_spacing = wsi_info.get('pixel_spacing', 0.00025)
        width = wsi_info.get('width', 80896)
        height = wsi_info.get('height', 21504)
        
        xml_parts = []
        xml_parts.append('\t\t\t<DataObject ObjectType="DPScannedImage">')
        
        # Add derivation description
        derivation_desc = f'tiff-useBigTIFF=0-useRgb=0-levels={len(pyramid_levels)},10002,10000,10001-processing=0-q80-sourceFilename=&quot;{source_filename}&quot;;PHILIPS UFS V1.8.6824 | Quality=2 | DWT=1 | Compressor=16'
        xml_parts.append(f'\t\t\t\t<Attribute Name="DICOM_DERIVATION_DESCRIPTION" Group="0x0008" Element="0x2111" PMSVR="IString">{derivation_desc}</Attribute>')
        
        # Add compression info and image type
        xml_parts.extend([
            '\t\t\t\t<Attribute Name="DICOM_LOSSY_IMAGE_COMPRESSION_METHOD" Group="0x0028" Element="0x2114" PMSVR="IStringArray">&quot;PHILIPS_DP_1_0&quot; &quot;PHILIPS_TIFF_1_0&quot;</Attribute>',
            '\t\t\t\t<Attribute Name="DICOM_LOSSY_IMAGE_COMPRESSION_RATIO" Group="0x0028" Element="0x2112" PMSVR="IDoubleArray">&quot;3&quot; &quot;3&quot;</Attribute>',
            '\t\t\t\t<Attribute Name="PIM_DP_IMAGE_TYPE" Group="0x301D" Element="0x1004" PMSVR="IString">WSI</Attribute>',
            '\t\t\t\t<Attribute Name="UFS_IMAGE_PIXEL_TRANSFORMATION_METHOD" Group="0x301D" Element="0x2013" PMSVR="IString">0</Attribute>',
        ])
        
        # Add DICOM image attributes
        xml_parts.extend([
            '\t\t\t\t<Attribute Name="DICOM_BITS_ALLOCATED" Group="0x0028" Element="0x0100" PMSVR="IUInt16">8</Attribute>',
            '\t\t\t\t<Attribute Name="DICOM_BITS_STORED" Group="0x0028" Element="0x0101" PMSVR="IUInt16">8</Attribute>',
            '\t\t\t\t<Attribute Name="DICOM_HIGH_BIT" Group="0x0028" Element="0x0102" PMSVR="IUInt16">7</Attribute>',
            '\t\t\t\t<Attribute Name="DICOM_LOSSY_IMAGE_COMPRESSION" Group="0x0028" Element="0x2110" PMSVR="IString">01</Attribute>',
            '\t\t\t\t<Attribute Name="DICOM_PHOTOMETRIC_INTERPRETATION" Group="0x0028" Element="0x0004" PMSVR="IString">RGB</Attribute>',
            '\t\t\t\t<Attribute Name="DICOM_PIXEL_REPRESENTATION" Group="0x0028" Element="0x0103" PMSVR="IUInt16">0</Attribute>',
            f'\t\t\t\t<Attribute Name="DICOM_PIXEL_SPACING" Group="0x0028" Element="0x0030" PMSVR="IDoubleArray">&quot;{pixel_spacing}&quot; &quot;{pixel_spacing}&quot;</Attribute>',
            '\t\t\t\t<Attribute Name="DICOM_PLANAR_CONFIGURATION" Group="0x0028" Element="0x0006" PMSVR="IUInt16">0</Attribute>',
            '\t\t\t\t<Attribute Name="DICOM_SAMPLES_PER_PIXEL" Group="0x0028" Element="0x0002" PMSVR="IUInt16">3</Attribute>',
        ])
        
        # Add pixel data representation sequence
        xml_parts.append('\t\t\t\t<Attribute Name="PIIM_PIXEL_DATA_REPRESENTATION_SEQUENCE" Group="0x1001" Element="0x8B01" PMSVR="IDataObjectArray">')
        xml_parts.append('\t\t\t\t\t<Array>')
        
        for i, level in enumerate(pyramid_levels):
            level_pixel_spacing = pixel_spacing * (2 ** i)
            xml_parts.extend([
                '\t\t\t\t\t\t<DataObject ObjectType="PixelDataRepresentation">',
                f'\t\t\t\t\t\t\t<Attribute Name="DICOM_PIXEL_SPACING" Group="0x0028" Element="0x0030" PMSVR="IDoubleArray">&quot;{level_pixel_spacing}&quot; &quot;{level_pixel_spacing}&quot;</Attribute>',
                '\t\t\t\t\t\t\t<Attribute Name="PIIM_DP_PIXEL_DATA_REPRESENTATION_POSITION" Group="0x101D" Element="0x100B" PMSVR="IDoubleArray">&quot;0&quot; &quot;0&quot; &quot;0&quot;</Attribute>',
                f'\t\t\t\t\t\t\t<Attribute Name="PIIM_PIXEL_DATA_REPRESENTATION_COLUMNS" Group="0x2001" Element="0x115E" PMSVR="IUInt32">{level["width"]}</Attribute>',
                f'\t\t\t\t\t\t\t<Attribute Name="PIIM_PIXEL_DATA_REPRESENTATION_NUMBER" Group="0x1001" Element="0x8B02" PMSVR="IUInt16">{i}</Attribute>',
                f'\t\t\t\t\t\t\t<Attribute Name="PIIM_PIXEL_DATA_REPRESENTATION_ROWS" Group="0x2001" Element="0x115D" PMSVR="IUInt32">{level["height"]}</Attribute>',
                '\t\t\t\t\t\t</DataObject>',
            ])
        
        xml_parts.extend([
            '\t\t\t\t\t</Array>',
            '\t\t\t\t</Attribute>',
            f'\t\t\t\t<Attribute Name="PIM_DP_IMAGE_COLUMNS" Group="0x301D" Element="0x1007" PMSVR="IUInt32">{width}</Attribute>',
            f'\t\t\t\t<Attribute Name="PIM_DP_IMAGE_ROWS" Group="0x301D" Element="0x1006" PMSVR="IUInt32">{height}</Attribute>',
            '\t\t\t\t<Attribute Name="PIM_DP_SOURCE_FILE" Group="0x301D" Element="0x1000" PMSVR="IString">%FILENAME%</Attribute>',
            '\t\t\t</DataObject>',
        ])
        
        return xml_parts
    
    def _generate_associated_image(self, image_type: str, image_data: str) -> list:
        """Generate associated image (MACRO or LABEL) XML."""
        return [
            '\t\t\t<DataObject ObjectType="DPScannedImage">',
            f'\t\t\t\t<Attribute Name="PIM_DP_IMAGE_DATA" Group="0x301D" Element="0x1005" PMSVR="IString">{image_data}</Attribute>',
            f'\t\t\t\t<Attribute Name="PIM_DP_IMAGE_TYPE" Group="0x301D" Element="0x1004" PMSVR="IString">{image_type}</Attribute>',
            '\t\t\t</DataObject>',
        ]
    
    def _generate_footer_attributes(self) -> list:
        """Generate footer attributes."""
        return [
            '\t<Attribute Name="PIM_DP_UFS_BARCODE" Group="0x301D" Element="0x1002" PMSVR="IString">Generated</Attribute>',
            '\t<Attribute Name="PIM_DP_UFS_INTERFACE_VERSION" Group="0x301D" Element="0x1001" PMSVR="IString">1.8.6824</Attribute>',
        ]

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
        
        # Initialize XML generator
        self.xml_generator = PhilipsXMLGenerator()
        
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

    def vips_image_to_base64_jpeg(self, vips_image):
        """Convert a pyvips image to Base64-encoded JPEG string."""
        try:
            # Save as JPEG to memory buffer
            jpeg_buffer = vips_image.jpegsave_buffer(Q=self.quality)
            
            # Encode to Base64
            base64_data = base64.b64encode(jpeg_buffer).decode('utf-8')
            
            log.info(f"Converted image to Base64 JPEG ({len(base64_data)} chars)")
            return base64_data
            
        except Exception as e:
            log.error(f"Failed to convert image to Base64: {e}")
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
        """Save pyvips image as Philips-compatible pyramidal TIFF with XML metadata"""
        
        # Set resolution metadata (pixels per unit)
        # Convert from micrometers to pixels per cm: 1cm = 10000µm
        pixels_per_cm_x = 10000.0 / self.pixel_size_x if self.pixel_size_x > 0 else 1.0
        pixels_per_cm_y = 10000.0 / self.pixel_size_y if self.pixel_size_y > 0 else 1.0
        
        log.info(f"Setting pixel size metadata: {self.pixel_size_x} x {self.pixel_size_y} µm")
        log.info(f"Resolution: {pixels_per_cm_x:.2f} x {pixels_per_cm_y:.2f} pixels/cm")
        
        # Generate pyramid information for XML
        pyramid_levels = []
        temp_width, temp_height = self.size_x, self.size_y
        while temp_width >= 256 and temp_height >= 256:
            pyramid_levels.append({
                'width': temp_width,
                'height': temp_height
            })
            temp_width //= 2
            temp_height //= 2
        
        log.info(f"Generated {len(pyramid_levels)} pyramid levels for XML metadata")
        
        # Convert macro and label images to Base64 if present
        macro_base64 = None
        label_base64 = None
        
        if macro_image is not None:
            log.info("Converting macro image to Base64...")
            macro_base64 = self.vips_image_to_base64_jpeg(macro_image)
        
        if label_image is not None:
            log.info("Converting label image to Base64...")
            label_base64 = self.vips_image_to_base64_jpeg(label_image)
        
        # Generate Philips XML metadata
        wsi_info = {
            'width': self.size_x,
            'height': self.size_y,
            'pixel_spacing': self.pixel_size_x / 1000.0  # Convert µm to mm
        }
        
        source_filename = os.path.basename(self.input_path)
        philips_xml = self.xml_generator.generate_xml(
            source_filename=source_filename,
            wsi_info=wsi_info,
            pyramid_levels=pyramid_levels,
            macro_image_data=macro_base64,
            label_image_data=label_base64
        )
        
        log.info(f"Generated Philips XML metadata ({len(philips_xml)} characters)")
        
        # Save main pyramid (we'll add XML metadata with tiffset afterward)
        save_params = {
            'tile': True,
            'tile_width': self.tile_size,
            'tile_height': self.tile_size,
            'pyramid': True,
            'bigtiff': True,
            'xres': pixels_per_cm_x,  # Resolution in pixels/cm
            'yres': pixels_per_cm_y,  # Resolution in pixels/cm
            'resunit': 'cm',  # Resolution unit: centimeters
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
        
        # Create multi-directory TIFF using tifffile (with or without associated images)
        log.info("Creating pyramidal TIFF with tifffile...")
        self.save_multi_directory_tiff_with_xml(vips_image, macro_image, label_image, save_params, philips_xml)
        
        
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


    def save_multi_directory_tiff_with_xml(self, vips_image, macro_image, label_image, save_params, philips_xml):
        """Save multi-directory TIFF with embedded macro and label images using tifffile"""
        try:
            log.info("Creating multi-directory TIFF using tifffile.TiffWriter...")
            
            # Determine compression settings
            compression = 'jpeg' if self.compression.lower() == 'jpeg' else None
            compressionargs = None
            if compression == 'jpeg':
                compressionargs = {'level': self.quality}
            
            # Create BigTIFF file with TiffWriter
            with tifffile.TiffWriter(self.output_path, bigtiff=True) as tif:
                # Generate pyramid levels from the main image
                pyramid_images = self.generate_pyramid_levels(vips_image)
                log.info(f"Generated {len(pyramid_images)} pyramid levels")
                
                pixels_per_cm_x = 10000.0 / self.pixel_size_x if self.pixel_size_x > 0 else 1.0
                pixels_per_cm_y = 10000.0 / self.pixel_size_y if self.pixel_size_y > 0 else 1.0
                
                # Write ALL pyramid levels first (directories 0-N) like reference file
                for level, pyramid_level in enumerate(pyramid_images):
                    level_array = self.vips_to_numpy(pyramid_level)
                    
                    # Determine subfile type: 0 for base image, 1 for reduced resolution
                    subfiletype = 0 if level == 0 else 1
                    
                    # Create Aperio-compatible description for pyramid levels
                    if level == 0:
                        # Base level needs Aperio format for OpenSlide detection
                        aperio_desc = f"Aperio Image Library v12.0.15\n{self.size_x}x{self.size_y} [0,0,{self.size_x},{self.size_y}] ({self.tile_size}x{self.tile_size}) JPEG/RGB Q={self.quality}|AppMag = 40|StripeWidth = 2040|ScanScope ID = SS1302|Filename = {os.path.basename(self.input_path)}|Date = {datetime.now().strftime('%m/%d/%y')}|Time = {datetime.now().strftime('%H:%M:%S')}|User = Claude|Piecewise Affine = 0|MPP = {self.pixel_size_x / 1000.0:.6f}|Left = 0.000000|Top = 0.000000|LineCameraSkew = -0.000424|LineAreaXOffset = 0.019265|LineAreaYOffset = -0.000313|Focus Offset = 0.000000|ImageID = {os.path.splitext(os.path.basename(self.input_path))[0]}|OriginalWidth = {self.size_x}|Originalheight = {self.size_y}|Filtered = 5|OriginallyScanned = 1"
                        description = aperio_desc
                    else:
                        # Pyramid levels with basic descriptions
                        mag = 40 / (2 ** level)
                        description = f"Aperio Image Library v12.0.15\n{pyramid_level.width}x{pyramid_level.height} -> {pyramid_level.width}x{pyramid_level.height} - ({self.tile_size}x{self.tile_size}) JPEG/RGB Q={self.quality}"
                    
                    # Write pyramid level
                    tif.write(
                        level_array,
                        photometric='rgb',
                        compression=compression,
                        compressionargs=compressionargs,
                        tile=(self.tile_size, self.tile_size),
                        subfiletype=subfiletype,
                        description=description,
                        software='Philips DP v1.0',
                        resolution=(pixels_per_cm_x, pixels_per_cm_y),
                        resolutionunit='CENTIMETER'
                    )
                    log.info(f"Wrote pyramid level {level} ({level_array.shape[1]}x{level_array.shape[0]})")
                
                # Write macro image AFTER all pyramid levels (Aperio SVS format)
                if macro_image is not None:
                    macro_array = self.vips_to_numpy(macro_image)
                    
                    # Aperio SVS format requires simple "macro\r" description and stripped storage
                    tif.write(
                        macro_array,
                        photometric='rgb',
                        compression='jpeg',
                        compressionargs={'level': self.quality},
                        subfiletype=1,  # Reduced resolution/thumbnail
                        description="macro\r",  # Aperio format: simple name + carriage return
                        software='Aperio Digital Pathology'
                        # NO tile parameter = stripped format (required for Aperio associated images)
                        # NO resolution tag
                    )
                    log.info(f"Wrote macro image ({macro_array.shape[1]}x{macro_array.shape[0]}) in Aperio stripped format")
                
                # Write label image LAST (Aperio SVS format)
                if label_image is not None:
                    label_array = self.vips_to_numpy(label_image)
                    
                    # Aperio SVS format requires simple "label\r" description and stripped storage
                    tif.write(
                        label_array,
                        photometric='rgb',
                        compression='jpeg',
                        compressionargs={'level': self.quality},
                        subfiletype=1,  # Reduced resolution/thumbnail
                        description="label\r",  # Aperio format: simple name + carriage return
                        software='Aperio Digital Pathology'
                        # NO tile parameter = stripped format (required for Aperio associated images)
                        # NO resolution tag
                    )
                    log.info(f"Wrote label image ({label_array.shape[1]}x{label_array.shape[0]}) in Aperio stripped format")
            
            log.info("Multi-directory TIFF created successfully with tifffile")
                
        except Exception as e:
            log.error(f"Failed to create multi-directory TIFF with tifffile: {e}")
            log.info("Falling back to pyvips pyramidal save")
            # Fallback to pyvips save
            vips_image.tiffsave(self.output_path, **save_params)
            log.warning("Metadata may not be properly set in fallback mode")

    def generate_pyramid_levels(self, vips_image):
        """Generate pyramid levels from a pyvips image"""
        pyramid_levels = []
        current_image = vips_image
        
        # Add the base level
        pyramid_levels.append(current_image)
        
        # Generate pyramid levels by halving resolution
        while current_image.width >= 256 and current_image.height >= 256:
            # Create half-resolution level
            current_image = current_image.resize(0.5, kernel='lanczos3')
            pyramid_levels.append(current_image)
            
            # Stop if we've reached a reasonable minimum size
            if current_image.width < 512 or current_image.height < 512:
                break
        
        log.info(f"Generated {len(pyramid_levels)} pyramid levels")
        return pyramid_levels
    
    def vips_to_numpy(self, vips_image):
        """Convert pyvips image to numpy array"""
        # Get image as memory buffer
        memory_buffer = vips_image.write_to_memory()
        
        # Convert to numpy array
        np_array = np.frombuffer(memory_buffer, dtype=np.uint8)
        
        # Reshape to (height, width, channels)
        height = vips_image.height
        width = vips_image.width
        channels = vips_image.bands
        
        np_array = np_array.reshape(height, width, channels)
        
        return np_array




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