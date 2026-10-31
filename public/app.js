const $=s=>document.querySelector(s);
const demos=[['Masteri Thảo Điền','Thảo Điền',10.5,2,65],['The Sun Avenue','An Phú',11,2,72],['Căn hộ An Phú xanh mát','An Phú',9.5,1,52],['Căn hộ 1PN Bình Trưng','Bình Trưng',8.5,1,48],['Căn hộ sáng thoáng Thủ Thiêm','Thủ Thiêm',11.5,2,68],['Căn hộ 2PN Thạnh Mỹ Lợi','Thạnh Mỹ Lợi',10,2,60]].map((x,i)=>({id:'demo-'+i,title:x[0],address:x[1]+', Quận 2',price:x[2]*1e6,bedrooms:x[3],area:x[4],source:'Dữ liệu minh họa',image:'/assets/room-'+i%3+'.svg',demo:true}));
// Crawler lưu 5–25 triệu; Bibi tìm 8–12 triệu nên đó là chip mặc định (giữ đúng ">8 và <12").
const PRICES=[{id:'lt8',label:'Dưới 8 tr',test:p=>p<=8e6},{id:'8-12',label:'8 – 12 tr',test:p=>p>8e6&&p<12e6},{id:'12-13',label:'12 – 13 tr',test:p=>p>=12e6&&p<=13e6},{id:'12-15',label:'12 – 15 tr',test:p=>p>=12e6&&p<15e6},{id:'15-20',label:'15 – 20 tr',test:p=>p>=15e6&&p<20e6},{id:'gt20',label:'Trên 20 tr',test:p=>p>=20e6},{id:'all',label:'Tất cả',test:()=>true}];
const DEFAULTS={price:'8-12',area:'',source:'',hasImage:false,age:'',ward:'',beds:'',sort:'new',layout:'grid'};
let saved;try{saved=new Set(JSON.parse(localStorage.getItem('bibi-saved')||'[]'))}catch{saved=new Set()}
let manual;try{manual=JSON.parse(localStorage.getItem('bibi-manual')||'[]')}catch{manual=[]}
let filters;try{filters={...DEFAULTS,...JSON.parse(localStorage.getItem('bibi-filters')||'{}')}}catch{filters={...DEFAULTS}}
let view='all',demo=true,autoMode=true,popped=null,data={listings:[],sources:[]},configs=[],timer;
const STATES={ok:'Đã đọc',empty:'Chưa có tin phù hợp',blocked:'Bị chặn',error:'Chưa đọc được'};
const normalize=s=>String(s).normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/đ/g,'d').toLowerCase();
const price=x=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:1}).format(x/1e6)+' triệu';
const svg=(id,cls='icon')=>{const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('class',cls);const u=document.createElementNS('http://www.w3.org/2000/svg','use');u.setAttribute('href','#'+id);s.append(u);return s};
// Ngày đăng theo nguồn (postedAt). Tin không rõ ngày không được coi là mới: lúc Bibi thấy lần đầu không phải ngày đăng.
const age=x=>x.postedAt?(Date.now()-new Date(x.postedAt))/864e5:Infinity;
const fresh=x=>age(x)<1;
const byNewest=(a,b)=>(!!b.manual-!!a.manual)||(!!b.postedAt-!!a.postedAt)||String(b.postedAt||b.firstSeen||'').localeCompare(String(a.postedAt||a.firstSeen||''));
function ago(iso){
 if(iso.length===10){ // chỉ có ngày (nguồn ghi "Hôm nay", "3 ngày trước", "29/10/2026"): đếm theo lịch giờ Việt Nam
  const d=Math.round((Date.parse(new Date(Date.now()+7*36e5).toISOString().slice(0,10))-Date.parse(iso))/864e5);
  if(d<=0)return 'hôm nay';if(d===1)return 'hôm qua';if(d<30)return d+' ngày trước';if(d<365)return Math.round(d/30)+' tháng trước';return new Date(iso).toLocaleDateString('vi-VN');
 }
 const d=(Date.now()-new Date(iso))/864e5;
 if(d<1/24)return 'vừa xong';if(d<1)return Math.round(d*24)+' giờ trước';if(d<2)return 'hôm qua';
 if(d<30)return Math.round(d)+' ngày trước';if(d<365)return Math.round(d/30)+' tháng trước';return new Date(iso).toLocaleDateString('vi-VN');
}
const postedLabel=x=>x.manual?'Bibi dán '+ago(x.firstSeen):x.postedAt?'Đăng '+ago(x.postedAt):'Chưa rõ ngày đăng';
function syncControls(){$('#ward').value=filters.ward;$('#beds').value=filters.beds;$('#sort').value=filters.sort;$('#area').value=filters.area;$('#has-image').checked=filters.hasImage;$('#age').value=filters.age}
function store(){try{localStorage.setItem('bibi-filters',JSON.stringify(filters))}catch{}}
// Mọi bộ lọc trừ giá; giá tách riêng để đếm số căn trên từng chip.
function baseRows(){
 const q=normalize($('#query').value),[amin,amax]=(filters.area||'0-1e9').split('-').map(Number);
 return (demo?demos:[...manual,...data.listings]).filter(x=>view!=='saved'||saved.has(x.id)).filter(x=>normalize(x.title+' '+x.address).includes(q))
  .filter(x=>!filters.ward||normalize(x.title+' '+x.address).includes(normalize(filters.ward))).filter(x=>!filters.beds||Number(x.bedrooms)===Number(filters.beds))
  .filter(x=>view==='saved'||!filters.area||(x.area>=amin&&x.area<amax)).filter(x=>view==='saved'||!filters.source||x.source===filters.source)
  .filter(x=>view==='saved'||!filters.hasImage||(x.image&&!x.demo)).filter(x=>view==='saved'||!filters.age||x.manual||age(x)<=Number(filters.age));
}
function renderFilters(base){
 $('#price-chips').replaceChildren(...PRICES.map(r=>{const b=document.createElement('button');b.className='chip';b.setAttribute('aria-pressed',filters.price===r.id);const n=document.createElement('small');n.textContent=base.filter(x=>r.test(x.price)).length;b.append(r.label,n);b.onclick=()=>{filters.price=r.id;store();render()};return b}));
 const names=[...new Set([...manual,...data.listings].map(x=>x.source))].sort();
 if($('#source').options.length-1!==names.length){$('#source').replaceChildren(new Option('Tất cả nguồn',''),...names.map(n=>new Option(n,n)))}
 $('#source').value=names.includes(filters.source)?filters.source:'';$('#source').disabled=demo;
 $('#reset').hidden=JSON.stringify({...filters,sort:'new',layout:'grid'})===JSON.stringify(DEFAULTS)&&!$('#query').value;
}
// Bản đồ: Leaflet + MarkerCluster chỉ tải khi Bibi mở chế độ bản đồ. Vị trí lấy từ geo.json (OpenStreetMap), gần đúng theo dự án/đường/phường.
const LEAFLET='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/',CLUSTER='https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/';
let map,tiles,cluster,leaflet,lastKeys='';
const addCss=href=>{const l=document.createElement('link');l.rel='stylesheet';l.href=href;document.head.append(l)};
const addJs=src=>new Promise((ok,fail)=>{const s=document.createElement('script');s.src=src;s.onload=ok;s.onerror=fail;document.head.append(s)});
const loadLeaflet=()=>leaflet||=(addCss(LEAFLET+'leaflet.min.css'),addCss(CLUSTER+'MarkerCluster.min.css'),addJs(LEAFLET+'leaflet.min.js').then(()=>addJs(CLUSTER+'leaflet.markercluster.min.js')));
// Tile chuẩn OpenStreetMap (dùng nhẹ, có ghi nguồn); chế độ tối đảo màu bằng CSS trên .leaflet-tile-pane.
const TILES='https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const shortPrice=p=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:1}).format(p/1e6)+'tr';
const GEO_LABEL={project:'Theo dự án',near:'Gần đúng theo đường',street:'Gần đúng theo đường',ward:'Gần đúng theo phường'};
function popup(x){
 const box=document.createElement('div');box.className='map-pop';
 if(x.image){const img=document.createElement('img');img.src=x.image;img.alt='';img.loading='lazy';img.onerror=()=>img.remove();box.append(img)}
 const p=document.createElement('strong');p.textContent=price(x.price)+' /tháng';
 const h=document.createElement('h4');h.textContent=x.title;
 const where=document.createElement('small');where.textContent=`${x.geo.place} · ${GEO_LABEL[x.geo.level]||'Gần đúng'}`;
 const row=document.createElement('div');row.className='map-pop-row';
 const heart=document.createElement('button');heart.className='heart';heart.append(svg('i-heart',''));
 const sync=()=>{heart.setAttribute('aria-pressed',saved.has(x.id));heart.setAttribute('aria-label',(saved.has(x.id)?'Bỏ lưu ':'Lưu ')+x.title)};sync();
 heart.onclick=()=>{saved.has(x.id)?saved.delete(x.id):saved.add(x.id);try{localStorage.setItem('bibi-saved',JSON.stringify([...saved]))}catch{}sync();$('#saved-count').textContent=saved.size;$('#hero-saved').textContent=saved.size};
 row.append(heart);
 try{const u=new URL(x.url);if(!['https:','http:'].includes(u.protocol))throw Error();const a=document.createElement('a');a.className='view';a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.append('Xem tin ',svg('i-arrow'));row.append(a)}catch{}
 const src=document.createElement('small');src.textContent=x.source+' · '+postedLabel(x);
 box.append(p,h,where,src,row);return box;
}
async function renderMap(rows){
 const placed=rows.filter(x=>x.geo),missing=rows.length-placed.length;
 $('#map-note').textContent=demo?'Bản minh họa chưa có vị trí; xem tin thật để thấy bản đồ.':`${placed.length} căn trên bản đồ`+(missing?` · ${missing} căn chỉ ghi “Quận 2” nên chưa ghim`:'');
 try{await loadLeaflet()}catch{$('#map-note').textContent='Chưa tải được bản đồ, thử lại sau nha.';return}
 if(!map){
  map=L.map('map',{scrollWheelZoom:false,zoomControl:true}).setView([10.79,106.745],14);
  tiles=L.tileLayer(TILES,{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
  cluster=L.markerClusterGroup({showCoverageOnHover:false,maxClusterRadius:48,spiderfyDistanceMultiplier:1.6,iconCreateFunction:c=>L.divIcon({html:`<span>${c.getChildCount()}</span>`,className:'cluster',iconSize:[48,48]})});
  map.addLayer(cluster);map.on('click focus',()=>map.scrollWheelZoom.enable());
 }
 map.invalidateSize();cluster.clearLayers();
 cluster.addLayers(placed.map(x=>L.marker([x.geo.lat,x.geo.lon],{title:x.title,icon:L.divIcon({className:'pin-wrap',iconSize:[0,0],html:`<span class="pin${x.geo.level==='project'?'':' approx'}${saved.has(x.id)?' loved':''}">${shortPrice(x.price)}</span>`})}).bindPopup(()=>popup(x),{maxWidth:270,minWidth:220})));
 const keys=placed.map(x=>x.id).join();
 if(keys!==lastKeys&&placed.length){lastKeys=keys;map.fitBounds(L.latLngBounds(placed.map(x=>[x.geo.lat,x.geo.lon])).pad(.08),{maxZoom:16})}
}
function render(){
 $('#saved-count').textContent=saved.size;$('#hero-saved').textContent=saved.size;$('#results').hidden=view==='sources';$('#sources').hidden=view!=='sources';$('#notice').hidden=view==='sources';
 document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
 $('#heading').textContent=view==='saved'?'Những căn Bibi đã thương':view==='sources'?'Bibi tìm tin ở đâu?':'Nhà xinh cho Bibi';
 const range=PRICES.find(r=>r.id===filters.price)||PRICES[1];
 $('#mode').textContent=demo?'Xem tin thật':'Xem bản minh họa';
 $('#notice strong').textContent=demo?'Đây là nhà minh họa thôi nha!':'Tin thật, có nguồn để kiểm tra';
 $('#notice p').textContent=demo?'Dữ liệu và hình ảnh để xem thử giao diện, không phải tin cho thuê đã xác minh.':'Căn hộ Quận 2 cho thuê theo tháng, giá 5 – 25 triệu. Đổi khoảng giá ở bộ lọc phía trên; nhớ kiểm tra tình trạng trên tin gốc.';
 const base=baseRows();renderFilters(base);
 let rows=view==='saved'?base:base.filter(x=>range.test(x.price));
 const key={low:(a,b)=>a.price-b.price,high:(a,b)=>b.price-a.price,big:(a,b)=>(b.area||0)-(a.area||0),ppm:(a,b)=>(a.area?a.price/a.area:1e12)-(b.area?b.price/b.area:1e12)}[filters.sort];
 rows.sort(key||byNewest);
 $('#summary').textContent=view==='sources'?`${configs.length} nguồn được cấu hình · Thu thập từ trang công khai`:`${rows.length} căn hộ ${demo?'minh họa':'phù hợp'} · Quận 2${view==='saved'?'':' · '+(range.id==='all'?'5 – 25 triệu':range.label.replace('tr','triệu'))+'/tháng'}`;
 $('#results').replaceChildren();
 for(const x of rows){const card=$('#card').content.cloneNode(true);const el=s=>card.querySelector(s);el('h3').textContent=x.title;el('.location span').textContent=x.address;el('.beds span').textContent=x.bedrooms?x.bedrooms+' phòng ngủ':'Chưa rõ';el('.area span').textContent=x.area?x.area+' m²':'Chưa rõ';el('.price strong').textContent=price(x.price);el('.badge').textContent=x.demo?'Minh họa':x.manual?'Tự thêm':fresh(x)?'Mới nè!':'Tin thật';el('img').src=x.image||'/assets/room-0.svg';el('img').alt=x.demo?'Phối cảnh căn hộ minh họa':x.title;el('img').onerror=e=>{e.target.onerror=null;e.target.src='/assets/room-0.svg';e.target.alt='Hình thay thế minh họa';};el('.source-line').textContent=x.source+(x.demo?' · Không phải tin thật':' · '+postedLabel(x));if(x.postedAt)el('.source-line').title='Ngày đăng theo nguồn: '+(x.postedAt.length===10?new Date(x.postedAt).toLocaleDateString('vi-VN'):new Date(x.postedAt).toLocaleString('vi-VN'));const link=el('.view');if(x.demo){link.querySelector('span').textContent='Minh họa';link.removeAttribute('target')}else{try{const u=new URL(x.url);if(!['https:','http:'].includes(u.protocol))throw Error();link.href=u.href}catch{link.remove()}}const heart=el('.heart');heart.setAttribute('aria-pressed',saved.has(x.id));if(popped===x.id)heart.classList.add('pop');heart.setAttribute('aria-label',(saved.has(x.id)?'Bỏ lưu ':'Lưu ')+x.title);heart.onclick=()=>{saved.has(x.id)?saved.delete(x.id):saved.add(x.id);popped=saved.has(x.id)?x.id:null;try{localStorage.setItem('bibi-saved',JSON.stringify([...saved]))}catch{}render()};$('#results').append(card)}
 const showMap=filters.layout==='map'&&view!=='sources';
 document.querySelectorAll('[data-layout]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.layout===filters.layout));
 $('#map-wrap').hidden=!showMap;if(showMap){$('#results').hidden=true;renderMap(rows)}
 popped=null;if(!rows.length){const empty=document.createElement('div');empty.className='empty';empty.textContent=view==='saved'?'Chưa thương căn nào hết. Bấm trái tim trên căn Bibi thích để lưu lại nha!':demo?'Hông thấy căn nào hợp. Thử đổi khu vực hoặc từ khóa nha.':data.listings.length?'Hông có căn nào khớp bộ lọc. Thử nới khoảng giá hoặc bấm “Xóa lọc” nha.':'Chưa có tin thật phù hợp. Bấm “Cập nhật tin thật” rồi xem trạng thái nguồn.';$('#results').append(empty)}
 $('#sources').replaceChildren();for(const c of configs){const s=data.sources.find(x=>x.id===c.id);const box=document.createElement('article');box.className='source-card';const a=document.createElement('a');a.href=c.origin+c.entry;a.target='_blank';a.rel='noopener noreferrer';a.append(c.name,svg('i-arrow'));const p=document.createElement('p');const dot=document.createElement('span');dot.className='dot '+(s?s.state==='ok'||s.state==='empty'?s.state:'error':'');const text=document.createElement('span');text.textContent=s?`${STATES[s.state]||STATES.error} · ${s.count} tin · ${s.message}`+(s.checkedAt?` · ${new Date(s.checkedAt).toLocaleString('vi-VN')}`:''):'Chưa chạy thu thập. Bấm cập nhật để kiểm tra nguồn.';p.append(dot,text);box.append(a,p);$('#sources').append(box)}
}
async function load(){try{const res=await fetch('/api/listings',{cache:'no-store'});if(!res.ok)throw Error();data=await res.json();if(autoMode)demo=!data.listings.length;$('#status').textContent=data.running?'Bibi chờ xíu, đang ghé các nguồn tin… Vẫn lọc và lưu căn hộ được nha.':data.updatedAt?'Lần thu thập gần nhất: '+new Date(data.updatedAt).toLocaleString('vi-VN')+' · Thời điểm thu thập không phải ngày đăng tin.':'';$('#refresh').disabled=data.running;$('#refresh-label').textContent=data.running?'Đang tìm tin…':'Cập nhật tin';render();clearTimeout(timer);if(data.running)timer=setTimeout(load,2500)}catch{$('#status').textContent='Chưa kết nối được máy chủ. Kiểm tra python server.py rồi tải lại trang.';$('#refresh').disabled=false}}
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>{view=b.dataset.view;render()});
$('#query').addEventListener('input',render);
[['ward','ward'],['beds','beds'],['sort','sort'],['area','area'],['source','source'],['age','age']].forEach(([id,k])=>$('#'+id).addEventListener('change',e=>{filters[k]=e.target.value;store();render()}));
[['has-image','hasImage']].forEach(([id,k])=>$('#'+id).addEventListener('change',e=>{filters[k]=e.target.checked;store();render()}));
document.querySelectorAll('[data-layout]').forEach(b=>b.onclick=()=>{filters.layout=b.dataset.layout;store();render()});
$('#reset').onclick=()=>{filters={...DEFAULTS,layout:filters.layout};$('#query').value='';store();syncControls();render()};
$('#search-button').onclick=()=>{view='all';render();$('.content').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})};$('#query').addEventListener('keydown',e=>{if(e.key==='Enter')$('#search-button').click()});$('#mode').onclick=()=>{autoMode=false;demo=!demo;render()};$('#refresh').onclick=async()=>{autoMode=false;demo=false;$('#refresh').disabled=true;try{const res=await fetch('/api/crawl',{method:'POST'});if(!res.ok)throw Error();await load()}catch{$('#status').textContent='Không bắt đầu được thu thập. Thử lại sau nhé.';$('#refresh').disabled=false}};
function applyTheme(){const t=document.documentElement.dataset.theme==='dark'?'dark':'light';document.documentElement.dataset.effective=t;$('#theme').setAttribute('aria-label',t==='dark'?'Chuyển sang giao diện sáng':'Chuyển sang giao diện tối');document.querySelector('meta[name=theme-color]').content=t==='dark'?'#1f1119':'#fff1f6'}
$('#theme').onclick=()=>{const t=document.documentElement.dataset.effective==='dark'?'light':'dark';document.documentElement.dataset.theme=t;try{localStorage.setItem('bibi-theme',t)}catch{}applyTheme()};applyTheme();
// Dán tin Facebook/Zalo: Facebook không cho bot đọc nhóm/trang, nên Bibi dán tay; tin chỉ lưu trên trình duyệt này.
const WARDS=['Thảo Điền','An Phú','An Khánh','Bình An','Bình Khánh','Bình Trưng Đông','Bình Trưng Tây','Bình Trưng','Thạnh Mỹ Lợi','Cát Lái','Thủ Thiêm','An Lợi Đông'];
function parsePrice(t){
 let m=t.match(/(\d{1,3}(?:[.,]\d{3}){2,})\s*(?:d|vnd|dong)\b/);if(m)return Number(m[1].replace(/[.,]/g,''));
 m=t.match(/(\d+(?:[.,]\d+)?)\s*(?:trieu|tr|cu)(?:\s*(\d{1,3})(?!\s*(?:m|pn|phong|wc)))?/);if(!m)return null;
 return (parseFloat(m[1].replace(',','.'))+(m[2]?Number(m[2])/10**m[2].length:0))*1e6; // 11tr5 -> 11,5 triệu; 8 triệu 500 -> 8,5
}
function parsePost(text,url){
 const t=normalize(text),num=re=>{const m=t.match(re);return m?parseFloat(m[1].replace(',','.')):null};
 const ward=WARDS.find(w=>t.includes(normalize(w))),host=(()=>{try{return new URL(url).hostname}catch{return ''}})();
 return {id:'manual-'+Date.now(),manual:true,title:text.trim().split('\n')[0].slice(0,110),address:(ward?ward+', ':'')+'Quận 2',price:parsePrice(t),area:num(/(\d+(?:[.,]\d+)?)\s*m\s?(?:2|²)/),bedrooms:num(/(\d)\s*(?:pn|phong ngu|br\b|bedroom)/),
  source:/facebook|fb\.com/.test(host)?'Facebook':/zalo/.test(host)?'Zalo':'Tự thêm',url:/^https?:$/.test((()=>{try{return new URL(url).protocol}catch{return ''}})())?url:'',image:'',postedAt:null,firstSeen:new Date().toISOString(),seenAt:new Date().toISOString()};
}
function saveManual(){try{localStorage.setItem('bibi-manual',JSON.stringify(manual))}catch{}renderManual();render()}
function renderManual(){
 $('#manual-count').textContent=manual.length?`· ${manual.length} tin đã dán`:'';
 $('#manual-list').replaceChildren(...manual.map(x=>{const li=document.createElement('li');const s=document.createElement('span');s.textContent=`${price(x.price)} · ${x.title}`;const b=document.createElement('button');b.className='reset';b.textContent='Xóa';b.setAttribute('aria-label','Xóa tin '+x.title);b.onclick=()=>{manual=manual.filter(y=>y.id!==x.id);saveManual()};li.append(s,b);return li}));
}
$('#paste-add').onclick=()=>{
 const text=$('#paste-text').value.trim();if(!text){$('#paste-msg').textContent='Bibi dán nội dung bài đăng vào ô trên nha.';return}
 const item=parsePost(text,$('#paste-url').value.trim());
 if(!item.price){$('#paste-msg').textContent='Chưa thấy giá thuê; thêm chữ kiểu “11tr5” hoặc “11,5 triệu” nha.';return}
 manual.unshift(item);$('#paste-text').value='';$('#paste-url').value='';
 $('#paste-msg').textContent=`Đã thêm: ${price(item.price)}${item.area?' · '+item.area+' m²':''}${item.bedrooms?' · '+item.bedrooms+' PN':''} · ${item.address}`;
 autoMode=false;demo=false;filters.price='all';store();saveManual();
};
renderManual();
// Dữ liệu được crawl định kỳ; trang tự tải lại tin mới mà không cần F5.
syncControls();render();fetch('/api/sources').then(r=>r.json()).then(x=>{configs=x;render()}).catch(()=>{});load();setInterval(()=>{if(!document.hidden)load()},5*60*1000);
