import http.client
import json
import threading
import time
from html.parser import HTMLParser

import pytest

from pole_motion.studio import STATIC, StudioServer


def test_player_is_outside_heading_and_inside_viewer():
    class LayoutParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.video_ancestors = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get('id') == 'video':
                self.video_ancestors = [item[1] for item in self.stack]
            if tag not in {'meta', 'link', 'input', 'br', 'img', 'hr'}:
                self.stack.append((tag, attrs))

        def handle_endtag(self, tag):
            assert self.stack and self.stack[-1][0] == tag, f'Unbalanced {tag}'
            self.stack.pop()

    parser = LayoutParser()
    parser.feed((STATIC / 'index.html').read_text(encoding='utf-8'))
    assert not parser.stack
    ancestors = parser.video_ancestors
    assert ancestors is not None
    classes = [a.get('class', '') for a in ancestors]
    assert 'page-heading' not in classes
    assert 'viewer-card' in classes
    assert any(a.get('id') == 'stage' for a in ancestors)


@pytest.fixture
def studio(tmp_path):
    server = StudioServer(('127.0.0.1', 0), tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    server.worker.shutdown()
    server.live.close()
    thread.join()


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def wait_job(server, key):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        code, body = request(server, 'GET', f'/api/jobs/{key}')
        assert code == 200
        result = json.loads(body)
        if result['status'] in ('done', 'error'):
            return result
        time.sleep(.01)
    pytest.fail('Job did not finish')


def test_upload_analysis_and_persistence(studio, monkeypatch):
    def extract(path, key):
        assert path.read_bytes() == b'video bytes'
        return {'recording_id': key}
    monkeypatch.setattr('pole_motion.extract.extract', extract)
    code, body = request(studio, 'POST', '/api/analyze', b'video bytes')
    assert code == 202
    key = json.loads(body)['id']
    result = wait_job(studio, key)
    assert result == {'status': 'done', 'document': {'recording_id': key}}
    assert json.loads((studio.storage / f'{key}.json').read_text()) == result['document']


def test_inference_failure_is_reported(studio, monkeypatch):
    def fail(*args):
        raise RuntimeError('Video non leggibile')
    monkeypatch.setattr('pole_motion.extract.extract', fail)
    _, body = request(studio, 'POST', '/api/analyze', b'invalid')
    result = wait_job(studio, json.loads(body)['id'])
    assert result == {'status': 'error', 'error': 'Video non leggibile'}


def test_rejects_external_origin_and_empty_upload(studio):
    assert request(studio, 'POST', '/api/analyze', b'video', {'Origin': 'https://external.example'})[0] == 403
    assert request(studio, 'POST', '/api/analyze', b'')[0] == 413
    assert not list(studio.storage.iterdir())


def test_serves_only_studio_assets(studio):
    for path in ('/', '/app.js', '/style.css', '/avatar-3d.js',
                 '/vendor/three.module.js', '/models/female-athlete.glb',
                 '/models/QUATERNIUS-LICENSE.txt'):
        assert request(studio, 'GET', path)[0] == 200
    assert request(studio, 'GET', '/models/female-athlete.glb')[1][:4] == b'glTF'
    assert b'CC0 1.0 Universal' in request(studio, 'GET', '/models/QUATERNIUS-LICENSE.txt')[1]
    assert request(studio, 'GET', '/vendor/../../pyproject.toml')[0] == 404
    assert request(studio, 'GET', '/../../pyproject.toml')[0] == 404
    assert request(studio, 'GET', '/api/jobs/missing')[0] == 404


def test_live_frames_are_not_persisted(studio, monkeypatch):
    def detect(encoded):
        assert encoded == b'jpeg'
        return {'landmarks': None, 'inference_ms': 10}
    monkeypatch.setattr(studio.live, 'detect', detect)
    code, body = request(studio, 'POST', '/api/live', b'jpeg')
    assert code == 200
    assert json.loads(body)['landmarks'] is None
    assert not list(studio.storage.iterdir())


def test_live_busy_and_errors(studio, monkeypatch):
    def occupied(_):
        raise BlockingIOError('busy')
    monkeypatch.setattr(studio.live, 'detect', occupied)
    assert request(studio, 'POST', '/api/live', b'jpeg')[0] == 429
    def invalid(_):
        raise ValueError('bad image')
    monkeypatch.setattr(studio.live, 'detect', invalid)
    code, body = request(studio, 'POST', '/api/live', b'bad')
    assert code == 400
    assert json.loads(body)['error'] == 'bad image'


def test_live_rejects_large_frame_and_foreign_origin(studio):
    assert request(studio, 'POST', '/api/live', b'x', {'Content-Length': str(2*1024**2+1)})[0] == 413
    assert request(studio, 'POST', '/api/live', b'x', {'Origin': 'https://external.example'})[0] == 403


def test_avatar_job_and_asset(studio, monkeypatch):
    import time
    from pole_motion import avatar
    monkeypatch.setattr(avatar, 'reconstruct', lambda path: {'schema_version': 'pole-motion-avatar-0.1', 'frames': []})
    assert request(studio, 'GET', '/avatar.js')[0] == 200
    code, body = request(studio, 'POST', '/api/avatar', b'video-test')
    assert code == 202
    key = json.loads(body)['id']
    for _ in range(100):
        code, body = request(studio, 'GET', '/api/jobs/' + key)
        result = json.loads(body)
        if result['status'] == 'done':
            break
        time.sleep(.01)
    assert result['document']['schema_version'] == 'pole-motion-avatar-0.1'


def test_library_recovers_after_restart_and_deduplicates(studio, monkeypatch):
    import hashlib
    from pole_motion.archive import Archive
    calls=[]
    def extract(path,key):
        calls.append(key)
        return {'schema_version':'0.1.0','recordings':[{'source':{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}]}
    monkeypatch.setattr('pole_motion.extract.extract',extract)
    _,body=request(studio,'POST','/api/analyze',b'0123456789',{'X-Video-Name':'Lezione%20uno.mp4'})
    key=json.loads(body)['id'];wait_job(studio,key)
    _,body=request(studio,'GET','/api/library');videos=json.loads(body)['videos']
    assert len(videos)==1 and videos[0]['name']=='Lezione uno.mp4'
    assert videos[0]['results']['analysis']['id']==key
    _,body=request(studio,'POST','/api/analyze',b'0123456789')
    assert json.loads(body)=={'id':key,'cached':True}
    assert len(calls)==1
    studio.jobs.clear();studio.archive=Archive(studio.storage)
    assert wait_job(studio,key)['status']=='done'
    assert len(studio.archive.groups())==1
    assert request(studio,'GET',f'/api/library/{key}/video',headers={'Range':'bytes=2-5'})==(206,b'2345')
    assert request(studio,'GET',f'/api/library/{key}/video',headers={'Range':'bytes=-3'})==(206,b'789')
    assert request(studio,'GET',f'/api/library/{key}/video',headers={'Range':'bytes=99-'})[0]==416
    assert request(studio,'GET','/api/library/../video')[0]==404


def test_duplicate_pending_job_is_shared(studio, monkeypatch):
    import hashlib
    gate=threading.Event();calls=[]
    def extract(path,key):
        calls.append(key);gate.wait(2)
        return {'schema_version':'0.1.0','recordings':[{'source':{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}]}
    monkeypatch.setattr('pole_motion.extract.extract',extract)
    try:
        _,a=request(studio,'POST','/api/analyze',b'same')
        _,b=request(studio,'POST','/api/analyze',b'same')
        assert json.loads(a)['id']==json.loads(b)['id']
    finally:gate.set()
    wait_job(studio,json.loads(a)['id']);assert len(calls)==1


def test_archive_video_can_be_used_for_avatar_without_reupload(studio, monkeypatch):
    import hashlib
    digest=hashlib.sha256(b'original').hexdigest()
    monkeypatch.setattr('pole_motion.extract.extract',lambda path,key:{'schema_version':'0.1.0','recordings':[{'source':{'sha256':digest}}]})
    _,body=request(studio,'POST','/api/analyze',b'original');key=json.loads(body)['id'];wait_job(studio,key)
    def reconstruct(path):
        assert path.read_bytes()==b'original'
        return {'schema_version':'pole-motion-avatar-0.1','source_sha256':digest,'frames':[]}
    monkeypatch.setattr('pole_motion.avatar.reconstruct',reconstruct)
    _,body=request(studio,'POST','/api/avatar',b'reuse',{'X-Archive-ID':key})
    wait_job(studio,json.loads(body)['id'])
    assert set(studio.archive.groups()[0]['results'])=={'analysis','avatar'}


def test_pose_label_persists_and_is_in_recovered_document(studio):
    from pole_motion.archive import Archive
    key='session-'+'a'*32;digest='b'*64
    document={'schema_version':'0.1.0','poses':[],'recordings':[{'id':'record-1','source':{'sha256':digest},'holds':[{'t0':1,'t1':2}]}]}
    (studio.storage/(key+'.mp4')).write_bytes(b'video')
    (studio.storage/(key+'.json')).write_text(json.dumps(document))
    studio.archive.register(key)
    payload={'sha256':digest,'t0':1,'t1':2,'name':' Gemini '}
    code,body=request(studio,'POST','/api/pose-label',json.dumps(payload).encode())
    assert code==200 and json.loads(body)['name']=='Gemini'
    pose_id=json.loads(body)['id']
    payload['name']='Gemini sinistro'
    assert request(studio,'POST','/api/pose-label',json.dumps(payload).encode())[0]==200
    studio.archive=Archive(studio.storage)
    code,body=request(studio,'GET',f'/api/library/{key}/document')
    poses=json.loads(body)['poses']
    assert len(poses)==1 and poses[0]['id']==pose_id
    assert poses[0]['name']=='Gemini sinistro' and poses[0]['review']=={'status':'draft'}
    assert poses[0]['references']==[{'recording_id':'record-1','t':1.5}]
    assert wait_job(studio,key)['document']['poses']==poses
    payload['t1']=3
    assert request(studio,'POST','/api/pose-label',json.dumps(payload).encode())[0]==400
    payload['t1']=2;payload['name']=' '
    assert request(studio,'POST','/api/pose-label',json.dumps(payload).encode())[0]==400
    assert request(studio,'POST','/api/pose-label',json.dumps(payload).encode(),{'Origin':'https://external.example'})[0]==403
