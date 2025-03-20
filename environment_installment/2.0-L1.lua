help([[PathologySDK 2.0-L1: This module sets up environment variables for the SDK.]])

-- Local Variables
local name = "pathologysdk"
local version = "2.0-L1"

-- Locate Home Directory
local homedir = os.getenv("HOME")
local root = pathJoin(homedir, "local", name, version, "usr")

-- Set Library Paths (Only `lib64/` Exists)
prepend_path("LD_LIBRARY_PATH", pathJoin(root, "lib64"))
prepend_path("LIBRARY_PATH", pathJoin(root, "lib64"))

-- Set Python Paths
prepend_path("PYTHONPATH", pathJoin(root, "lib64", "python3.6", "site-packages"))