"""Bounded public-page crawler. No bypasses, credentials or private endpoints."""
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

AGENT = 'BibiHomeBot/1.0'
def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value).lower().replace('đ','d')) if unicodedata.category(c) != 'Mn')

def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', ''))

def eligible(item):
    text = fold(str(item.get('address','')) + ' ' + item.get('title',''))
    area = re.search(r'\b(quan\s*2|q\.?\s*2|thao dien|an phu|binh trung|thanh my loi|cat lai|thu thiem|an khanh|binh an|binh khanh)\b', text)
    apartment = any(x in fold(item.get('title','') + ' ' + item.get('kind','')) for x in ['can ho','chung cu','apartment','condominium'])
    return bool(area and apartment and 8_000_000 < item.get('price',0) < 12_000_000 and item.get('monthly',False))

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.links=[]; self.blocks=[]; self.capture=False; self.buf=''; self.feed(text)
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='a' and a.get('href'): self.links.append(a['href'])
        if tag=='script' and a.get('type','').lower()=='application/ld+json': self.capture=True; self.buf=''
    def handle_data(self, data):
        if self.capture: self.buf+=data
    def handle_endtag(self, tag):
        if tag=='script' and self.capture:
            try: self.blocks.append(json.loads(self.buf))
            except ValueError: pass
            self.capture=False

def walk(value):
    if isinstance(value,dict):
        yield value
        for child in value.values(): yield from walk(child)
    elif isinstance(value,list):
        for child in value: yield from walk(child)

def extract(html, url, source):
    results=[]
    for block in Page(html).blocks:
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
            item={'id':hashlib.sha256(canonical(target).encode()).hexdigest()[:16], 'title':str(title),'address':str(address),'kind':str(obj.get('@type','')), 'price':price,'monthly':monthly,'image':image if isinstance(image,str) and image.startswith('https://') else '', 'url':target,'source':source,'area':obj.get('floorSize',{}).get('value') if isinstance(obj.get('floorSize'),dict) else None,'bedrooms':obj.get('numberOfBedrooms'), 'seenAt':datetime.now(timezone.utc).isoformat()}
            if eligible(item): results.append(item)
    return results

def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':AGENT,'Accept':'text/html'}),timeout=15) as response:
        if urlsplit(response.url).netloc != urlsplit(url).netloc: raise ValueError('Nguồn chuyển sang tên miền khác')
        return response.read(2_000_000).decode('utf-8',errors='replace')

def crawl_source(config):
    origin=config['origin']; entry=urljoin(origin,config['entry']); started=time.monotonic()
    status={'id':config['id'],'name':config['name'],'url':entry,'count':0,'state':'error','message':''}
    items=[]
    try:
        robot=RobotFileParser(); robot.parse(fetch(urljoin(origin,'/robots.txt')).splitlines())
        if not robot.can_fetch(AGENT,entry): raise ValueError('robots.txt không cho phép thu thập trang này')
        delay=max(2,float(robot.crawl_delay(AGENT) or 0))
        html=fetch(entry); items.extend(extract(html,entry,config['name']))
        links=list(dict.fromkeys(canonical(urljoin(entry,l)) for l in Page(html).links))
        for link in [l for l in links if urlsplit(l).netloc==urlsplit(origin).netloc and re.search(r'cho-thue|thue-can-ho|can-ho-chung-cu',l) and l!=canonical(entry)][:config.get('limit',12)]:
            if time.monotonic()-started>90: break
            if robot.can_fetch(AGENT,link):
                time.sleep(delay)
                try: items.extend(extract(fetch(link),link,config['name']))
                except Exception: continue
        status.update(state='ok' if items else 'empty',message='Đã đọc dữ liệu công khai' if items else 'Không tìm được tin JSON-LD đủ giá, kỳ thuê và địa chỉ; có thể cần adapter riêng.')
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
