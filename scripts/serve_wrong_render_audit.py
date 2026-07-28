"""Serve the project root for the local WrongRender annotation frontend."""

import argparse
import http.server
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    os.chdir(ROOT)
    address = ("127.0.0.1", args.port)
    print(f"Open http://{address[0]}:{address[1]}/outputs/human_audit/wrong_render_1200/web_annotation/")
    http.server.ThreadingHTTPServer(address, http.server.SimpleHTTPRequestHandler).serve_forever()


if __name__ == "__main__":
    main()
