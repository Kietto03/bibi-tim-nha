# Bibi tìm nhà ♡

Ứng dụng web tổng hợp căn hộ cho thuê tại **khu vực Quận 2 (cũ)**. Crawler lưu tin **5–25 triệu VND/tháng**; web mặc định lọc khoảng Bibi tìm là **lớn hơn 8 và nhỏ hơn 12 triệu**. Python 3.10+, không cần cài dependency; frontend HTML/CSS/JS.

## Chạy

```sh
python server.py
```

Mở http://localhost:8080. Windows có thể dùng `py server.py`. Đổi cổng bằng biến môi trường `PORT`. Chỉ bind loopback; đây chưa phải cấu hình public production.

Server tự crawl ngay khi khởi động rồi lặp lại mỗi 30 phút. Đổi chu kỳ bằng `CRAWL_EVERY_MINUTES` (đặt `0` để tắt, chỉ crawl khi bấm "Cập nhật tin").

Trên Windows, chạy `powershell -ExecutionPolicy Bypass -File .\start.ps1` để khởi động nền, ghi log vào `data/server.*.log`, kiểm tra API rồi mở trình duyệt. Script sử dụng server đang chạy nếu API phản hồi.

```sh
python -m unittest discover -s tests -v
```

## Có gì?

- Giao diện hoạt hình hồng kiểu sổ sticker, ảnh Bibi làm nhân vật chính. Mặc định giao diện sáng; nút mặt trời/mặt trăng chuyển sang tối và được nhớ trên trình duyệt.
- Tìm kiếm không dấu; lọc khu vực, phòng ngủ, khoảng giá (chip có đếm số căn, gồm 8–12 và 12–13 triệu), diện tích, nguồn tin, chỉ tin có ảnh, đăng trong 24 giờ / 7 / 30 / 90 ngày; sắp xếp mới đăng, giá, diện tích, giá/m².
- **Ngày đăng** đọc từ nguồn ("2 giờ trước", "Hôm qua", "17/9/2026", `datePosted`); nguồn chỉ ghi ngày thì lưu dạng ngày (`2026-10-31`) để không bịa giờ. Tin không rõ ngày ghi "Chưa rõ ngày đăng" và không được coi là mới. Nhiều nguồn còn giữ tin từ 2024–2025: lọc "Đăng trong" để bỏ tin cũ.
- **Dán tin Facebook / Zalo**: Facebook không cho bot đọc nhóm/trang (cần đăng nhập, cấm thu thập tự động) nên trang không crawl Facebook. Bibi dán nội dung bài + link; trang tự đọc giá ("11tr5", "8 triệu 500", "8.500.000đ"), diện tích, phòng ngủ, phường. Tin dán chỉ lưu trong trình duyệt đó. Bộ lọc và yêu thích lưu trên trình duyệt; tab "Đã thương" luôn hiện đủ căn đã lưu.
- Tự hiện **tin thật** khi đã có dữ liệu; chế độ **minh họa** chỉ dùng khi chưa có tin. Trang tự tải lại dữ liệu mỗi 5 phút.
- API `GET /api/listings`, `GET /api/sources`, `POST /api/crawl`; crawl nền, trạng thái từng nguồn, lưu JSON atomic.

## Thu thập dữ liệu

Nguồn cấu hình trong `sources.json` (17 nguồn): Mogi, Mua Bán, Rever, Nhà Đất 24h, Batdongsan.vn, Bds.com.vn, Batdongsanonline, Alo Mua Bán Nhà Đất, Phòng Trọ 123, i-Batdongsan, Homedy, Hoozing, Guland, 123nhadatviet, Alonhadat, Batdongsan.com.vn, Nhà Tốt. Mỗi nguồn khai báo trang danh sách (`entry`), mẫu phân trang (`page`, ví dụ `?cp={n}`, `/p{n}`, `/trang-{n}`), số trang (`pages`) và mẫu URL tin chi tiết (`detail`).

`crawler.py` đọc trang danh sách theo ba cách, không cần adapter riêng cho từng site:

1. **JSON-LD** schema.org (giá VND, kỳ thuê, địa chỉ).
2. **Microdata** `itemscope` RealEstateListing (ví dụ Alonhadat, có kèm địa chỉ cũ "(cũ)").
3. **Thẻ tin**: phần tử lớn nhất chỉ chứa đúng một link chi tiết; lấy tiêu đề, giá (`9,5 triệu`, `12tr/tháng`, `8.500.000 đ`), diện tích, phòng ngủ, địa chỉ, ảnh.

Chỉ nhận tin giá 5–25 triệu VND theo tháng (`MIN_PRICE`/`MAX_PRICE` trong `crawler.py`) (loại giá theo ngày, theo m², tỷ), loại căn hộ và khu vực Quận 2 cũ (gồm tên phường cũ/mới như Thảo Điền, An Phú, An Khánh, Bình Trưng, Cát Lái, Thủ Thiêm). Chống trùng theo URL chuẩn hoặc tiêu đề + địa chỉ + giá.

