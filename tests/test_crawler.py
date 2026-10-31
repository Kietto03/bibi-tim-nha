import json
import unittest
from crawler import eligible,extract,dedupe

class CrawlerTests(unittest.TestCase):
    def item(self,price=10_000_000): return {'title':'Cho thuê căn hộ Thảo Điền','address':'Quận 2','price':price,'monthly':True,'url':'https://example.com/tin/1','kind':'Apartment'}
    def test_strict_boundaries(self):
        for p,want in [(8_000_000,False),(8_000_001,True),(11_999_999,True),(12_000_000,False)]: self.assertEqual(eligible(self.item(p)),want)
    def test_reject_wrong_district_and_period(self):
        i=self.item();i.update(title='Cho thuê căn hộ',address='Quận 12');self.assertFalse(eligible(i))
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

if __name__=='__main__': unittest.main()
