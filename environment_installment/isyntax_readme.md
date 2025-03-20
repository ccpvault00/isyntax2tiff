# Installation issues
## 1. install philips sdk

## 2. edit isyntax2raw source code on anaconda environment
Modify the source file to handle missing metadata:

Modify the /ISYNTAX2RAW/__init__.py file in the conda env folder. I have edited those files and saved the [init.py](./ISYNTAX2RAW/__init__.py) and [isyntax2raw.py](./ISYNTAX2RAW/cli/isyntax2raw.py). My editing are labled with `ziyu` in the code.


replace those files in the conde env with my edited files will solve the `MISSING METADATA` issue.

## 3. install raw2tiff in conda (recommended)
search it on google. install using conda command.


## install raw2tiff from java source (Alternative) 
### 1. install openjdk, gradle, blosc
### 2. build project using gradle
`gradlew.bat build`
### 3. run: ??

# Run
## 1. isyntax2raw
Run the conversion:

    isyntax2raw write_tiles ../source/name.i2syntax name.zarr

## 2. raw2tiff
Run the conversion (Bio-Formats 6.x):

    raw2ometiff tile_directory pyramid.ome.tiff

or generate a 5.9.x-compatible pyramid:

    raw2ometiff tile_directory pyramid.tiff --legacy