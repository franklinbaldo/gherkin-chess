from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .mcp_server import mcp, session_manager


def main():
    parser = argparse.ArgumentParser(description="gherkin-chess CLI and MCP Server")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # mcp command
    mcp_parser = subparsers.add_parser("mcp", help="Run MCP server over stdio")

    # web command
    web_parser = subparsers.add_parser("web", help="Run lightweight observer web UI")
    web_parser.add_argument("--port", type=int, default=8000, help="Web UI port (default: 8000)")

    # corpus command
    corpus_parser = subparsers.add_parser("corpus", help="List stored OKF features in corpus")

    args = parser.parse_args()

    if args.command == "mcp" or args.command is None:
        # Default to running MCP server
        mcp.run()
    elif args.command == "corpus":
        features = session_manager.corpus.load_all_features()
        print(f"Total features in OKF bundle: {len(features)}")
        for i, f in enumerate(features, 1):
            print(f"{i}. [{f.name}] origin: {f.origin_fen} ({len(f.scenarios)} scenarios)")
    elif args.command == "web":
        from .web_server import run_web
        run_web(port=args.port)


if __name__ == "__main__":
    main()