import numpy as np
import pytest
from pole_motion.pose import PoseFrame
from pole_motion.avatar import motion_from_frames


def test_world_motion_preserves_depth_and_centers_hips():
    world = np.ones((33, 4)); world[0, 2] = 3
    result = motion_from_frames([PoseFrame(0, world=world), PoseFrame(.1)], "abc")
    assert result["frames"][0]["points"][0][2] == 2
    assert result["frames"][0]["points"][23][:3] == [0, 0, 0]
    assert result["frames"][1]["points"] is None
    assert world[23, 0] == 1
    assert result["root_translation"] is False


def test_invalid_motion_rejected():
    with pytest.raises(ValueError):
        motion_from_frames([PoseFrame(0, world=np.zeros((33, 3)))], "a")
    with pytest.raises(ValueError):
        motion_from_frames([PoseFrame(1), PoseFrame(0)], "a")


def test_motion_keeps_image_space_hip_trajectory():
    world = np.zeros((33, 4)); world[:, 3] = 1
    image = np.zeros((33, 3)); image[:, 2] = 1
    image[23, :2] = [.4, .7]; image[24, :2] = [.6, .9]
    result = motion_from_frames([PoseFrame(0, lm=image, world=world)], "abc")
    assert result["root_translation"] is True
    assert result["frames"][0]["root"] == [.5, .8, 1.0]
