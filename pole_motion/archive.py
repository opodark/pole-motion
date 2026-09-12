"""Persistent, hash-addressed index of local Studio analyses."""
import json
import re
import threading
from pathlib import Path

KEY = re.compile(r"session-[a-f0-9]{32}\Z")

class Archive:
    def __init__(self, storage):
        self.storage = Path(storage)
        self.entries = {}
        self.lock = threading.RLock()
        for path in self.storage.glob('session-*.json'):
            if not KEY.fullmatch(path.stem):
                continue
            try:
                self.register(path.stem)
            except (ValueError, KeyError, OSError, IndexError, TypeError):
                continue

    def register(self, key, name=None, elapsed=None):
        if not KEY.fullmatch(key):
            raise ValueError('Invalid archive ID')
        path = self.storage / (key+'.json')
        data = json.loads(path.read_text(encoding='utf-8'))
        kind = 'avatar' if data.get('schema_version') == 'pole-motion-avatar-0.1' else 'analysis'
        source = data.get('source_sha256') if kind == 'avatar' else data.get('recordings', [{}])[0].get('source', {}).get('sha256')
        if not source:
            return
        video = self.storage / (key+'.mp4')
        if not video.is_file():
            return
        meta = self.storage / (key+'.meta.json')
        previous = json.loads(meta.read_text(encoding='utf-8')) if meta.exists() else {}
        entry = dict(id=key, sha256=source, kind=kind,
                     name=name or previous.get('name') or 'Video salvato',
                     size=video.stat().st_size, created=path.stat().st_mtime,
                     elapsed_s=elapsed if elapsed is not None else previous.get('elapsed_s'),
                     engine='MediaPipe CPU')
        with self.lock:
            self.entries[key] = entry
        if name is not None:
            temp=meta.with_suffix('.tmp')
            temp.write_text(json.dumps(entry), encoding='utf-8'); temp.replace(meta)

    def get(self, key):
        with self.lock:
            return dict(self.entries[key]) if key in self.entries else None

    def find(self, digest, kind):
        with self.lock:
            return next((dict(e) for e in sorted(self.entries.values(),key=lambda e:e['created'],reverse=True)
                         if e['sha256']==digest and e['kind']==kind),None)

    def groups(self):
        with self.lock:
            groups={}
            for e in sorted(self.entries.values(),key=lambda e:e['created'],reverse=True):
                g=groups.setdefault(e['sha256'],dict(sha256=e['sha256'],name=e['name'],size=e['size'],created=e['created'],video_id=e['id'],results={}))
                g['results'].setdefault(e['kind'],dict(e))
            return list(groups.values())

    def label_hold(self, digest, t0, t1, name):
        if not isinstance(name,str) or not 1<=len(name.strip())<=120:
            raise ValueError('Inserisci un nome da 1 a 120 caratteri')
        entry=self.find(digest,'analysis')
        if not entry:raise ValueError('Salva prima l analisi di questo video nello Studio')
        document=json.loads((self.storage/(entry['id']+'.json')).read_text(encoding='utf-8'))
        record=document['recordings'][0]
        if not any(h['t0']==t0 and h['t1']==t1 for h in record['holds']):
            raise ValueError('Fermo non presente nella analisi salvata')
        import hashlib
        label_id='pose-'+hashlib.sha256(f'{digest}:{t0:.6f}:{t1:.6f}'.encode()).hexdigest()[:24]
        path=self.storage/'pose-labels.json'
        with self.lock:
            labels=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            item=dict(id=label_id,sha256=digest,t0=t0,t1=t1,name=name.strip(),status='draft')
            labels[label_id]=item
            temp=path.with_suffix('.tmp');temp.write_text(json.dumps(labels,ensure_ascii=False),encoding='utf-8');temp.replace(path)
        return item

    def document(self,key):
        if not self.get(key):raise ValueError('Analisi non trovata')
        document=json.loads((self.storage/(key+'.json')).read_text(encoding='utf-8'))
        path=self.storage/'pose-labels.json'
        if document.get('schema_version')!='0.1.0' or not path.exists():return document
        with self.lock:labels=json.loads(path.read_text(encoding='utf-8'))
        for record in document['recordings']:
            for item in labels.values():
                if item['sha256']!=record['source'].get('sha256'):continue
                if not any(h['t0']==item['t0'] and h['t1']==item['t1'] for h in record['holds']):continue
                pose=dict(id=item['id'],name=item['name'],aliases=[],description='',references=[{'recording_id':record['id'],'t':(item['t0']+item['t1'])/2}],review={'status':'draft'})
                document['poses']=[p for p in document['poses'] if p['id']!=item['id']]+[pose]
        return document
