import hashlib

from pole_motion.webcam_demo import _hash_file


def test_hash_file_matches_hashlib(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"not really a video, just some bytes")
    assert _hash_file(p) == hashlib.sha256(p.read_bytes()).hexdigest()
