# Installation on OSC
Solution modified based on OSC [tutorial](https://www.osc.edu/resources/getting_started/howto/howto_locally_installing_software#getting-started)
## 1. Download from [Philips knowledge center](https://philips.mizecx.com/cc/knowledgeCenter.html?0b02b0ef41ddca1559617e2d350f77be8c43bfb3bd8a7b465631359da601aa757f2d0ecb2a58d4b1d7226d3506249a61#sblox=non)

Search `pathology sdk` and download the `PathologySDK_2.0-L1_Packages.zip`. After extraction, using the CentOS version of it that fits OSC systam.

## 2. build `local` folder in home
        local
            |-- src
            |-- share
                `-- lmodfiles


put sdk centos version installation folder into the `local/src`.
`local/share/lmodfiles` will save the module files later.

create a separate folder `local/pathologysdk/2.0-L1`. All new modules need a directory in this format `local/<name>/<version>`. This is where we save the installed files.

## 3. install
Provided installation script use `YUM` which need ADMIN. To avoid it, manually build files to `local/pathologysdk/2.0-L1`:

    cd pathologysdk-python36-modules
    for rpm in *.rpm; do rpm2cpio $rpm | cpio -idmv -D $HOME/local/pathologysdk/2.0-L1/; done

Also:

    cd ..
    cd pathologysdk-modules
    for rpm in *.rpm; do rpm2cpio $rpm | cpio -idmv -D $HOME/local/pathologysdk/2.0-L1/; done

## 4. create module manually:
Create a .lua file names `2.0-L1.lua`, and copy it to `/local/share/lmodfiles/pathologysdk/` (need to create the folder if you dont have). The sample lua file is in [here](./2.0-L1.lua).

Now you should have a module in your env. load it by:

    module use $HOME/local/share/lmodfiles
    module load pathologysdk/2.0-L1


# install isyntax2tif packages
[Solution](https://www.glencoesoftware.com/blog/2019/12/09/converting-whole-slide-images-to-OME-TIFF.html)

Make a work directory in your folder.
## requirement

    python==3.6.*
    tinyxml

## 1. install isyntax2raw
clone [it](https://github.com/glencoesoftware/isyntax2raw) to your folder:

    git clone https://github.com/glencoesoftware/isyntax2raw.git

Then, configure the package :

    cd isyntax2raw
    pip install .

Verify if it is working:

    isyntax2raw write_tiles <input.i2syntax> <output.zarr>

if got error saying cannot find `libtinyxml.so.0`, find `litinyxml.so*` in the env:

    find $HOME/.conda/envs/philips/ -name "libtinyxml.so*"

Usually, you can only find `libtinyxml.so` but not `libtinyxml.so.0`. To solve it, link `libtinyxml.so.0` with `libtinyxml.so`:

    ln -s $HOME/.conda/envs/philips/lib/libtinyxml.so $HOME/.conda/envs/philips/lib/libtinyxml.so.0

Verify if it is linked:

    ls -lah $HOME/.conda/envs/philips/lib/ | grep libtinyxml


## 2. install raw2ometiff:
Requirement: blosc

    conda install blosc

install raw2ometiff by [conda](https://anaconda.org/ome/raw2ometiff):

    conda install ome::raw2ometiff

## 3. install packages for ome-tiff to pyramidal-tiff:
Requirement: libvips, pyvips:

    conda install conda-forge::libvips
    pip install pyvips

# Usage
* This is a use case based on command lines. For batch running on OSC, go to the parent dir [readme](../README.md).

load pathology sdk:

    module use $HOME/local/share/lmodfiles
    module load pathologysdk/2.0-L1

## 1. isyntax2raw
Run the conversion:

    isyntax2raw write_tiles ../source/name.i2syntax name.zarr

If missing metadata error happens, see how to [debug](./isyntax_readme.md) isyntax2raw's source code.

## 2. raw2tiff (to OME-TIFF)
Run the conversion (Bio-Formats 6.x):

    raw2ometiff tile_directory pyramid.ome.tiff --rgb

or generate a 5.9.x-compatible pyramid:

    raw2ometiff tile_directory pyramid.tiff --legacy --rgb

## 3. OME-TIFF to pyramidal-tiff:
Run:
    python ../ome2pyramidaltiff.py --input inputdir --output outputdir