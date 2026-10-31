"""One-off: build geo.json (Quận 2 gazetteer) from OpenStreetMap Nominatim.

Run rarely (`python geocode.py`); results are committed so crawls never call Nominatim.
Follows the Nominatim usage policy: identifying User-Agent, <= 1 request/second, cached output.
"""
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
AGENT = 'BibiHomeBot/1.0 (+https://github.com/Kietto03/bibi-tim-nha)'
# Khung Quận 2 cũ; kết quả ngoài khung bị loại để tránh trùng tên ở quận khác.
BOX = (106.705, 10.745, 106.805, 10.825)  # west, south, east, north

# (tên hiển thị, loại, bí danh không dấu dùng để khớp tin, các truy vấn thử lần lượt)
PLACES = [
    ('Masteri Thảo Điền','project',['masteri thao dien'],['Masteri Thảo Điền','Masteri Thao Dien']),
    ('Masteri An Phú','project',['masteri an phu'],['Masteri An Phú','Masteri An Phu']),
    ('Lumière Riverside','project',['lumiere riverside','lumiere'],['Lumière Riverside','Masteri Lumière Riverside']),
    ('Lexington Residence','project',['lexington'],['Lexington Residence','Lexington']),
    ('The Sun Avenue','project',['sun avenue'],['The Sun Avenue']),
    ('The Estella','project',['estella'],['The Estella','Estella Heights']),
    ('Vista Verde','project',['vista verde'],['Vista Verde']),
    ('The Vista An Phú','project',['the vista an phu','vista an phu'],['The Vista An Phú','The Vista']),
    ('Feliz en Vista','project',['feliz en vista','feliz'],['Feliz en Vista']),
    ('Đảo Kim Cương','project',['dao kim cuong','diamond island'],['Diamond Island','Đảo Kim Cương']),
    ('Empire City','project',['empire city','emprirecity','empirecity','linden','tilia','narra'],['Empire City']),
    ('The Metropole Thủ Thiêm','project',['metropole'],['The Metropole Thủ Thiêm','The Metropole']),
    ('Khu đô thị Sala','project',['sala','sarimi','sadora','sarica'],['Sala','Sarimi','Sadora']),
    ('Palm Heights','project',['palm heights'],['Palm Heights']),
    ('Cantavil An Phú','project',['cantavil'],['Cantavil An Phú','Cantavil Premier','Cantavil']),
    ('Petroland','project',['petroland'],['Petroland']),
    ('Chung cư An Lộc','project',['an loc'],['Chung cư An Lộc']),
    ('The CBD Premium Home','project',['cbd premium','the cbd'],['The CBD Premium Home','CBD Premium Home']),
    ('Homyland','project',['homyland'],['Homyland Riverside','Homyland']),
    ('CitiHome','project',['citihome','citi home'],['CitiHome','Citi Home']),
    ('Citi Soho','project',['citi soho','citisoho'],['Citi Soho']),
    ('One Verandah','project',['one verandah'],['One Verandah']),
    ('Imperia An Phú','project',['imperia'],['Imperia An Phú','Imperia']),
    ('The Krista','project',['krista'],['The Krista']),
    ('Centana Thủ Thiêm','project',['centana'],['Centana Thủ Thiêm','Centana']),
    ('Victoria Village','project',['victoria village','vitoria village'],['Victoria Village']),
    ('Thảo Điền Pearl','project',['thao dien pearl'],['Thảo Điền Pearl']),
    ('Tropic Garden','project',['tropic garden'],['Tropic Garden']),
    ('Gateway Thảo Điền','project',['gateway thao dien','gateway'],['Gateway Thảo Điền']),
    ('The Nassim','project',['nassim'],['The Nassim','Nassim Thảo Điền']),
    ('Q2 Thảo Điền','project',['q2 thao dien'],['Q2 Thảo Điền']),
    ('The River Thủ Thiêm','project',['the river thu thiem'],['The River Thủ Thiêm']),
    ("D'Lusso",'project',['d lusso','dlusso',"d'lusso"],["D'Lusso",'DLusso']),
    ('Precia','project',['precia'],['Precia']),
    ('New City Thủ Thiêm','project',['new city'],['New City Thủ Thiêm','New City']),
    ('La Astoria','project',['la astoria'],['La Astoria']),
    ('Chung cư Bộ Công An','project',['bo cong an'],['Chung cư Bộ Công An']),
    ('Thủ Thiêm Dragon','project',['thu thiem dragon'],['Thủ Thiêm Dragon']),
    ('Thủ Thiêm Sky','project',['thu thiem sky'],['Thủ Thiêm Sky']),
    ('Fideco Riverview','project',['fideco'],['Fideco Riverview']),
    ('Xi Riverview Palace','project',['xi riverview'],['Xi Riverview Palace']),
    ('Waterina Suites','project',['waterina'],['Waterina Suites']),
    ('De Capella','project',['de capella'],['De Capella']),
    ('The Ascent','project',['the ascent'],['The Ascent Thảo Điền','The Ascent']),
    ('Hoàng Anh Riverview','project',['hoang anh riverview','hoang anh river view'],['Hoàng Anh Riverview']),
    ('Parcspring','project',['parcspring','parc spring'],['Parcspring']),
    ('Bình Minh','project',['chung cu binh minh'],['Chung cư Bình Minh']),
    ('Đường Xuân Thủy','street',['xuan thuy'],['Xuân Thủy, Thảo Điền']),
    ('Đường Quốc Hương','street',['quoc huong'],['Quốc Hương']),
    ('Đường Nguyễn Văn Hưởng','street',['nguyen van huong'],['Nguyễn Văn Hưởng']),
    ('Đường Trần Ngọc Diện','street',['tran ngoc dien'],['Trần Ngọc Diện']),
    ('Đường Nguyễn Cừ','street',['nguyen cu'],['Nguyễn Cừ']),
    ('Đường Tống Hữu Định','street',['tong huu dinh'],['Tống Hữu Định']),
    ('Đường Lê Văn Miến','street',['le van mien'],['Lê Văn Miến']),
    ('Đường Mai Chí Thọ','street',['mai chi tho'],['Mai Chí Thọ']),
    ('Đường Song Hành','street',['song hanh'],['Song Hành, An Phú']),
    ('Đường Lương Định Của','street',['luong dinh cua'],['Lương Định Của']),
    ('Đường Trần Não','street',['tran nao'],['Trần Não']),
    ('Đường Nguyễn Hoàng','street',['nguyen hoang'],['Nguyễn Hoàng, An Phú']),
    ('Đường Nguyễn Duy Trinh','street',['nguyen duy trinh'],['Nguyễn Duy Trinh']),
    ('Đường Đồng Văn Cống','street',['dong van cong'],['Đồng Văn Cống']),
    ('Đường Nguyễn Thị Định','street',['nguyen thi dinh'],['Nguyễn Thị Định']),
    ('Đường Nguyễn Quý Cảnh','street',['nguyen quy canh'],['Nguyễn Quý Cảnh']),
    ('Đường Võ Trường Toản','street',['vo truong toan'],['Võ Trường Toản']),
    ('Đường Lê Hữu Kiều','street',['le huu kieu'],['Lê Hữu Kiều']),
    ('Đường Trần Lựu','street',['tran luu'],['Trần Lựu']),
    ('Đường Nguyễn Văn Giáp','street',['nguyen van giap'],['Nguyễn Văn Giáp']),
    ('Đường Bát Nàn','street',['bat nan'],['Bát Nàn']),
    ('Đường Thân Văn Nhiếp','street',['than van nhiep'],['Thân Văn Nhiếp']),
    ('Đường Quách Giai','street',['quach giai'],['Quách Giai']),
    ('Đường Nguyễn Tư Nghiêm','street',['nguyen tu nghiem'],['Nguyễn Tư Nghiêm']),
    ('Đường Phan Văn Đáng','street',['phan van dang'],['Phan Văn Đáng']),
    ('Đường Vũ Tông Phan','street',['vu tong phan'],['Vũ Tông Phan']),
    ('Đường Nguyễn Thanh Sơn','street',['nguyen thanh son'],['Nguyễn Thanh Sơn']),
    ('Đường Nguyễn Văn Kỉnh','street',['nguyen van kinh'],['Nguyễn Văn Kỉnh']),
    ('Phường Thảo Điền','ward',['thao dien'],['Thảo Điền, Thủ Đức','Phường Thảo Điền']),
    ('Phường An Phú','ward',['an phu(?! dong)'],['An Phú, Thủ Đức','Phường An Phú']),
    ('Phường An Khánh','ward',['an khanh'],['An Khánh, Thủ Đức','Phường An Khánh']),
    ('Phường Bình An','ward',['binh an'],['Bình An, Thủ Đức','Phường Bình An']),
    ('Phường Bình Khánh','ward',['binh khanh'],['Bình Khánh, Thủ Đức','Phường Bình Khánh']),
    ('Phường Bình Trưng Đông','ward',['binh trung dong'],['Bình Trưng Đông']),
    ('Phường Bình Trưng Tây','ward',['binh trung tay'],['Bình Trưng Tây']),
    ('Phường Bình Trưng','ward',['binh trung'],['Bình Trưng, Thủ Đức','Bình Trưng Đông']),
    ('Phường Cát Lái','ward',['cat lai'],['Cát Lái, Thủ Đức','Phường Cát Lái']),
    ('Phường Thạnh Mỹ Lợi','ward',['thanh my loi'],['Thạnh Mỹ Lợi','Phường Thạnh Mỹ Lợi']),
    ('Phường Thủ Thiêm','ward',['thu thiem'],['Thủ Thiêm, Thủ Đức','Phường Thủ Thiêm']),
    ('Phường An Lợi Đông','ward',['an loi dong'],['An Lợi Đông']),
]

