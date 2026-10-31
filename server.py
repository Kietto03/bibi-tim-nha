import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from crawler import crawl_source, dedupe

ROOT=Path(__file__).parent
LOCK=threading.Lock()
STATE=ROOT/'data'/'listings.json'
STALE_DAYS=3
running=False
def load():
    try: return json.loads(STATE.read_text('utf-8'))
    except (FileNotFoundError,ValueError): return {'listings':[],'sources':[], 'updatedAt':None}
def merge(previous,fresh,now):
    """Keep firstSeen across runs; listings beyond the scanned pages stay until unseen for STALE_DAYS."""
    old={x['id']:x for x in previous}
    merged=[{**x,'firstSeen':old.get(x['id'],{}).get('firstSeen') or x['seenAt']} for x in fresh]
    ids={x['id'] for x in merged}
    for x in previous:
        if x['id'] in ids: continue
        age=(now-datetime.fromisoformat(x.get('seenAt') or now.isoformat())).days
        if age<STALE_DAYS: merged.append(x)
    return dedupe(merged)
def refresh():
    global running
    try:
        configs=json.loads((ROOT/'sources.json').read_text('utf-8'))
        with ThreadPoolExecutor(max_workers=len(configs)) as pool: results=list(pool.map(crawl_source,configs))
        previous=load(); now=datetime.now(timezone.utc)
        data={'listings':merge(previous['listings'],[x for items,_ in results for x in items],now),'sources':[s for _,s in results],'updatedAt':now.isoformat()}
        STATE.parent.mkdir(exist_ok=True); temp=STATE.with_suffix('.tmp'); temp.write_text(json.dumps(data,ensure_ascii=False),'utf-8'); temp.replace(STATE)
    finally:
        with LOCK: running=False
def start_refresh():
    global running
    with LOCK:
        if running: return False
        running=True
    threading.Thread(target=refresh,daemon=True).start(); return True
def schedule(minutes):
    def loop():
        while True:
            start_refresh(); time.sleep(minutes*60)
    threading.Thread(target=loop,daemon=True).start()
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/'public'),**kw)
    def send_json(self,data,status=200):
        body=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if urlsplit(self.path).path=='/api/listings': return self.send_json({**load(),'running':running})
        if urlsplit(self.path).path=='/api/sources': return self.send_json(json.loads((ROOT/'sources.json').read_text('utf-8')))
        return super().do_GET()
    def do_POST(self):
        # Loopback app: reject cross-origin browser mutations.
        if self.headers.get('Origin') and self.headers['Origin']!='http://'+self.headers.get('Host',''): return self.send_json({'error':'Origin không hợp lệ'},403)
        if self.path!='/api/crawl': return self.send_json({'error':'Không tìm thấy'},404)
        start_refresh(); self.send_json({'running':True},202)
if __name__=='__main__':
    port=int(os.environ.get('PORT','8080')); print(f'Bibi tìm nhà: http://localhost:{port}',flush=True)
    minutes=float(os.environ.get('CRAWL_EVERY_MINUTES','30'))
    if minutes>0: schedule(minutes)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
