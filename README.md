# Bibi tìm nhà ♡

Ứng dụng web local tổng hợp căn hộ cho thuê tại **khu vực Quận 2 (cũ)**, giá thuê **lớn hơn 8.000.000 và nhỏ hơn 12.000.000 VND/tháng**. Python 3.10+, không cần cài dependency; frontend HTML/CSS/JS.

## Chạy

```sh
python server.py
```

Mở http://localhost:8080. Windows có thể dùng `py server.py`. Đổi cổng bằng biến môi trường `PORT`. Chỉ bind loopback; đây chưa phải cấu hình public production.

Trên Windows, chạy `powershell -ExecutionPolicy Bypass -File .\start.ps1` để khởi động nền, ghi log vào `data/server.*.log`, kiểm tra API rồi mở trình duyệt. Script sử dụng server đang chạy nếu API phản hồi.

```sh
python -m unittest discover -s tests -v
```

## Có gì?

- Giao diện responsive hồng pastel, ảnh Bibi, chế độ sáng/tối theo hệ thống; thao tác bàn phím, focus rõ ràng, nút 44px và giảm chuyển động.
- Tìm kiếm không dấu, lọc khu vực/phòng ngủ, sắp xếp giá, lưu yêu thích trên trình duyệt.
- Hai chế độ **minh họa** và **tin thật** tách biệt. Tên dự án, giá và hình vẽ trong demo là giả lập, không phải thông tin chào thuê.
- API `GET /api/listings`, `GET /api/sources`, `POST /api/crawl`; crawl nền, trạng thái từng nguồn, lưu JSON atomic, giữ dữ liệu cũ nếu nguồn lỗi.
- Cấu hình bốn nguồn trong `sources.json`; mỗi nguồn tối đa 12 trang liên kết và ngân sách khoảng 90 giây cộng timeout request đang chạy. Tôn trọng robots.txt, tối thiểu 2 giây giữa trang trong cùng nguồn.

## Giới hạn thu thập cần biết

Không có crawler nào cam kết bao phủ tất cả website. Bản này là crawler tổng quát **JSON-LD** với cấu hình entry page cho Batdongsan, Nhà Tốt, Mogi và Alonhadat. Các URL cần được kiểm tra khi triển khai; cấu trúc website có thể thay đổi. Chưa có adapter DOM/API riêng cho từng website. Trang render JavaScript, thiếu schema, chặn bot hoặc yêu cầu đăng nhập sẽ không cung cấp kết quả qua adapter hiện tại. Không vượt CAPTCHA hay đăng nhập. Trạng thái rỗng không có nghĩa là nguồn không có nhà.

Chỉ nhận tin có giá VND, bằng chứng kỳ thuê tháng, loại căn hộ và địa chỉ phù hợp. Những tin thiếu trường bị bỏ qua thay vì đoán. Giá phụ phí không được suy ra. Chống trùng bảo thủ theo URL chuẩn hoặc tiêu đề + địa chỉ + giá; chưa nhận diện cùng căn đăng lại với nội dung khác. Tin cũ giữ lại khi nguồn lỗi có thể hết hiệu lực; luôn xem thời điểm thu thập và kiểm tra tin gốc. Chưa có lịch chạy tự động; có thể gọi API bằng Task Scheduler/cron khi server đang chạy. Không có tài khoản, đồng bộ yêu thích hay thông báo ngoài app.

## Mở rộng

Thêm nguồn tin vào `sources.json` với origin tin cậy, entry và limit. Nếu nguồn không xuất JSON-LD, viết extractor riêng trong `crawler.py`, giữ hợp đồng trường của `extract`, gọi `eligible` trước khi lưu và thêm fixture kiểm thử. Trước triển khai internet cần xác thực endpoint crawl, giới hạn tần suất, HTTPS, giám sát và kho lưu trữ phù hợp. Không cho người dùng nhập URL tùy ý vào crawler.

## Thiết kế

Áp dụng [Apple Design Skill của dickwu](https://github.com/dickwu/apple-design-skill): tham khảo accessibility, layout, typography, color, designing-for-macos, cross-platform, buttons, searching, collections. Chuyển nguyên tắc sang web: CSS token, font hệ thống, lưới thích ứng, semantic HTML và native controls. Điểm nhận diện là ảnh Bibi kiểu polaroid trên nền hồng phấn; hình căn hộ demo là SVG nội bộ. Skill đã được đọc qua web; không cài global và không sao chép kho skill do môi trường shell không phân giải được github.com.

Ảnh chân dung do người dùng cung cấp, chỉ sao chép vào repo local theo yêu cầu. Kiểm tra quyền sử dụng trước khi công khai repo. Dữ liệu live chưa được xác thực end-to-end trong môi trường phát triển hạn chế mạng.
