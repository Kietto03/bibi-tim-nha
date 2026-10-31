"""Bounded public-page crawler. No bypasses, credentials or private endpoints."""
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

AGENT = 'BibiHomeBot/1.0'
BUDGET = 150
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','source','track','wbr'}
LISTING_TYPES = ('realestatelisting','apartment','residence','accommodation','product','offer','house','singlefamilyresidence')

def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value).lower().replace('đ','d')) if unicodedata.category(c) != 'Mn')

def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', ''))

AREA = re.compile(r'\b(quan\s*2|q\.?\s*2|thao dien|an phu(?! dong)|binh trung|thanh my loi|cat lai|thu thiem|an khanh|binh an|binh khanh)\b')

def eligible(item):
    area = AREA.search(fold(str(item.get('address','')) + ' ' + item.get('title','')))
    apartment = any(x in fold(item.get('title','') + ' ' + item.get('kind','')) for x in ['can ho','chung cu','apartment','condominium'])
    return bool(area and apartment and 8_000_000 < item.get('price',0) < 12_000_000 and item.get('monthly',False))

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

def make_item(url, source, title, address, kind, price, monthly, image, area, bedrooms):
    return {'id':hashlib.sha256(canonical(url).encode()).hexdigest()[:16],'title':re.sub(r'\s+',' ',str(title)).strip(),'address':re.sub(r'\s+',' ',str(address)).strip(),'kind':str(kind),
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
            results.append(make_item(target,source,title,address,obj.get('@type',''),price,monthly,image if isinstance(image,str) and image.startswith('https://') else '',area,obj.get('numberOfBedrooms')))
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
        results.append(make_item(target,source,title,address,config.get('kind',''),price or 0,bool(monthly),image_of(node,url),
                                 parse_number(r'(\d+(?:[.,]\d+)?)\s*m\s?(?:2|²)',text),parse_number(r'(\d+)\s*(?:pn|phong ngu)\b',text)))
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
                                 parse_number(r'(\d+(?:[.,]\d+)?)\s*m\s?(?:2|²)',text),parse_number(r'(\d+)\s*(?:pn|phong ngu|phong)\b',text)))
    return results

def extract(html, url, source, config=None):
    config=config or {}
    page=Page(html)
    found=from_jsonld(page,url,source)+from_microdata(page,url,source,config)
    if config.get('detail'): found+=from_cards(page,url,source,config)
    return [x for x in dedupe(found) if eligible(x)]

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

def page_urls(config):
    entry=urljoin(config['origin'],config['entry'])
    pattern=config.get('page')
    urls=[entry]
    for n in range(2,config.get('pages',1)+1):
        if not pattern: break
        if pattern.startswith('?'): urls.append(entry+pattern.format(n=n))
        elif entry.endswith('.html'): urls.append(entry[:-5]+pattern.format(n=n)+'.html')
        else: urls.append(entry.rstrip('/')+pattern.format(n=n))
    return urls

def crawl_source(config):
    origin=config['origin']; started=time.monotonic()
    urls=page_urls(config)
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
        status.update(state='ok' if items else 'empty',message=f"Đã đọc {status['pages']} trang danh sách" if items else f"Đã đọc {status['pages']} trang nhưng chưa có tin 8–12 triệu phù hợp.")
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