Quét **sâu** (tới 40 trang/nguồn, `pages` trong `sources.json`) mỗi 6 giờ và khi push; các lượt còn lại quét **nhanh** 5 trang đầu (`SHALLOW`), nơi tin mới xuất hiện. Biến môi trường `CRAWL_DEEP=0/1`; server local quét sâu ở lượt đầu và mỗi lượt thứ 6.

Tiêu đề nêu quận/dự án ngoài Quận 2 (Khang Điền, Safira, Jamila, Quận 9, Bình Thạnh…) mà không nhắc khu nào của Quận 2 thì bị loại, kể cả khi mô tả có câu "gần Quận 2".

Mỗi lượt crawl gộp với dữ liệu cũ: tin giữ `firstSeen` (lần đầu thấy) và `seenAt` (lần cuối thấy); tin không còn xuất hiện quá 3 ngày bị xóa. Tôn trọng robots.txt (RFC 9309: lỗi 4xx = không giới hạn, 401/403/5xx = không vào), `Crawl-delay` và tối thiểu 2 giây giữa các trang cùng nguồn; mỗi nguồn tối đa khoảng 150 giây; các nguồn chạy song song.

**Giới hạn**: Batdongsan.com.vn và Nhà Tốt trả 403 cho bot nên hiển thị trạng thái "Bị chặn"; Bibi không vượt chặn, không giả trình duyệt, không vượt CAPTCHA hay đăng nhập. Giá thuê căn hộ Quận 2 phần lớn trên 12 triệu; một lượt quét sâu được khoảng 1.850 tin 5–25 triệu, trong đó khoảng 280 tin 8–12 triệu và 180 tin 12–13 triệu. Một số nguồn (Alonhadat, i-Batdongsan, 123nhadatviet) đôi khi trả 429 với IP của GitHub Actions; lượt sau sẽ thử lại. Cấu trúc website có thể đổi; khi một nguồn chuyển sang "Chưa có tin phù hợp" lâu ngày, hãy kiểm tra lại `entry`/`page`/`detail`. Tin có thể đã cho thuê dù vẫn còn trên trang nguồn; luôn kiểm tra tin gốc.

## Bản đồ

Nút **Danh sách / Bản đồ** hiển thị các căn đang lọc trên bản đồ Leaflet (tải từ cdnjs khi mở bản đồ, tile © OpenStreetMap contributors). Pin là tem giá; nhiều căn gần nhau được gộp thành cụm.

Tin đăng hầu như không có tọa độ, nên vị trí là **gần đúng**: `crawler.locate()` khớp tiêu đề + địa chỉ với danh bạ `geo.json` (khoảng 85 dự án, đường, phường Quận 2), ưu tiên dự án → đường → phường. Pin viền nét đứt là vị trí theo đường/phường. Tin chỉ ghi "Quận 2" không được ghim (khoảng 14%).

`geo.json` được tạo một lần bằng `python geocode.py` từ OpenStreetMap Nominatim (User-Agent riêng, ≤ 1 request/giây, chỉ nhận kết quả trong khung Quận 2) rồi commit; crawl thường không gọi Nominatim. Các chỉnh tay sau khi rà kết quả nằm trong `DERIVED`/`NEAR` của `geocode.py`. Thêm dự án mới: thêm dòng vào `PLACES` rồi chạy lại script.

## GitHub Pages

Workflow `.github/workflows/pages.yml` crawl rồi deploy mỗi 30 phút, khi push vào main/master hoặc chạy thủ công. Trong Settings → Pages, chọn Source: GitHub Actions. GitHub Pages không chạy Python server: runner thu thập dữ liệu rồi đóng gói `listings.json` cùng giao diện; nút tải lại chỉ đọc dữ liệu đã xuất. Dữ liệu lượt trước được khôi phục từ cache Actions, hoặc từ `listings.json` đang public nếu cache bị xóa. Lịch Actions có thể trễ ở giờ cao điểm và bị GitHub tạm ngừng nếu repo không có hoạt động trong 60 ngày.

`python build_pages.py` tạo `dist/` không crawl, `python build_pages.py --crawl` thu thập trước khi tạo. Ảnh Bibi được đóng gói vào trang public theo yêu cầu công khai ứng dụng.

## Mở rộng

Thêm nguồn vào `sources.json` với origin tin cậy, `entry`, `page`, `pages`, `detail`, `"rent": true` và `"kind": "căn hộ"`; chạy `python -c "from crawler import crawl_source; import json; print(crawl_source(json.load(open('sources.json', encoding='utf-8'))[0])[1])"` để xem trạng thái. Trước triển khai internet cần xác thực endpoint crawl, giới hạn tần suất, HTTPS, giám sát và kho lưu trữ phù hợp. Không cho người dùng nhập URL tùy ý vào crawler.

## Thiết kế

Áp dụng skill [web-design-engineer](https://github.com/ConardLi/garden-skills/tree/main/skills/web-design-engineer) (nhánh Warm Humanist, phỏng theo recipe Mailchimp-Freddie): viền mực dày, bóng cứng lệch, nút viên thuốc, Baloo 2 + Nunito, hồng bubblegum + vàng bơ, ảnh thật của Bibi thay vì vẽ người bằng SVG, không dùng emoji làm icon.

Ảnh chân dung do người dùng cung cấp. Kiểm tra quyền sử dụng trước khi công khai repo.
