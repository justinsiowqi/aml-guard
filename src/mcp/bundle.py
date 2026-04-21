"""
Bundle the AML Guard MCP server into a zip file for H2OGPTe upload.

Packages:
  server.py          — FastMCP entrypoint (top level)
  envs.json          — H2OGPTe secret-injection manifest (top level, single copy)
  requirements.txt   — dependencies installed at server startup (top level)
  aml_tools/         — single flat package: tools_impl, schema, tool_defs,
                       connection, queries. Named `aml_tools` (not `mcp`) to
                       avoid shadowing the pip-installed `mcp` package that
                       FastMCP ships as.

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
SKIP_FILES_FROM_MCP = {"server.py", "bundle.py", "envs.json", "__init__.py"}
SKIP_FILES_FROM_GRAPH = {"__init__.py"}


def _should_exclude(path: str) -> bool:
    return any(p in path for p in EXCLUDE_PATTERNS)


def _copy_package_files(src: Path, dest: Path, skip: set[str]) -> None:
    """Copy .py files from src into dest, skipping listed filenames and excluded patterns."""
    for item in src.iterdir():
        if item.name in skip or _should_exclude(item.name):
            continue
        if item.is_file() and item.suffix == ".py":
            shutil.copy(item, dest / item.name)


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
    graph_dir = src_dir / "graph"
    project_root = src_dir.parent                      # aml-guard/
    dist_dir = mcp_dir / "dist_mcp"

    print("Building AML Guard MCP bundle...")
    print(f"  Project root : {project_root}")
    print(f"  Output       : {output_name}")

    # Clean old staging dir
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir()

    # server.py (top level)
    shutil.copy(mcp_dir / "server.py", dist_dir / "server.py")
    print("  Copied: server.py")

    # envs.json (top level, single copy)
    envs_src = mcp_dir / "envs.json"
    if envs_src.exists():
        shutil.copy(envs_src, dist_dir / "envs.json")
        print("  Copied: envs.json")
    else:
        print(f"  Warning: envs.json not found at {envs_src}")

    # requirements.txt from project root (top level)
    req_src = project_root / "requirements.txt"
    if req_src.exists():
        shutil.copy(req_src, dist_dir / "requirements.txt")
        print("  Copied: requirements.txt")
    else:
        print("  Warning: requirements.txt not found — server will skip dependency install.")

    # aml_tools/ — flattened package combining src/mcp/ and src/graph/
    aml_tools_dest = dist_dir / "aml_tools"
    aml_tools_dest.mkdir()
    (aml_tools_dest / "__init__.py").write_text('"""AML Guard bundled tools package."""\n')

    _copy_package_files(mcp_dir, aml_tools_dest, SKIP_FILES_FROM_MCP)
    _copy_package_files(graph_dir, aml_tools_dest, SKIP_FILES_FROM_GRAPH)
    copied = sorted(f.name for f in aml_tools_dest.iterdir() if f.suffix == ".py")
    print(f"  Copied: aml_tools/ ({', '.join(copied)})")

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
        print("  Cleaned up staging dir.")

    print(f"Done! Bundle ready at: {zip_path}")
    return zip_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bundle AML Guard MCP server for H2OGPTe.")
    parser.add_argument("--output", "-o", default="aml_guard_mcp.zip", help="Output zip filename.")
    parser.add_argument("--no-cleanup", action="store_true", help="Keep staging directory after bundling.")
    args = parser.parse_args()
    build_mcp_zip(output_name=args.output, cleanup=not args.no_cleanup)
