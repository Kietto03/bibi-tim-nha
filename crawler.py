"""Bounded public-page crawler. No bypasses, credentials or private endpoints."""
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

AGENT = 'BibiHomeBot/1.0'
BUDGET = 150
SHALLOW = 5
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','source','track','wbr'}
LISTING_TYPES = ('realestatelisting','apartment','residence','accommodation','product','offer','house','singlefamilyresidence')

def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value).lower().replace('đ','d')) if unicodedata.category(c) != 'Mn')

def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', ''))

AREA = re.compile(r'\b(quan\s*2|q\.?\s*2|thao dien|an phu(?! dong)|binh trung|thanh my loi|cat lai|thu thiem|an khanh|binh an|binh khanh)\b')

# Lưu rộng hơn khoảng Bibi tìm (8–12 triệu) để web lọc lại được; khoảng mặc định nằm ở app.js.
MIN_PRICE, MAX_PRICE = 5_000_000, 25_000_000

# Tiêu đề nêu quận khác / dự án ngoài Quận 2 (Khang Điền, Vinhomes Grand Park ở Quận 9...) mà không nhắc Quận 2 thì loại,
# kể cả khi mô tả có câu kiểu "gần Quận 2".
ELSEWHERE = re.compile(r'\b(quan\s*(?:[013-9]|1[0-2])|q\.?\s*(?:[013-9]|1[0-2]))\b|\b(phu huu|long truong|truong thanh|phuoc long|tang nhon phu|hiep phu|long thanh my|khang dien|safira|jamila|vinhomes grand park|binh thanh|nha be|go vap|tan binh|phu nhuan)\b')

def eligible(item):
    title = fold(item.get('title','')).replace('_',' ')
    if ELSEWHERE.search(title) and not AREA.search(title) and not locate({'title':title}): return False
    area = AREA.search(fold(str(item.get('address','')) + ' ' + item.get('title','')))
    apartment = any(x in fold(item.get('title','') + ' ' + item.get('kind','')) for x in ['can ho','chung cu','apartment','condominium'])
    return bool(area and apartment and MIN_PRICE <= item.get('price',0) <= MAX_PRICE and item.get('monthly',False))

GEO_RANK = {'project':0,'near':1,'street':2,'ward':3}
_places = None

def places():
    """geo.json (built by geocode.py from OpenStreetMap), most specific aliases first."""
    global _places
    if _places is None:
        try: raw = json.loads((Path(__file__).parent/'geo.json').read_text('utf-8'))['places']
        except (FileNotFoundError, ValueError, KeyError): raw = []
        # 'thao dien' cũng khớp 'thaodien', 'thao-dien'; "d lusso" khớp "d’lusso".
        _places = sorted(((re.compile(r'\b'+alias.replace(' ',"[\\s'’-]*")+r'\b'), p) for p in raw for alias in p['aliases']),
                         key=lambda x:(GEO_RANK.get(x[1]['kind'],9), -len(x[0].pattern)))
    return _places

def locate(item):
    """Approximate map position from project / street / ward names; None when only 'Quận 2' is known."""
    text = fold(item.get('title','') + ' ' + str(item.get('address','')))
    for pattern, place in places():
        if pattern.search(text):
            return {'lat':place['lat'],'lon':place['lon'],'place':place['name'],'level':place['kind']}
    return None

def parse_price(text):
    """'9,5 triệu' / '12 tr/tháng' / '8.500.000 đ' -> VND; None when absent, negotiable or not VND."""
    t = fold(text)
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(ty|trieu|tr)\b', t)
    if m:
        n = float(m.group(1).replace(',','.'))
        return n * (1e9 if m.group(2)=='ty' else 1e6)
    m = re.search(r'(\d{1,3}(?:[.,]\d{3}){2,})\s*(d|vnd|dong)\b', t)
    return float(re.sub(r'[.,]','',m.group(1))) if m else None

def parse_number(pattern, text):
    m = re.search(pattern, fold(text))
    return float(m.group(1).replace(',','.')) if m else None

