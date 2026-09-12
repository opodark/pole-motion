"""Validate the exchange format and relationships across its records."""
import json
import math
from datetime import datetime, timezone
from importlib.resources import files

from jsonschema import Draft202012Validator


def validate(document):
    schema = json.loads(files("pole_motion").joinpath("catalog.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)

    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Non-finite numbers are not valid measurements")
        if isinstance(value, dict):
            for item in value.values():
                finite(item)
        elif isinstance(value, list):
            for item in value:
                finite(item)

    finite(document)
    indices = {}
    for collection in ("poses", "recordings", "movements"):
        rows = document[collection]
        indices[collection] = {r["id"]: r for r in rows}
        if len(indices[collection]) != len(rows):
            raise ValueError(f"Duplicate IDs in {collection}")

    for record in document["recordings"]:
        times = [f["t"] for f in record["frames"]]
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError("Frame times must be strictly increasing")
        if any(t > record["duration_s"] for t in times):
            raise ValueError("Frame outside recording duration")
        for key in ("contacts", "holds"):
            for item in record[key]:
                if not 0 <= item["t0"] <= item["t1"] <= record["duration_s"]:
                    raise ValueError(f"Invalid {key} interval")
        for event in record["events"]:
            if event["t"] > record["duration_s"]:
                raise ValueError("Event outside recording duration")

    for pose in document["poses"]:
        for ref in pose["references"]:
            record = indices["recordings"].get(ref["recording_id"])
            if record is None or ref["t"] > record["duration_s"]:
                raise ValueError("Invalid pose reference")
        if pose["review"]["status"] == "validated" and not pose["references"]:
            raise ValueError("Validated poses need a reference")

    for movement in document["movements"]:
        previous = -1
        for step in movement["steps"]:
            pose = indices["poses"].get(step["pose_id"])
            if pose is None:
                raise ValueError("Unknown pose in movement")
            if step["at_s"] < previous:
                raise ValueError("Movement steps must be ordered")
            previous = step["at_s"]
            if movement["review"]["status"] == "validated" and pose["review"]["status"] != "validated":
                raise ValueError("Validated movements require validated poses")
    return document


def hold_focus(recording, t0, t1):
    """Parte (mano/piede) con la presa che si sovrappone di piu' al fermo
    [t0, t1] fra i `contacts` gia' calcolati sulla registrazione, o None
    se nessun contatto ricade in quella finestra."""
    best_part, best_overlap = None, 0.0
    for c in recording["contacts"]:
        overlap = min(t1, c["t1"]) - max(t0, c["t0"])
        if overlap > best_overlap:
            best_part, best_overlap = c["part"], overlap
    return best_part


def promote_hold(document, recording_id, hold_index, pose_id, name, reviewer, *,
                 aliases=None, description="", t=None, notes=None):
    """Crea (o aggiorna, se `pose_id` esiste gia') una `pose` VALIDATA nel
    documento, con riferimento a un fermo di una registrazione esistente.

    E' cosi' che nasce il dizionario condiviso: l'AI propone i fermi,
    l'istruttrice ne sceglie uno, gli da' un nome e lo valida qui.
    Il documento viene rivalidato per intero prima di essere ritornato,
    quindi qualunque incoerenza (id malformato, riferimento fuori range,
    ...) fa fallire la chiamata senza lasciare il documento a meta'.
    """
    recording = next((r for r in document["recordings"] if r["id"] == recording_id), None)
    if recording is None:
        raise ValueError(f"Registrazione sconosciuta: {recording_id}")
    holds = recording["holds"]
    if not 0 <= hold_index < len(holds):
        raise ValueError(f"Indice fermo fuori range: {hold_index} (0..{len(holds) - 1})")
    h = holds[hold_index]
    ref_t = h["t0"] + (h["t1"] - h["t0"]) / 2 if t is None else t

    pose_entry = {
        "id": pose_id,
        "name": name,
        "aliases": list(aliases or []),
        "description": description,
        "references": [{"recording_id": recording_id, "t": ref_t}],
        "review": {
            "status": "validated",
            "reviewer": reviewer,
            "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }
    if notes:
        pose_entry["review"]["notes"] = notes

    poses = document.get("poses", [])
    existing = next((i for i, p in enumerate(poses) if p["id"] == pose_id), None)
    candidate_poses = list(poses)
    if existing is not None:
        candidate_poses[existing] = pose_entry
    else:
        candidate_poses.append(pose_entry)

    candidate = dict(document)
    candidate["poses"] = candidate_poses
    validate(candidate)

    document["poses"] = candidate_poses
    return document
