import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from urllib.error import HTTPError
from crawler import eligible,extract,dedupe,parse_price,page_urls,robots_for
from server import merge

CARDS='''<ul><li><div class="img"><img data-src="https://cdn.example.com/a.jpg"></div>
<a href="/quan-2/cho-thue-can-ho-thao-dien-id101"><h2>Cho thuê căn hộ Thảo Điền 2PN</h2></a>
<div class="prop-addr">Quận 2 (TP. Thủ Đức), TPHCM</div><ul><li>65 m<sup>2</sup></li><li>2 PN</li></ul><div class="price">10,5 triệu</div></li>
<li><a href="/quan-2/cho-thue-can-ho-sala-id102"><h2>Căn hộ Sala giá 25 triệu</h2></a><div class="prop-addr">Quận 2</div><div class="price">25 triệu</div></li>
<li><a href="/quan-2/cho-thue-can-ho-ngay-id103"><h2>Căn hộ An Phú theo ngày</h2></a><div class="prop-addr">Quận 2</div><div class="price">9 triệu/ngày</div></li></ul>'''
MICRO='''<article itemscope itemtype="https://schema.org/RealEstateListing"><a itemprop="url" href="/can-ho-thao-dien-902.html"><h3 itemprop="name">Căn hộ 1PN Thảo Điền</h3></a>
<img itemprop="image" src="https://example.com/x.jpg"><span class="price" itemprop="offers" itemscope itemtype="https://schema.org/Offer">Giá: <span itemprop="price" content="9000000">9 triệu / tháng</span></span>
<p class="address">Đường Thảo Điền, Phường An Khánh</p><p class="old-address">Phường Thảo Điền, Quận 2 (cũ)</p></article>'''
CONFIG={'detail':r'-id\d+$','rent':True,'kind':'căn hộ'}

class CrawlerTests(unittest.TestCase):
    def item(self,price=10_000_000): return {'title':'Cho thuê căn hộ Thảo Điền','address':'Quận 2','price':price,'monthly':True,'url':'https://example.com/tin/1','kind':'Apartment'}
    def test_strict_boundaries(self):
        for p,want in [(8_000_000,False),(8_000_001,True),(11_999_999,True),(12_000_000,False)]: self.assertEqual(eligible(self.item(p)),want)
    def test_reject_wrong_district_and_period(self):
        i=self.item();i.update(title='Cho thuê căn hộ',address='Quận 12');self.assertFalse(eligible(i))
        i=self.item();i.update(title='Cho thuê căn hộ',address='An Phú Đông, Quận 12');self.assertFalse(eligible(i))
        i=self.item();i['monthly']=False;self.assertFalse(eligible(i))
        i=self.item();i.update(title='Nhà phố Quận 2',kind='House');self.assertFalse(eligible(i))
    def test_jsonld_currency_period_and_malformed(self):
        obj={'@type':'Apartment','name':'Cho thuê căn hộ Quận 2','address':'Thảo Điền','offers':{'price':10000000,'priceCurrency':'VND','priceSpecification':{'unitText':'tháng'}}}
        html='<script type="application/ld+json">'+json.dumps(obj)+'</script>'
        self.assertEqual(len(extract(html,'https://example.com/1','Test')),1)
        obj['offers']['priceCurrency']='USD'
        self.assertEqual(extract('<script type="application/ld+json">'+json.dumps(obj)+'</script>','https://example.com/1','Test'),[])
        self.assertEqual(extract('<script type="application/ld+json">oops</script>','https://example.com','Test'),[])
    def test_dedupe_tracking_urls(self):
        a=self.item();b={**a,'url':a['url']+'?utm_source=a'};self.assertEqual(len(dedupe([a,b])),1)
    def test_parse_price(self):
        for text,want in [('10,5 triệu',10_500_000),('12tr/tháng',12_000_000),('8.500.000 đ',8_500_000),('2,5 tỷ',2_500_000_000),('Thỏa thuận',None)]:
            self.assertEqual(parse_price(text),want)
    def test_listing_cards(self):
        items=extract(CARDS,'https://example.com/quan-2/thue-can-ho','Ví dụ',CONFIG)
        self.assertEqual([x['url'] for x in items],['https://example.com/quan-2/cho-thue-can-ho-thao-dien-id101'])
        x=items[0]
        self.assertEqual((x['price'],x['area'],x['bedrooms'],x['image']),(10_500_000,65,2,'https://cdn.example.com/a.jpg'))
        self.assertEqual(x['title'],'Cho thuê căn hộ Thảo Điền 2PN')
    def test_microdata_with_old_address(self):
        items=extract(MICRO,'https://example.com/cho-thue','Ví dụ',{'rent':True,'kind':'căn hộ'})
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['price'],9_000_000)
        self.assertIn('Quận 2',items[0]['address'])
    def test_page_urls(self):
        base={'origin':'https://x.vn','pages':3}
        self.assertEqual(page_urls({**base,'entry':'/a','page':'?cp={n}'})[1:],['https://x.vn/a?cp=2','https://x.vn/a?cp=3'])
        self.assertEqual(page_urls({**base,'entry':'/a/q2.html','page':'/trang--{n}'})[1],'https://x.vn/a/q2/trang--2.html')
        self.assertEqual(page_urls({**base,'entry':'/a/','page':'/p{n}'})[1],'https://x.vn/a/p2')
    def test_robots_status_rules(self):
        for code,allowed in [(404,True),(406,True),(403,False),(503,False)]:
            with mock.patch('crawler.fetch',side_effect=HTTPError('u',code,'x',{},None)):
                self.assertEqual(robots_for('https://x.vn').can_fetch('BibiHomeBot/1.0','https://x.vn/a'),allowed,code)
    def test_merge_keeps_first_seen_and_expires(self):
        now=datetime.now(timezone.utc)
        old={**self.item(),'id':'a','source':'S','seenAt':(now-timedelta(days=1)).isoformat(),'firstSeen':(now-timedelta(days=2)).isoformat()}
        gone={**self.item(),'id':'b','url':'https://example.com/tin/2','title':'Khác','source':'S','seenAt':(now-timedelta(days=5)).isoformat()}
        fresh={**old,'seenAt':now.isoformat()};fresh.pop('firstSeen')
        result=merge([old,gone],[fresh],now)
        self.assertEqual([x['id'] for x in result],['a'])
        self.assertEqual(result[0]['firstSeen'],old['firstSeen'])

if __name__=='__main__': unittest.main()
