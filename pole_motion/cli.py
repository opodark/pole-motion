import argparse
import json
from pathlib import Path

from .catalog import validate


def main():
    parser = argparse.ArgumentParser(description="Pole Motion catalog and video analysis")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate", help="Validate a catalog JSON")
    check.add_argument("file", type=Path)
    analysis = commands.add_parser("analyze", help="Export draft measurements from a video")
    analysis.add_argument("video", type=Path)
    analysis.add_argument("--id", required=True)
    analysis.add_argument("--fps", type=float, default=8.0)
    analysis.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate":
        validate(json.loads(args.file.read_text(encoding="utf-8")))
        print("Catalog valid (schema 0.1.0)")
    else:
        from .extract import extract
        document = extract(args.video, args.id, args.fps)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        print(args.out)


if __name__ == "__main__":
    main()