VN = timezone(timedelta(hours=7))
UNITS = {'phut':timedelta(minutes=1),'gio':timedelta(hours=1),'ngay':timedelta(days=1),'tuan':timedelta(weeks=1),'thang':timedelta(days=30),'nam':timedelta(days=365)}

def parse_posted(text, now=None, absolute=True):
    """'2 giờ trước' / 'Hôm qua' / '17/9/2026, lúc: 11 giờ 3 phút' / '2026-10-31' -> ISO in UTC+7, or None.
    Day-precision sources ('Hôm nay', '3 ngày trước', '29/10/2026') give a date only ('2026-10-29'), so the page
    never shows a made-up hour. Absolute dates older than 3 years (or in the future) are ignored: cards also show
    build years, move-in dates..."""
    now = (now or datetime.now(VN)).astimezone(VN); t = fold(text)
    m = re.search(r'(\d+)\s*(phut|gio|ngay|tuan|thang|nam)\s*truoc', t)
    if m:
        when = now - int(m.group(1))*UNITS[m.group(2)]
        return when.isoformat(timespec='minutes') if m.group(2) in ('phut','gio') else when.date().isoformat()
    if 'vua xong' in t: return now.isoformat(timespec='minutes')
    if 'hom nay' in t: return now.date().isoformat()
    if 'hom qua' in t: return (now - timedelta(days=1)).date().isoformat()
    if not absolute: return None
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})(?:[t ](\d{2}):(\d{2}))?', t) or re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', t)
    if not m: return None
    timed = False
    try:
        if len(m.group(1)) == 4:
            timed = bool(m.group(4))
            when = datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)),int(m.group(4) or 12),int(m.group(5) or 0),tzinfo=VN)
        else:
            when = datetime(int(m.group(3)),int(m.group(2)),int(m.group(1)),12,tzinfo=VN)
            clock = re.search(r'(\d{1,2})\s*(?:gio|:|h)\s*(\d{1,2})', t[m.end():m.end()+30]) or re.search(r'(\d{1,2}):(\d{2})', t[max(0,m.start()-8):m.start()])
            if clock and int(clock.group(1)) < 24 and int(clock.group(2)) < 60:
                when = when.replace(hour=int(clock.group(1)),minute=int(clock.group(2))); timed = True
    except ValueError: return None
    if not now - timedelta(days=3*365) <= when <= now + timedelta(hours=12): return None
    return when.isoformat(timespec='minutes') if timed else when.date().isoformat()

def posted_in(node):
    """Prefer an element that looks like a date label; fall back to relative phrases anywhere in the card."""
    for n in node.iter():
        cls = n.classes()
        if re.search(r'date|time|created|publish|posted|ngay-dang', cls) and not re.search(r'selling|rating|deadline', cls):
            found = parse_posted(n.attrs.get('datetime') or n.attrs.get('content') or n.text())
            if found: return found
    for n in node.iter():  # an element holding nothing but a date, e.g. <span>17/09/2026</span>
        if re.fullmatch(r'\s*(\d{1,2}:\d{2}\s*)?\d{1,2}/\d{1,2}/\d{4}(,?\s*\d{1,2}:\d{2})?\s*', n.text() or 'x'):
            found = parse_posted(n.text())
            if found: return found
    text = node.text()
    m = re.search(r'(?:ngay dang|dang ngay|cap nhat)\s*:?\s*(.{0,40})', fold(text))
    return parse_posted(text, absolute=False) or (parse_posted(m.group(1)) if m else None)

class Node:
    __slots__ = ('tag','attrs','children','parent')
    def __init__(self, tag, attrs, parent):
        self.tag=tag; self.attrs=attrs; self.children=[]; self.parent=parent
    def text(self):
        out=[]
        def go(n):
            for c in n.children:
                if isinstance(c,str): out.append(c)
                elif c.tag not in ('script','style','noscript'): go(c)
        go(self); return re.sub(r'\s+',' ',' '.join(out)).strip()
    def iter(self):
        for c in self.children:
            if isinstance(c,Node): yield c; yield from c.iter()
    def classes(self): return fold(self.attrs.get('class','') + ' ' + self.attrs.get('itemprop',''))

