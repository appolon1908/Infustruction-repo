# Server A historical inventory schema repair

This directory preserves the September 1, 2026 inventory. The September 6
source-only repair is not a new server observation or production certification.

The original `PRODUCTION-PORT-EXPOSURE.md` contains the complete container
port bindings. JSON `published_ports` and the CSV column now preserve those
exact host-address/host-port-to-container-port strings, including ranges.
Exposed-only container ports are separate JSON `exposed_ports` entries and
are never classified as host publications. All 102 original container records
remain; the CSV now declares its eleven-column schema.

The JSON and CSV corrections derive only from this same committed historical
port snapshot, not from new Docker access. Other record fields and the raw
port/host-listener evidence remain unchanged. Original versions remain in Git
ancestry. The portable `SHA256SUMS` uses filenames relative to this directory,
includes this explanation, and excludes itself. It is an integrity manifest,
not a cryptographic signature or proof of fresh runtime observation.

From this directory, run `sha256sum --check SHA256SUMS`. From the repository
root, run `python3 scripts/validate_server_a_consolidation.py` and
`python3 -m unittest discover -s tests -p test_server_a_consolidation.py -v`.
These commands validate source artifacts only and never contact a host.