# Sửa sau khi rà kết quả OSM:
# - DERIVED: Nominatim trả POI sai cho phường -> lấy trung bình các dự án chắc chắn nằm trong phường.
# - NEAR: dự án chưa có trên OSM -> gắn theo con đường của dự án (độ chính xác cấp đường).
DERIVED = {'Phường Thủ Thiêm':['The River Thủ Thiêm','The Metropole Thủ Thiêm','Empire City']}
NEAR = {'Victoria Village':(['victoria village','vitoria village'],'Đường Đồng Văn Cống'),
        'The CBD Premium Home':(['cbd premium','the cbd'],'Đường Đồng Văn Cống'),
        'Hoàng Anh Riverview':(['hoang anh riverview','hoang anh river view'],'Đường Nguyễn Văn Hưởng')}

def finalize(places):
    by={p['name']:p for p in places}
    for name,sources in DERIVED.items():
        pts=[by[n] for n in sources if n in by]
        if name in by and pts:
            by[name].update(lat=round(sum(p['lat'] for p in pts)/len(pts),6),lon=round(sum(p['lon'] for p in pts)/len(pts),6),osm='Trung bình: '+', '.join(p['name'] for p in pts))
    for name,(aliases,street) in NEAR.items():
        if name not in by and street in by:
            places.append({'name':name,'kind':'near','aliases':aliases,'lat':by[street]['lat'],'lon':by[street]['lon'],'osm':'Theo '+street})
    return places

