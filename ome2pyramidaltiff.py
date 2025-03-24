# install pyvips using: pip install pyvips
import pyvips
import argparse

parser = argparse.ArgumentParser(description="Save a slide as a pyramidal TIFF with tiling.")
parser.add_argument("--path", type=str, help="Path to the OME-TIFF file.")
parser.add_argument("--output", type=str, help="Path to save the pyramidal TIFF file.")
args = parser.parse_args()

# Load your full-resolution OME-TIFF (level 0)
slide = pyvips.Image.new_from_file(args.path, access="sequential")

# Save it as a pyramidal TIFF with tiling
slide.tiffsave(
    args.output,
    tile=True,           # Use tiling
    tile_width=512,      # Tile size (standard)
    tile_height=512,
    pyramid=True,        # Create pyramid levels (multi-resolution)
    compression="jpeg",  # JPEG compression (widely supported by OpenSlide)
    Q=90,                # JPEG quality (adjust as needed)
    bigtiff=True         # Use BigTIFF if the file is large (>4GB)
)
