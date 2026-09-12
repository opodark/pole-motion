"""Local video review studio. Run with python -m pole_motion.studio."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import hashlib
import time
import re
import os
import shutil
import mimetypes
from pathlib import Path
import threading
from urllib.parse import urlparse, unquote, parse_qs
import uuid
from .live import LivePose
from .archive import Archive, KEY

STATIC = Path(__file__).with_name('studio_web')


class StudioServer(ThreadingHTTPServer):
    def __init__(self, address, storage):
        super().__init__(address, Handler)
        self.storage = Path(storage)
        self.storage.mkdir(parents=True, exist_ok=True)
        self.archive = Archive(self.storage)
        self.pending = {}
        self.names = {}
        self.jobs = {}
        self.lock = threading.Lock()
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.live = LivePose()

    def analyze(self, key, path, avatar=False):
        started = time.monotonic()
        with self.lock:
            self.jobs[key] = {'status': 'running'}
        logging.info('Job %s started: %s', key, 'avatar-3d' if avatar else 'analysis-2d')
        try:
            if avatar:
                from .avatar import reconstruct
                document = reconstruct(path)
            else:
                from .extract import extract
                document = extract(path, key)
            target=self.storage / f'{key}.json'
            temporary=target.with_suffix('.tmp')
            temporary.write_text(json.dumps(document, allow_nan=False), encoding='utf-8')
            temporary.replace(target)
            self.archive.register(key, self.names.get(key, 'Video salvato'), round(time.monotonic()-started,2))
            result = {'status': 'done', 'document': document}
            logging.info('Job %s completed: schema=%s', key, document.get('schema_version'))
        except Exception as exc:
            logging.exception('Job %s failed', key)
            result = {'status': 'error', 'error': str(exc)}
        with self.lock:
            self.jobs[key] = result
            self.pending = {k:v for k,v in self.pending.items() if v != key}


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, value):
        body = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path).path
        if route == '/api/library':
            self.reply(200, {'videos': self.server.archive.groups(), 'engine': 'MediaPipe CPU'})
            return
        if route.startswith('/api/library/'):
            parts = route.split('/')
            entry = self.server.archive.get(parts[3]) if len(parts)==5 else None
            if not entry or parts[4] not in ('video','document'):
                self.reply(404, {'error':'Analisi non trovata'}); return
            if parts[4]=='document':
                self.reply(200, self.server.archive.document(entry['id']))
            else:
                self.serve_video(self.server.storage/(entry['id']+'.mp4'))
            return
        if route.startswith('/api/jobs/'):
            with self.server.lock:
                key=route.rsplit('/', 1)[-1]
                result = self.server.jobs.get(key)
            if result is None and self.server.archive.get(key):
                result={'status':'done','document':json.loads((self.server.storage/(key+'.json')).read_text(encoding='utf-8'))}
            if result and result.get('status')=='done' and self.server.archive.get(key):
                result={'status':'done','document':self.server.archive.document(key)}
            self.reply(200 if result else 404, result or {'error': 'Analisi non trovata'})
            return
        assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                  '/live-effects.js': ('live-effects.js', 'text/javascript'),
                  '/avatar.js': ('avatar.js', 'text/javascript'),
                  '/avatar-3d.js': ('avatar-3d.js', 'text/javascript'),
                  '/style.css': ('style.css', 'text/css')}
        if route.startswith(('/vendor/', '/models/')):
            relative = route.lstrip('/')
            candidate = (STATIC / relative).resolve()
            if candidate.is_relative_to(STATIC.resolve()) and candidate.is_file():
                body = candidate.read_bytes()
                mime = mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
                self.send_response(200)
                self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        if route not in assets:
            self.reply(404, {'error': 'Not found'})
            return
        name, mime = assets[route]
        body = (STATIC / name).read_bytes()
        self.send_response(200)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_video(self, path):
        size=path.stat().st_size; start=0; end=size-1; code=200
        value=self.headers.get('Range')
        if value:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
            if not match or not any(match.groups()):
                self.send_response(416); self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
            a,b=match.groups()
            if a: start=int(a);end=min(int(b),size-1) if b else size-1
            else: start=max(0,size-int(b))
            if start>end or start>=size:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
            code=206
        self.send_response(code);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(end-start+1))
        if code==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with path.open('rb') as stream:
                stream.seek(start);remaining=end-start+1
                while remaining:
                    chunk=stream.read(min(1024*1024,remaining))
                    if not chunk:break
                    self.wfile.write(chunk);remaining-=len(chunk)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            pass

    def do_POST(self):
        # Only same-origin browser requests may send local data or start inference.
        origin = self.headers.get('Origin')
        host = self.headers.get('Host', '')
        port = self.server.server_port
        if host not in (f'127.0.0.1:{port}', f'localhost:{port}') or (origin and origin != 'http://' + host):
            self.reply(403, {'error': 'Origine non consentita'})
            return
        if self.path == '/api/pose-label':
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096:raise ValueError('Richiesta non valida')
                payload=json.loads(self.rfile.read(size))
                result=self.server.archive.label_hold(payload['sha256'],payload['t0'],payload['t1'],payload['name'])
                self.reply(200,result)
            except (ValueError,KeyError,TypeError) as exc:
                self.reply(400,{'error':str(exc)})
            return
        if self.path not in ('/api/analyze', '/api/live', '/api/avatar'):
            self.reply(404, {'error': 'Not found'})
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            size = 0
        limit = 2 * 1024 ** 2 if self.path == '/api/live' else 1024 ** 3
        if not 0 < size <= limit:
            self.reply(413, {'error': 'Seleziona un video di dimensione inferiore a 1 GB.'})
            return
        if self.path == '/api/live':
            try:
                session = self.headers.get('X-Live-Session', '')[:80]
                pole = self.headers.get('X-Pole-X')
                pole = float(pole) if pole else None
                if pole is not None and not 0 <= pole <= 1:
                    raise ValueError('Posizione palo non valida')
                encoded = self.rfile.read(size)
                result = self.server.live.detect(encoded, session, pole) if session else self.server.live.detect(encoded)
                self.reply(200, result)
            except BlockingIOError as exc:
                self.reply(429, {'error': str(exc)})
            except Exception as exc:
                self.reply(400, {'error': str(exc)})
            return
        kind='avatar' if self.path=='/api/avatar' else 'analysis'
        key = 'session-' + uuid.uuid4().hex
        path = self.server.storage / f'{key}.mp4'
        try:
            source_id=self.headers.get('X-Archive-ID')
            if source_id:
                entry=self.server.archive.get(source_id)
                if not entry:raise ValueError('Video archiviato non trovato')
                if size>1024:raise ValueError('Richiesta archivio non valida')
                self.rfile.read(size)
                source=self.server.storage/(source_id+'.mp4')
                try:os.link(source,path)
                except OSError:shutil.copyfile(source,path)
                source_hash=entry['sha256']
            else:
                digest=hashlib.sha256()
                with path.open('wb') as stream:
                    remaining=size
                    while remaining:
                        chunk=self.rfile.read(min(1024*1024,remaining))
                        if not chunk:raise ValueError('Caricamento interrotto')
                        stream.write(chunk);digest.update(chunk);remaining-=len(chunk)
                source_hash=digest.hexdigest()
            cache_key=(source_hash,kind)
            with self.server.lock:
                cached=self.server.archive.find(*cache_key)
                existing=cached['id'] if cached else self.server.pending.get(cache_key)
                if existing:
                    path.unlink();self.reply(202,{'id':existing,'cached':bool(cached)});return
                self.server.pending[cache_key]=key
                self.server.names[key]=unquote(self.headers.get('X-Video-Name','Video salvato'))[:240]
                self.server.jobs[key] = {'status': 'queued'}
            self.server.worker.submit(self.server.analyze, key, path, self.path == "/api/avatar")
            self.reply(202, {'id': key})
        except Exception as exc:
            path.unlink(missing_ok=True)
            self.reply(400, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--storage', type=Path, default=Path('outputs/studio'))
    args = parser.parse_args()
    args.storage.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.FileHandler(args.storage / 'studio.log', encoding='utf-8'), logging.StreamHandler()])
    server = StudioServer(('127.0.0.1', args.port), args.storage)
    print(f'Pole Motion Studio: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.worker.shutdown(wait=True)
        server.live.close()


if __name__ == '__main__':
    main()
