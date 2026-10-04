"""Prepare a self-contained PBIP snapshot for native Power BI Desktop export.

This generates text project files only. Open the generated PBIP, Refresh, and
use Desktop's File > Save as > PBIX to create the actual distributable file.
"""

import argparse
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path

from setup_dashboard import ROOT, prepare_dashboard


def prepare_standalone(data_path, output_dir):
    """Embed the exact validated CSV bytes and retain the report and DAX model.

    Gzip reduces the text model size. Bounded base64 literals are joined by M
    before decompression; no local file path or credentials are needed at refresh.
    The snapshot is fixed until a new release is built from a reviewed CSV.
    """
    data = Path(data_path).resolve()
    project = prepare_dashboard(data, output_dir)
    definition = project.parent / "premium_growth.SemanticModel/definition"
    raw = data.read_bytes()
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    if gzip.decompress(compressed) != raw:
        raise RuntimeError("Snapshot compression did not preserve input bytes")
    encoded = base64.b64encode(compressed).decode("ascii")
    # Keep each M literal below 32 KiB; concatenate before decoding base64.
    chunks = [encoded[i:i + 32760] for i in range(0, len(encoded), 32760)]
    literals = ",\n".join('                    "' + chunk + '"' for chunk in chunks)
    replacement = (
        'SnapshotBytes = Binary.Decompress(Binary.FromText(Text.Combine({\n'
        + literals
        + '\n                }), BinaryEncoding.Base64), Compression.GZip),\n'
        '                Source = Csv.Document(SnapshotBytes, '
        '[Delimiter=",", Columns=13, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),'
    )
    table = definition / "tables/Polizas.tmdl"
    text = table.read_text(encoding="utf-8")
    pattern = r'Source = if Text\.Trim\(ReportingCsvPath\).*?QuoteStyle=QuoteStyle\.Csv\]\),'
    text, count = re.subn(pattern, lambda _: replacement, text)
    if count != 1:
        raise RuntimeError("Expected exactly one CSV source in the model")
    table.write_text(text, encoding="utf-8", newline="\n")
    (definition / "expressions.tmdl").unlink()
    model = definition / "model.tmdl"
    text = model.read_text(encoding="utf-8")
    text = text.replace('["ReportingCsvPath","Polizas"]', '["Polizas"]')
    text = text.replace('ref expression ReportingCsvPath', '')
    model.write_text(text, encoding="utf-8", newline="\n")
    manifest = {"csv_sha256": hashlib.sha256(raw).hexdigest(), "csv_bytes": len(raw),
                "compressed_bytes": len(compressed), "external_csv_required": False,
                "pbix_export": "Power BI Desktop > Refresh > File > Save as > PBIX"}
    (project.parent / "snapshot_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed/portfolio_reporting.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "work/pbi_standalone")
    args = parser.parse_args()
    try:
        project = prepare_standalone(args.data, args.output)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(2, f"Standalone build stopped: {error}\n")
    print(f"Open, Refresh and Save as PBIX in Power BI Desktop: {project}")


if __name__ == "__main__":
    main()
