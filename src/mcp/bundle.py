"""
Bundle the AML Guard MCP server into a zip file for H2OGPTe upload.

Packages:
  server.py          — FastMCP entrypoint
  requirements.txt   — dependencies installed at server startup
  mcp/               — tools_impl.py, schema.py (flattened from src/mcp/)
  graph/             — connection.py, queries.py (flattened from src/graph/)

Usage:
  python src/mcp/bundle.py
  python src/mcp/bundle.py --output my_bundle.zip
"""

import argparse
import os
import shutil
import zipfile
from pathlib import Path

EXCLUDE_PATTERNS = {"__pycache__", ".pyc", ".pyo", ".git", ".DS_Store", ".env", "dist_mcp"}


def _should_exclude(path: str) -> bool:
    return any(p in path for p in EXCLUDE_PATTERNS)


def _copy_filter(directory, files):
    return [f for f in files if _should_exclude(f)]


def build_mcp_zip(output_name: str = "aml_guard_mcp.zip", cleanup: bool = True) -> Path:
    """
    Build a zip containing the MCP server and all runtime dependencies.

    Args:
        output_name: Filename for the output zip.
        cleanup: Remove the staging directory after zipping.

    Returns:
        Path to the created zip file.
    """
    mcp_dir = Path(__file__).resolve().parent          # src/mcp/
    src_dir = mcp_dir.parent                           # src/
    project_root = src_dir.parent                      # aml-guard/
    dist_dir = mcp_dir / "dist_mcp"

    print("Building AML Guard MCP bundle...")
    print(f"  Project root : {project_root}")
    print(f"  Output       : {output_name}")

    # Clean old staging dir
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir()

    # server.py
    shutil.copy(mcp_dir / "server.py", dist_dir / "server.py")
    print("  Copied: server.py")

    # requirements.txt from project root
    req_src = project_root / "requirements.txt"
    if req_src.exists():
        shutil.copy(req_src, dist_dir / "requirements.txt")
        print("  Copied: requirements.txt")
    else:
        print("  Warning: requirements.txt not found — server will skip dependency install.")

    # src/mcp/ → mcp/  (exclude server.py and bundle.py — already at root)
    mcp_dest = dist_dir / "mcp"
    shutil.copytree(mcp_dir, mcp_dest, ignore=_copy_filter)
    for skip in ("server.py", "bundle.py"):
        (mcp_dest / skip).unlink(missing_ok=True)
    print("  Copied: mcp/ (tools_impl, schema, tool_defs)")

    # src/graph/ → graph/
    graph_src = src_dir / "graph"
    if not graph_src.exists():
        raise FileNotFoundError(f"graph directory not found at {graph_src}")
    shutil.copytree(graph_src, dist_dir / "graph", ignore=_copy_filter)
    print("  Copied: graph/ (connection, queries)")

    # Create zip
    zip_path = mcp_dir / output_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dist_dir):
            dirs[:] = [d for d in dirs if not _should_exclude(d)]
            for file in files:
                if _should_exclude(file):
                    continue
                file_path = Path(root) / file
                zipf.write(file_path, file_path.relative_to(dist_dir))

    zip_size = zip_path.stat().st_size / (1024 * 1024)
    print(f"  Created: {output_name} ({zip_size:.2f} MB)")

    if cleanup:
        shutil.rmtree(dist_dir)
        print(f"  Cleaned up staging dir.")

    print(f"Done! Bundle ready at: {zip_path}")
    return zip_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bundle AML Guard MCP server for H2OGPTe.")
    parser.add_argument("--output", "-o", default="aml_guard_mcp.zip", help="Output zip filename.")
    parser.add_argument("--no-cleanup", action="store_true", help="Keep staging directory after bundling.")
    args = parser.parse_args()
    build_mcp_zip(output_name=args.output, cleanup=not args.no_cleanup)