class Page(HTMLParser):
    """Small DOM: links, JSON-LD blocks and a node tree for microdata / listing cards."""
    def __init__(self, text):
        super().__init__(convert_charrefs=True); self.links=[]; self.blocks=[]; self.capture=False; self.buf=''
        self.root=Node('root',{},None); self.cur=self.root; self.feed(text)
    def handle_starttag(self, tag, attrs):
        a={k:(v or '') for k,v in attrs}
        if tag=='a' and a.get('href'): self.links.append(a['href'])
        if tag=='script' and a.get('type','').lower()=='application/ld+json': self.capture=True; self.buf=''
        node=Node(tag,a,self.cur); self.cur.children.append(node)
        if tag not in VOID: self.cur=node
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID: self.cur=self.cur.parent
    def handle_data(self, data):
        if self.capture: self.buf+=data
        self.cur.children.append(data)
    def handle_endtag(self, tag):
        if tag=='script' and self.capture:
            try: self.blocks.append(json.loads(self.buf))
            except ValueError: pass
            self.capture=False
        n=self.cur
        while n is not self.root and n.tag!=tag: n=n.parent
        if n is not self.root: self.cur=n.parent

def walk(value):
    if isinstance(value,dict):
        yield value
        for child in value.values(): yield from walk(child)
    elif isinstance(value,list):
        for child in value: yield from walk(child)

def image_of(node, base):
    for img in [node] if node.tag=='img' else [n for n in node.iter() if n.tag in ('img','source')]:
        for key in ('data-src','data-original','data-lazy-src','src','srcset','data-srcset'):
            value=img.attrs.get(key,'').strip().split(',')[0].split(' ')[0]
            if value and not value.startswith('data:'):
                url=urljoin(base,value)
                if url.startswith('https://'): return url
    return ''

def make_item(url, source, title, address, kind, price, monthly, image, area, bedrooms, posted=None):
    return {'postedAt':posted,'id':hashlib.sha256(canonical(url).encode()).hexdigest()[:16],'title':re.sub(r'\s+',' ',str(title)).strip(),'address':re.sub(r'\s+',' ',str(address)).strip(),'kind':str(kind),
            'price':price,'monthly':monthly,'image':image,'url':url,'source':source,'area':area,'bedrooms':bedrooms,'seenAt':datetime.now(timezone.utc).isoformat()}

def from_jsonld(page, url, source):
    results=[]
    for block in page.blocks:
        for obj in walk(block):
            offers=obj.get('offers')
            if isinstance(offers,list): offers=offers[0] if offers else None
            if not isinstance(offers,dict): continue
            spec=offers.get('priceSpecification',{})
            if not isinstance(spec,dict): spec={}
            raw=offers.get('price',spec.get('price',0))
            try: price=float(str(raw).replace(',',''))
            except (ValueError,TypeError): continue
            if offers.get('priceCurrency',spec.get('priceCurrency','')) != 'VND': continue
            title=obj.get('name',''); description=obj.get('description','')
            period=fold(str(spec.get('unitText',''))+' '+str(spec.get('billingDuration',''))+' '+str(description)+' '+str(title))
            monthly=bool(re.search(r'thang|month|\bMON\b',period,re.I))
            address=obj.get('address','')
            if isinstance(address,dict): address=', '.join(str(address.get(k,'')) for k in ['streetAddress','addressLocality','addressRegion'])
            image=obj.get('image','')
            if isinstance(image,list): image=image[0] if image else ''
            if isinstance(image,dict): image=image.get('url','')
            target=urljoin(url, str(obj.get('url') or offers.get('url') or url))
            if urlsplit(target).netloc != urlsplit(url).netloc: continue
            area=obj.get('floorSize',{}).get('value') if isinstance(obj.get('floorSize'),dict) else None
            results.append(make_item(target,source,title,address,obj.get('@type',''),price,monthly,image if isinstance(image,str) and image.startswith('https://') else '',area,obj.get('numberOfBedrooms'),parse_posted(str(obj.get('datePosted',''))) if obj.get('datePosted') else None))
    return results