def search(query):
    west,south,east,north = BOX
    params = urlencode({'q':query+', Thành phố Hồ Chí Minh','format':'jsonv2','limit':1,'countrycodes':'vn','viewbox':f'{west},{north},{east},{south}','bounded':1})
    with urlopen(Request('https://nominatim.openstreetmap.org/search?'+params,headers={'User-Agent':AGENT,'Accept-Language':'vi'}),timeout=30) as r:
        found = json.load(r)
    time.sleep(1.1)
    return found[0] if found else None

def main():
    out=[]; missing=[]
    for name,kind,aliases,queries in PLACES:
        hit=None
        for q in queries:
            hit=search(q)
            if hit: break
        if not hit: missing.append(name); continue
        lat,lon=float(hit['lat']),float(hit['lon'])
        out.append({'name':name,'kind':kind,'aliases':aliases,'lat':round(lat,6),'lon':round(lon,6),'osm':hit.get('display_name','')[:140]})
        print(f'{kind:7} {name:28} {lat:.5f},{lon:.5f}  {hit.get("display_name","")[:70]}')
    out=finalize(out)
    (ROOT/'geo.json').write_text(json.dumps({'source':'© OpenStreetMap contributors (Nominatim)','places':out},ensure_ascii=False,indent=1),'utf-8')
    print('\nKhông tìm thấy:',', '.join(missing))

if __name__=='__main__': main()
