The Challenge

  - OSC-specific repo: Originally designed for Ohio Supercomputer Center with SLURM
  - Proprietary dependencies: Requires Philips PathologySDK (not publicly available)
  - Version conflicts: SDK built for Python 3.8/Ubuntu 20.04, but modern systems use newer versions

  What Worked: The Efficient Approach

  1. Use Conda Environment First

  # Create isolated environment with correct Python version
  mamba create -n isyntax2tiff python=3.8
  mamba activate isyntax2tiff

  2. Extract SDK Packages Manually (Not System Installation)

  # Extract .deb packages to local directory (avoid sudo/system conflicts)
  mkdir -p ~/local/pathologysdk/2.0-L1
  cd pathologysdk-modules/
  for deb in *.deb; do dpkg-deb -x $deb ~/local/pathologysdk/2.0-L1/; done
  cd ../pathologysdk-python38-modules/
  for deb in *.deb; do dpkg-deb -x $deb ~/local/pathologysdk/2.0-L1/; done

  3. Link Python Modules to Conda Environment

  # Add SDK to Python path
  echo "/home/USER/local/pathologysdk/2.0-L1/usr/lib/python3/dist-packages" >
  ~/miniforge3/envs/isyntax2tiff/lib/python3.8/site-packages/pathology-sdk.pth

  4. Fix Library Dependencies

  # Create missing version symlinks
  cd ~/local/pathologysdk/2.0-L1/usr/local/lib/
  ln -s libpixelengine.so.5.1.0 libpixelengine.so.5
  # (repeat for other libraries)

  # Install compatible OpenSSL version
  mamba install openssl=1.1.1

  5. Make Environment Persistent

  # Auto-set library paths when activating conda env
  mkdir -p ~/miniforge3/envs/isyntax2tiff/etc/conda/activate.d/
  echo 'export LD_LIBRARY_PATH="/home/USER/local/pathologysdk/2.0-L1/usr/local/lib:$LD_LIBRARY_PATH"' >
  ~/miniforge3/envs/isyntax2tiff/etc/conda/activate.d/pathology-sdk.sh

  Efficient Setup Script for Next Time

  #!/bin/bash
  # Quick PathologySDK setup script

  # 1. Create environment
  mamba create -n isyntax2tiff python=3.8 -y
  mamba activate isyntax2tiff

  # 2. Install conda dependencies
  mamba install -c conda-forge libvips pyvips blosc tinyxml openssl=1.1.1 -y
  mamba install -c ome raw2ometiff -y

  # 3. Extract SDK (assuming SDK is in ~/PathologySDK/)
  mkdir -p ~/local/pathologysdk/2.0-L1
  cd ~/PathologySDK/Ubuntu20.04/philips-pathologysdk-2.0-L1-ubuntu20_04_py38_research/
  for deb in pathologysdk-modules/*.deb pathologysdk-python38-modules/*.deb; do
      dpkg-deb -x "$deb" ~/local/pathologysdk/2.0-L1/
  done

  # 4. Link Python modules
  echo "$HOME/local/pathologysdk/2.0-L1/usr/lib/python3/dist-packages" >
  ~/miniforge3/envs/isyntax2tiff/lib/python3.8/site-packages/pathology-sdk.pth

  # 5. Create library symlinks
  cd ~/local/pathologysdk/2.0-L1/usr/local/lib/
  for lib in libpixelengine libeglrendercontext libgles2renderbackend libgles3renderbackend libsoftwarerenderbackend
  libsoftwarerendercontext; do
      ln -sf ${lib}.so.5.1.0 ${lib}.so.5
  done

  # 6. Set up environment activation
  mkdir -p ~/miniforge3/envs/isyntax2tiff/etc/conda/activate.d/
  echo "export LD_LIBRARY_PATH=\"$HOME/local/pathologysdk/2.0-L1/usr/local/lib:\$LD_LIBRARY_PATH\"" >
  ~/miniforge3/envs/isyntax2tiff/etc/conda/activate.d/pathology-sdk.sh

  # 7. Install isyntax2raw
  git clone https://github.com/glencoesoftware/isyntax2raw.git
  cd isyntax2raw && pip install .

  Key Insights

  - Avoid system installation for proprietary SDKs (use local extraction)
  - Version isolation is crucial (conda environments)
  - Manual dependency management beats automated scripts for complex setups
  - Symlinks solve version mismatches between SDK expectations and system libraries