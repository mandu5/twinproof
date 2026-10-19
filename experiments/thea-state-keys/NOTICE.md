The Python adapters, launcher, downloader, documentation, and experiment-derived
metadata in this directory are supplied under the accompanying MIT license from
this repository. This does not grant rights to external THEA code or game inputs.

The external inputs are public artifacts from bruno353/thea at commit
`b7f0ce0fa391f27b3134f875c964f14b883cfb2c`. Their redistribution/license scope has
not been independently established. No external Python source, archive, or frame
file is included here. `fetch_inputs.py` downloads the exact pinned artifacts
directly from their upstream URLs, into a caller-selected local cache. Users must
assess applicable upstream terms for their use.

Private historical experiment receipts remain byte-for-byte in the original local
cache. Published receipts are explicit projections: only personal absolute path
strings are replaced by named placeholders. Their private original hashes and
published projection hashes are recorded separately in `receipts/provenance.json`.
The portable runner does not read or execute commands from these receipts. Full
snapshot grids and duplicate raw discovery logs are omitted. Compact derived
histories and full-state hashes reconstruct and check the two fixed witnesses.
