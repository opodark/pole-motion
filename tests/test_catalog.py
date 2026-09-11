import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from pole_motion.catalog import hold_focus, promote_hold, validate


@pytest.fixture
def catalog():
    return json.loads((Path(__file__).parents[1] / "examples/catalog.json").read_text(encoding="utf-8"))


def test_example(catalog):
    validate(catalog)


@pytest.mark.parametrize("case", ["duplicate", "reference", "ordering", "interval", "unknown_pose", "nan"])
def test_rejects_broken_relationships(catalog, case):
    r = catalog["recordings"][0]
    if case == "duplicate":
        catalog["poses"].append(copy.deepcopy(catalog["poses"][0]))
    elif case == "reference":
        catalog["poses"][0]["references"][0]["recording_id"] = "missing"
    elif case == "ordering":
        r["frames"].append(copy.deepcopy(r["frames"][0]))
    elif case == "interval":
        r["holds"] = [{"t0": 1, "t1": 0.5}]
    elif case == "unknown_pose":
        catalog["movements"][0]["steps"][0]["pose_id"] = "missing"
    else:
        r["duration_s"] = float("nan")
    with pytest.raises(ValueError):
        validate(catalog)


def test_validated_movement_requires_validated_poses(catalog):
    catalog["movements"][0]["review"] = {"status": "validated", "reviewer": "teacher", "reviewed_at": "2026-09-10"}
    with pytest.raises(ValueError):
        validate(catalog)
    catalog["poses"][0]["review"] = copy.deepcopy(catalog["movements"][0]["review"])
    validate(catalog)


def test_validated_pose_requires_reviewer(catalog):
    catalog["poses"][0]["review"]["status"] = "validated"
    with pytest.raises(ValidationError):
        validate(catalog)


def test_visibility_is_not_depth(catalog):
    points = [[0.5, 0.5, 1.0] for _ in range(33)]
    catalog["recordings"][0]["frames"][0]["landmarks"] = points
    validate(catalog)
    points[0][2] = -0.4
    with pytest.raises(ValidationError):
        validate(catalog)


def test_unknown_version(catalog):
    catalog["schema_version"] = "2.0.0"
    with pytest.raises(ValidationError):
        validate(catalog)


def test_hold_focus_picks_the_most_overlapping_contact(catalog):
    r = catalog["recordings"][0]
    r["duration_s"] = 10
    r["contacts"] = [
        {"part": "left_hand", "t0": 1.2, "t1": 2.8},
        {"part": "right_foot", "t0": 2.7, "t1": 2.9},
    ]
    assert hold_focus(r, 1.0, 3.0) == "left_hand"
    assert hold_focus(r, 5.0, 6.0) is None


def test_promote_hold_creates_a_validated_pose(catalog):
    r = catalog["recordings"][0]
    r["duration_s"] = 10
    r["holds"] = [{"t0": 1.0, "t1": 3.0}, {"t0": 5.0, "t1": 6.0}]
    r["contacts"] = [{"part": "left_hand", "t0": 1.2, "t1": 2.8}]

    result = promote_hold(catalog, r["id"], 0, "invert-basic", "Invert base",
                          "istruttrice", aliases=["invert"], description="posa di prova")
    pose = next(p for p in result["poses"] if p["id"] == "invert-basic")
    assert pose["review"]["status"] == "validated"
    assert pose["review"]["reviewer"] == "istruttrice"
    assert isinstance(pose["review"]["reviewed_at"], str) and pose["review"]["reviewed_at"]
    assert pose["references"] == [{"recording_id": r["id"], "t": 2.0}]  # centro del fermo

    # ripromuovere lo stesso pose_id aggiorna la voce, non la duplica
    result = promote_hold(result, r["id"], 0, "invert-basic", "Invert base", "istruttrice")
    assert sum(1 for p in result["poses"] if p["id"] == "invert-basic") == 1


def test_promote_hold_rejects_unknown_recording(catalog):
    with pytest.raises(ValueError):
        promote_hold(catalog, "missing-recording", 0, "x", "X", "reviewer")


def test_promote_hold_rejects_bad_index(catalog):
    r = catalog["recordings"][0]
    r["holds"] = [{"t0": 0, "t1": 1}]
    with pytest.raises(ValueError):
        promote_hold(catalog, r["id"], 5, "x", "X", "reviewer")
