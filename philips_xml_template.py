#!/usr/bin/env python3
"""
Philips TIFF XML Metadata Template Generator

This module generates XML metadata that matches the Philips official TIFF format.
The XML structure follows the DPUfsImport format with DICOM groups and elements.
"""

import base64
from datetime import datetime
from typing import List, Dict, Any, Optional

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
                    wsi_info: Dict[str, Any],
                    pyramid_levels: List[Dict[str, Any]],
                    macro_image_data: Optional[str] = None,
                    label_image_data: Optional[str] = None) -> str:
        """
        Generate complete Philips XML metadata.
        
        Args:
            source_filename: Original iSyntax filename
            wsi_info: WSI information (width, height, pixel_spacing)
            pyramid_levels: List of pyramid level information
            macro_image_data: Base64 encoded macro image (JPEG)
            label_image_data: Base64 encoded label image (JPEG)
        """
        
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
                             calibration_date: str, calibration_time: str) -> List[str]:
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
                          wsi_info: Dict[str, Any], 
                          pyramid_levels: List[Dict[str, Any]]) -> List[str]:
        """Generate WSI image XML."""
        
        pixel_spacing = wsi_info.get('pixel_spacing', 0.00025)
        width = wsi_info.get('width', 80896)
        height = wsi_info.get('height', 21504)
        
        xml_parts = []
        xml_parts.append('\t\t\t<DataObject ObjectType="DPScannedImage">')
        
        # Add derivation description
        derivation_desc = f'tiff-useBigTIFF=0-useRgb=0-levels={len(pyramid_levels)},10002,10000,10001-processing=0-q80-sourceFilename=&quot;{source_filename}&quot;;PHILIPS UFS V1.8.6824 | Quality=2 | DWT=1 | Compressor=16'
        xml_parts.append(f'\t\t\t\t<Attribute Name="DICOM_DERIVATION_DESCRIPTION" Group="0x0008" Element="0x2111" PMSVR="IString">{derivation_desc}</Attribute>')
        
        # Add compression info
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
    
    def _generate_associated_image(self, image_type: str, image_data: str) -> List[str]:
        """Generate associated image (MACRO or LABEL) XML."""
        return [
            '\t\t\t<DataObject ObjectType="DPScannedImage">',
            f'\t\t\t\t<Attribute Name="PIM_DP_IMAGE_DATA" Group="0x301D" Element="0x1005" PMSVR="IString">{image_data}</Attribute>',
            f'\t\t\t\t<Attribute Name="PIM_DP_IMAGE_TYPE" Group="0x301D" Element="0x1004" PMSVR="IString">{image_type}</Attribute>',
            '\t\t\t</DataObject>',
        ]
    
    def _generate_footer_attributes(self) -> List[str]:
        """Generate footer attributes."""
        return [
            '\t<Attribute Name="PIM_DP_UFS_BARCODE" Group="0x301D" Element="0x1002" PMSVR="IString">S114-99047-_-A-3</Attribute>',
            '\t<Attribute Name="PIM_DP_UFS_INTERFACE_VERSION" Group="0x301D" Element="0x1001" PMSVR="IString">1.8.6824</Attribute>',
        ]


def example_usage():
    """Example of how to use the PhilipsXMLGenerator."""
    
    generator = PhilipsXMLGenerator()
    
    # Example WSI info
    wsi_info = {
        'width': 80896,
        'height': 21504,
        'pixel_spacing': 0.00025
    }
    
    # Example pyramid levels
    pyramid_levels = [
        {'width': 80896, 'height': 21504},
        {'width': 40448, 'height': 10752},
        {'width': 20480, 'height': 5632},
        {'width': 10240, 'height': 3072},
        {'width': 5120, 'height': 1536},
        {'width': 2560, 'height': 1024},
        {'width': 1536, 'height': 512},
        {'width': 1024, 'height': 512},
        {'width': 512, 'height': 512},
    ]
    
    # Generate XML
    xml_content = generator.generate_xml(
        source_filename="example.isyntax",
        wsi_info=wsi_info,
        pyramid_levels=pyramid_levels,
        macro_image_data="[BASE64_ENCODED_MACRO_IMAGE]",
        label_image_data="[BASE64_ENCODED_LABEL_IMAGE]"
    )
    
    print("Generated Philips XML:")
    print("=" * 50)
    print(xml_content)


if __name__ == "__main__":
    example_usage()