def from_microdata(page, url, source, config):
    """schema.org itemscope listings (e.g. Alonhadat)."""
    results=[]
    for node in page.root.iter():
        if 'itemscope' not in node.attrs or not any(t in fold(node.attrs.get('itemtype','')) for t in LISTING_TYPES[:4]): continue
        props={}
        for n in node.iter():
            key=n.attrs.get('itemprop')
            if key and key not in props: props[key]=n
        link=props.get('url')
        href=link.attrs.get('href') if link is not None else None
        if not href: continue
        target=urljoin(url,href)
        if urlsplit(target).netloc != urlsplit(url).netloc: continue
        price_node=props.get('price')
        text=node.text()
        price=None
        if price_node is not None:
            try: price=float(price_node.attrs.get('content') or 'x')
            except ValueError: price=parse_price(price_node.text())
        address=' '.join(n.text() for n in node.iter() if 'address' in n.classes() or n.attrs.get('itemprop')=='address')
        title=props['name'].text() if 'name' in props else ''
        price_text=fold(price_node.parent.text() if price_node is not None and price_node.parent else text)
        monthly=bool(re.search(r'thang|month',price_text)) or (config.get('rent') and not re.search(r'/\s*(ngay|dem|m2)',price_text))
        dated=props.get('datePosted')
        posted=parse_posted(dated.attrs.get('datetime') or dated.attrs.get('content') or dated.text()) if dated is not None else None
        results.append(make_item(target,source,title,address,config.get('kind',''),price or 0,bool(monthly),image_of(node,url),
                                 parse_number(r'(\d+(?:[.,]\d+)?)\s*m\s?(?:2|²)',text),parse_number(r'(\d+)\s*(?:pn|phong ngu)\b',text),posted or posted_in(node)))
    return results

def from_cards(page, url, source, config):
    """Listing cards: the largest element that contains exactly one detail link."""
    detail=re.compile(config['detail'])
    host=urlsplit(url).netloc
    anchors={}
    for n in page.root.iter():
        if n.tag=='a' and n.attrs.get('href'):
            target=canonical(urljoin(url,n.attrs['href']))
            if urlsplit(target).netloc==host and detail.search(target): anchors.setdefault(target,[]).append(n)
    def targets(n): return {canonical(urljoin(url,a.attrs['href'])) for a in n.iter() if a.tag=='a' and a.attrs.get('href') and detail.search(canonical(urljoin(url,a.attrs['href'])))}
    results=[]
    for target,nodes in anchors.items():
        card=nodes[0]
        while card.parent is not None and card.parent is not page.root and targets(card.parent)<={target}: card=card.parent
        text=card.text()
        if len(text)>3000: continue
        heading=next((n for n in card.iter() if n.tag in ('h1','h2','h3','h4') or 'title' in n.classes()),None)
        title=max((a.attrs.get('title','') for a in nodes),key=len) or (heading.text() if heading is not None else '') or max((a.text() for a in nodes),key=len)
        price_node=next((n for n in card.iter() if re.search(r'\b(price|gia)\b',n.classes()) and parse_price(n.text())),None)
        price_text=price_node.text() if price_node is not None else text.replace(title,' ')
        price=parse_price(price_text)
        if not price: continue
        folded=fold(price_text)
        monthly=bool(re.search(r'thang|month',folded)) or (config.get('rent') and not re.search(r'/\s*(ngay|dem|tuan|m2)|\bty\b',folded))
        # No address element: label with the source's area only when the card itself mentions it.
        address=' '.join(n.text() for n in card.iter() if re.search(r'addr|address|location|dia-?chi|khu-?vuc',n.classes())) or (config.get('area','Quận 2') if AREA.search(fold(text)) else '')
        results.append(make_item(target,source,title,address,config.get('kind',''),price,bool(monthly),image_of(card,url),
                                 parse_number(r'(\d+(?:[.,]\d+)?)\s*m\s?(?:2|²)',text),parse_number(r'(\d+)\s*(?:pn|phong ngu|phong)\b',text),posted_in(card)))
    return results

