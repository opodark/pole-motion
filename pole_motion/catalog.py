"""Validate the exchange format and relationships across its records."""
import json
import math
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
