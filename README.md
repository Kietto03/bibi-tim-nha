# Bibi tìm nhà ♡

Ứng dụng web tổng hợp căn hộ cho thuê tại **khu vực Quận 2 (cũ)**, giá thuê **lớn hơn 8.000.000 và nhỏ hơn 12.000.000 VND/tháng**. Python 3.10+, không cần cài dependency; frontend HTML/CSS/JS.

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
- Tìm kiếm không dấu, lọc khu vực/phòng ngủ, sắp xếp giá, lưu yêu thích trên trình duyệt.
- Tự hiện **tin thật** khi đã có dữ liệu; chế độ **minh họa** chỉ dùng khi chưa có tin. Trang tự tải lại dữ liệu mỗi 5 phút.
- API `GET /api/listings`, `GET /api/sources`, `POST /api/crawl`; crawl nền, trạng thái từng nguồn, lưu JSON atomic.

## Thu thập dữ liệu

Nguồn cấu hình trong `sources.json`: Mogi, Mua Bán, Rever, Nhà Đất 24h, Batdongsan.vn, 123nhadatviet, Alonhadat, Batdongsan.com.vn, Nhà Tốt. Mỗi nguồn khai báo trang danh sách (`entry`), mẫu phân trang (`page`, ví dụ `?cp={n}`, `/p{n}`, `/trang-{n}`), số trang (`pages`) và mẫu URL tin chi tiết (`detail`).

`crawler.py` đọc trang danh sách theo ba cách, không cần adapter riêng cho từng site:

1. **JSON-LD** schema.org (giá VND, kỳ thuê, địa chỉ).
2. **Microdata** `itemscope` RealEstateListing (ví dụ Alonhadat, có kèm địa chỉ cũ "(cũ)").
3. **Thẻ tin**: phần tử lớn nhất chỉ chứa đúng một link chi tiết; lấy tiêu đề, giá (`9,5 triệu`, `12tr/tháng`, `8.500.000 đ`), diện tích, phòng ngủ, địa chỉ, ảnh.

Chỉ nhận tin có giá VND theo tháng (loại giá theo ngày, theo m², tỷ), loại căn hộ và khu vực Quận 2 cũ (gồm tên phường cũ/mới như Thảo Điền, An Phú, An Khánh, Bình Trưng, Cát Lái, Thủ Thiêm). Chống trùng theo URL chuẩn hoặc tiêu đề + địa chỉ + giá.

Mỗi lượt crawl gộp với dữ liệu cũ: tin giữ `firstSeen` (lần đầu thấy) và `seenAt` (lần cuối thấy); tin không còn xuất hiện quá 3 ngày bị xóa. Tôn trọng robots.txt (RFC 9309: lỗi 4xx = không giới hạn, 401/403/5xx = không vào), `Crawl-delay` và tối thiểu 2 giây giữa các trang cùng nguồn; mỗi nguồn tối đa khoảng 150 giây; các nguồn chạy song song.

**Giới hạn**: Batdongsan.com.vn và Nhà Tốt trả 403 cho bot nên hiển thị trạng thái "Bị chặn"; Bibi không vượt chặn, không giả trình duyệt, không vượt CAPTCHA hay đăng nhập. Giá thuê căn hộ Quận 2 phần lớn trên 12 triệu, nên mỗi lượt thường chỉ vài chục tin lọt bộ lọc. Cấu trúc website có thể đổi; khi một nguồn chuyển sang "Chưa có tin phù hợp" lâu ngày, hãy kiểm tra lại `entry`/`page`/`detail`. Tin có thể đã cho thuê dù vẫn còn trên trang nguồn; luôn kiểm tra tin gốc.

## GitHub Pages

Workflow `.github/workflows/pages.yml` crawl rồi deploy mỗi 30 phút, khi push vào main/master hoặc chạy thủ công. Trong Settings → Pages, chọn Source: GitHub Actions. GitHub Pages không chạy Python server: runner thu thập dữ liệu rồi đóng gói `listings.json` cùng giao diện; nút tải lại chỉ đọc dữ liệu đã xuất. Dữ liệu lượt trước được khôi phục từ cache Actions, hoặc từ `listings.json` đang public nếu cache bị xóa. Lịch Actions có thể trễ ở giờ cao điểm và bị GitHub tạm ngừng nếu repo không có hoạt động trong 60 ngày.

`python build_pages.py` tạo `dist/` không crawl, `python build_pages.py --crawl` thu thập trước khi tạo. Ảnh Bibi được đóng gói vào trang public theo yêu cầu công khai ứng dụng.

## Mở rộng

Thêm nguồn vào `sources.json` với origin tin cậy, `entry`, `page`, `pages`, `detail`, `"rent": true` và `"kind": "căn hộ"`; chạy `python -c "from crawler import crawl_source; import json; print(crawl_source(json.load(open('sources.json', encoding='utf-8'))[0])[1])"` để xem trạng thái. Trước triển khai internet cần xác thực endpoint crawl, giới hạn tần suất, HTTPS, giám sát và kho lưu trữ phù hợp. Không cho người dùng nhập URL tùy ý vào crawler.

## Thiết kế

Áp dụng skill [web-design-engineer](https://github.com/ConardLi/garden-skills/tree/main/skills/web-design-engineer) (nhánh Warm Humanist, phỏng theo recipe Mailchimp-Freddie): viền mực dày, bóng cứng lệch, nút viên thuốc, Baloo 2 + Nunito, hồng bubblegum + vàng bơ, ảnh thật của Bibi thay vì vẽ người bằng SVG, không dùng emoji làm icon.

Ảnh chân dung do người dùng cung cấp. Kiểm tra quyền sử dụng trước khi công khai repo.
