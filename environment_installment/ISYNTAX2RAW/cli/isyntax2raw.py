# encoding: utf-8
#
# Copyright (c) 2019 Glencoe Software, Inc. All rights reserved.
#
# This software is distributed under the terms described by the LICENCE file
# you can find at the root of the distribution bundle.
# If the file is missing please request a copy by contacting
# support@glencoesoftware.com.

import click
import logging
import json #ziyu

from .. import WriteTiles

def check_metadata(isyntax_obj): #ziyu
    """Check which metadata fields exist in the given iSyntax object."""
    
    pe_in = isyntax_obj.pixel_engine["in"]  # Access pixel engine
    metadata_fields = {
        "Pixel engine version": lambda: isyntax_obj.pixel_engine.version,
        "Barcode": lambda: isyntax_obj.barcode(),
        "Date of last calibration": lambda: pe_in.date_of_last_calibration,
        "Time of last calibration": lambda: pe_in.time_of_last_calibration,
        "Manufacturer": lambda: pe_in.manufacturer,
        "Model name": lambda: pe_in.model_name,
        "Device serial number": lambda: pe_in.device_serial_number,
        "Derivation description": lambda: isyntax_obj.derivation_description(),
        "Software versions": lambda: pe_in.software_versions,
        "Number of images": lambda: isyntax_obj.num_images(),
        "Scanner calibration status": lambda: pe_in.scanner_calibration_status,
        "Scanner operator ID": lambda: pe_in.scanner_operator_id,
        # "Scanner rack number": lambda: pe_in.scanner_rack_number,
        "Scanner rack priority": lambda: pe_in.scanner_rack_priority,
        # "Scanner slot number": lambda: pe_in.scanner_slot_number,
        "iSyntax file version": lambda: pe_in.isyntax_file_version,
    }

    available_metadata = {}
    missing_metadata = []

    for key, func in metadata_fields.items():
        try:
            value = func()
            available_metadata[key] = value
        except (AttributeError, KeyError, TypeError):
            missing_metadata.append(key)

    # Print results
    print("\n✅ Available Metadata:")
    print(json.dumps(available_metadata, indent=4))

    print("\n❌ Missing Metadata:")
    if missing_metadata:
        print("\n".join(missing_metadata))
    else:
        print("All metadata fields are available!")

    return available_metadata, missing_metadata

def setup_logging(debug):
    level = logging.INFO
    if debug:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s [%(name)16s] "
               "(%(thread)10s) %(message)s"
    )


@click.group()
def cli():
    pass


@cli.command(name='write_tiles')
@click.option(
    "--tile_width", default=512, type=int, show_default=True,
    help="tile width in pixels"
)
@click.option(
    "--tile_height", default=512, type=int, show_default=True,
    help="tile height in pixels"
)
@click.option(
    "--resolutions", type=int,
    help="number of pyramid resolutions to generate [default: all]"
)
@click.option(
    "--max_workers", default=4, type=int,
    show_default=True,
    help="maximum number of tile workers that will run at one time",
)
@click.option(
    "--batch_size", default=250, type=int, show_default=True,
    help="number of patches fed into the iSyntax SDK at one time"
)
@click.option(
    "--fill_color", type=click.IntRange(min=0, max=255), default=0,
    show_default=True,
    help="background color for missing tiles (0-255)"
)
@click.option(
    "--nested/--no-nested", default=True, show_default=True,
    help="Whether to use '/' as the chunk path separator"
)
@click.option(
    "--debug", is_flag=True,
    help="enable debugging",
)
@click.argument("input_path")
@click.argument("output_path")
def write_tiles(
    tile_width, tile_height, resolutions, max_workers, batch_size,
    fill_color, nested, debug, input_path, output_path
):
    setup_logging(debug)
    with WriteTiles(
        tile_width, tile_height, resolutions, max_workers,
        batch_size, fill_color, nested, input_path, output_path
    ) as wt:
        check_metadata(wt) #ziyu
        wt.write_metadata()
        wt.write_label_image()
        wt.write_macro_image()
        wt.write_pyramid()


@cli.command(name='write_metadata')
@click.option(
    "--debug", is_flag=True,
    help="enable debugging",
)
@click.argument('input_path')
@click.argument('output_file')
def write_metadata(debug, input_path, output_file):
    setup_logging(debug)
    with WriteTiles(
        None, None, None, None,
        None, None, None, input_path, None
    ) as wt:
        wt.write_metadata_json(output_file)


def main():
    cli()