def extract(html, url, source, config=None):
    config=config or {}
    page=Page(html)
    found=from_jsonld(page,url,source)+from_microdata(page,url,source,config)
    if config.get('detail'): found+=from_cards(page,url,source,config)
    # Cùng một tin có thể đến từ JSON-LD, microdata và thẻ tin: gộp, lấp các trường còn trống.
    merged={}
    for x in found:
        key=canonical(x['url'])
        if key in merged: merged[key].update({k:v for k,v in x.items() if v and not merged[key].get(k)})
        else: merged[key]=dict(x)
    return [x for x in dedupe(list(merged.values())) if eligible(x)]

def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':AGENT,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Accept-Language':'vi,en;q=0.8'}),timeout=20) as response:
        if urlsplit(response.url).netloc != urlsplit(url).netloc: raise ValueError('Nguồn chuyển sang tên miền khác')
        return response.read(3_000_000).decode('utf-8',errors='replace')

def robots_for(origin):
    """RFC 9309: 4xx (except 401/403) means no restrictions; 401/403/5xx means stay out."""
    robot=RobotFileParser()
    try: robot.parse(fetch(urljoin(origin,'/robots.txt')).splitlines())
    except HTTPError as error:
        robot.parse([] if 400<=error.code<500 and error.code not in (401,403) else ['User-agent: *','Disallow: /'])
    return robot

def page_urls(config, deep=True):
    entry=urljoin(config['origin'],config['entry'])
    pattern=config.get('page')
    urls=[entry]
    for n in range(2,(config.get('pages',1) if deep else min(config.get('pages',1),SHALLOW))+1):
        if not pattern: break
        ext=re.search(r'\.html?$',entry)
        if pattern[0] in '?&': urls.append(entry+pattern.format(n=n))
        elif ext: urls.append(entry[:ext.start()]+pattern.format(n=n)+ext.group())
        else: urls.append(entry.rstrip('/')+pattern.format(n=n))
    return urls

def crawl_source(config, deep=True):
    """deep: every configured page (a few times a day); otherwise only the first SHALLOW pages, where new posts appear."""
    origin=config['origin']; started=time.monotonic()
    urls=page_urls(config,deep)
    status={'id':config['id'],'name':config['name'],'url':urls[0],'count':0,'pages':0,'state':'error','message':''}
    items=[]
    try:
        robot=robots_for(origin)
        if not robot.can_fetch(AGENT,urls[0]): raise ValueError('robots.txt không cho phép thu thập trang này')
        delay=max(2,float(robot.crawl_delay(AGENT) or 0))
        for i,url in enumerate(urls):
            if time.monotonic()-started>BUDGET or not robot.can_fetch(AGENT,url): break
            if i: time.sleep(delay)
            try: html=fetch(url)
            except Exception:
                if i: break
                raise
            status['pages']+=1
            found=extract(html,url,config['name'],config)
            items.extend(found)
        items=dedupe(items)
        status.update(state='ok' if items else 'empty',message=f"Đã đọc {status['pages']} trang danh sách" if items else f"Đã đọc {status['pages']} trang nhưng chưa có căn hộ Quận 2 trong khoảng 5–25 triệu.")
    except HTTPError as error:
        status.update(state='blocked' if error.code in (401,403,429) else 'error',
                      message='Nguồn chặn truy cập tự động (HTTP %d); Bibi không vượt chặn.'%error.code if error.code in (401,403,429) else 'HTTP %d'%error.code)
    except Exception as error: status['message']=str(error)[:240]
    status['count']=len(items); status['checkedAt']=datetime.now(timezone.utc).isoformat()
    return items,status

def dedupe(items):
    seen=set(); result=[]
    for item in items:
        # Conservative: same canonical URL or exact normalized title/address/price.
        keys=(canonical(item['url']), (fold(item['title']),fold(item['address']),item['price']))
        if any(k in seen for k in keys): continue
        seen.update(keys); result.append(item)
    return result
