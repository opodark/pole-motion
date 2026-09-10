import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from pole_motion.catalog import validate


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
