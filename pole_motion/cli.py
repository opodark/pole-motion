import argparse
import json
from pathlib import Path

from .catalog import hold_focus, promote_hold, validate


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(document: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def _find_recording(document: dict, recording_id: str) -> dict:
    record = next((r for r in document["recordings"] if r["id"] == recording_id), None)
    if record is None:
        raise SystemExit(f"Registrazione sconosciuta: {recording_id}")
    return record


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

    listing = commands.add_parser("list-holds", help="List the holds of a recording (with the likely grip)")
    listing.add_argument("file", type=Path)
    listing.add_argument("--recording", required=True)

    naming = commands.add_parser("name-pose", help="Promote a hold to a validated pose")
    naming.add_argument("file", type=Path)
    naming.add_argument("--recording", required=True)
    naming.add_argument("--hold", type=int, required=True, help="indice mostrato da list-holds")
    naming.add_argument("--pose-id", required=True, dest="pose_id")
    naming.add_argument("--name", required=True)
    naming.add_argument("--reviewer", required=True)
    naming.add_argument("--alias", action="append", default=[], dest="aliases")
    naming.add_argument("--description", default="")
    naming.add_argument("--out", type=Path, default=None, help="default: sovrascrive il file di input")

    args = parser.parse_args()

    if args.command == "validate":
        validate(_load(args.file))
        print("Catalog valid (schema 0.1.0)")

    elif args.command == "analyze":
        from .extract import extract
        document = extract(args.video, args.id, args.fps)
        _save(document, args.out)
        print(args.out)

    elif args.command == "list-holds":
        document = _load(args.file)
        record = _find_recording(document, args.recording)
        holds = record["holds"]
        if not holds:
            print("Nessun fermo in questa registrazione.")
        for i, h in enumerate(holds):
            part = hold_focus(record, h["t0"], h["t1"])
            print(f"[{i}] {h['t0']:6.2f}-{h['t1']:6.2f}s  presa={part or '?'}")

    elif args.command == "name-pose":
        document = _load(args.file)
        document = promote_hold(
            document, args.recording, args.hold, args.pose_id, args.name, args.reviewer,
            aliases=args.aliases, description=args.description,
        )
        out = args.out or args.file
        _save(document, out)
        print(f"posa '{args.pose_id}' validata -> {out}")


if __name__ == "__main__":
    main()
