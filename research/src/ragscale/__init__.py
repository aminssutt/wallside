"""ragscale: document-identification accuracy of RAG pipelines as the corpus grows."""

import os

# torch and faiss-cpu each bundle their own libomp on macOS; whichever initializes second aborts the process
# (OMP Error #15). The harness restricts faiss to a single thread wherever both are loaded (FilteredANN), so
# allowing the duplicate runtime is safe here. Set before any submodule imports either library.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

__version__ = "0.1.0"
