"""Generate a self-contained Pages artifact; no local Python server required."""
import argparse
import json
import os
import shutil
import time
from pathlib import Path
from server import refresh, load

ROOT = Path(__file__).parent
def build(crawl=False):
    if crawl:
        refresh()
    target = ROOT / 'dist'
    target.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'public', target, dirs_exist_ok=True)
    html = (target / 'index.html').read_text('utf-8')
    html = html.replace('href="/"', 'href="./"').replace('href="/style.css"', 'href="./style.css"').replace('src="/app.js"', 'src="./app.js"').replace('src="/assets/', 'src="./assets/')
    html = html.replace('<script src="./app.js"', '<script>window.BIBI_STATIC=true;</script><script src="./app.js"')
    # Cache-bust: GitHub Pages caches assets ~10 minutes, so stale JS could show old data.
    version = os.environ.get('GITHUB_SHA', str(int(time.time())))[:12]
    html = html.replace('href="./style.css"', f'href="./style.css?v={version}"').replace('src="./app.js"', f'src="./app.js?v={version}"')
    (target / 'index.html').write_text(html, 'utf-8')
    js = (target / 'app.js').read_text('utf-8').replace("'/assets/", "'./assets/")
    js = js.replace("fetch('/api/listings'", "fetch(window.BIBI_STATIC?'./listings.json':'/api/listings'")
    js = js.replace("fetch('/api/sources')", "fetch(window.BIBI_STATIC?'./sources.json':'/api/sources')")
    js = js.replace("$('#refresh').onclick=async()=>{", "$('#refresh').onclick=async()=>{if(window.BIBI_STATIC){demo=false;await load();return;}")
    js = js.replace("'Cập nhật tin'", "(window.BIBI_STATIC?'Tải lại tin':'Cập nhật tin')")
    js = js.replace("'Chưa kết nối được máy chủ. Kiểm tra python server.py rồi tải lại trang.'", "(window.BIBI_STATIC?'Chưa tải được dữ liệu. Hãy tải lại trang.':'Chưa kết nối được máy chủ. Kiểm tra python server.py rồi tải lại trang.')")
    js = js.replace("'Chưa có tin thật phù hợp. Bấm “Cập nhật tin thật” rồi xem trạng thái nguồn.'", "(window.BIBI_STATIC?'Chưa có tin thật phù hợp. Xem trạng thái nguồn; dữ liệu được cập nhật bởi GitHub Actions.':'Chưa có tin thật phù hợp. Bấm “Cập nhật tin thật” rồi xem trạng thái nguồn.')")
    (target / 'app.js').write_text(js, 'utf-8')
    (target / 'sources.json').write_text((ROOT / 'sources.json').read_text('utf-8'), 'utf-8')
    (target / 'listings.json').write_text(json.dumps({**load(), 'running': False}, ensure_ascii=False), 'utf-8')
    (target / '.nojekyll').touch()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--crawl', action='store_true')
    build(parser.parse_args().crawl)
