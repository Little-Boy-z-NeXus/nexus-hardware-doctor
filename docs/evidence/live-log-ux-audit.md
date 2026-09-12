# Audit UX — ESP32 Live Log

## Audit scope

Khu vực `ESP32 Live Log` trên trang `/hardware`, dựa trên ảnh vấn đề người dùng cung cấp tại `C:\Users\lenovo\AppData\Local\Temp\codex-clipboard-8adc025a-010e-4ef5-9f39-c19d5ee160a1.png` và trạng thái COM8 realtime trong Codex in-app Browser.

## User goal

Người dùng cần nhìn thấy bản ghi mới nhất ngay khi mở trang, nhận biết mình đang xem dữ liệu live hay log cũ, đọc nhanh các số đo quan trọng, và chỉ mở JSON thô khi thực sự cần debug.

## Strengths

- Log đã lấy trực tiếp từ backend và tiếp tục cập nhật realtime.
- Có sẵn bộ lọc mức, tìm kiếm, tạm dừng, ẩn log cũ và tải log.
- Màu nền terminal tạo ranh giới rõ với khu vực chẩn đoán.

## Notable risks

- P1: bộ đệm giữ cố định 160 bản ghi nên số lượng phần tử không đổi; cơ chế tự cuộn cũ chỉ phụ thuộc số lượng, vì vậy log mới có thể đến nhưng màn hình không đi theo bản ghi mới nhất.
- P1: toàn bộ telemetry được in thành một dòng JSON dài, khiến điện áp, dòng, công suất và trạng thái motor khó quét bằng mắt.
- P2: trạng thái “đang bám live” và “đang xem log cũ” chưa được phân biệt; người dùng không biết dữ liệu trên màn hình còn mới hay không.
- P2: ở vùng nội dung hẹp, các trường dài tạo cuộn ngang và làm mất nhịp đọc.
- P2: dữ liệu kỹ thuật quan trọng và JSON gốc cùng có độ ưu tiên thị giác như nhau.

## Opportunity areas

- Dùng ID bản ghi mới nhất làm tín hiệu cuộn thay vì chỉ dùng độ dài danh sách.
- Tách mỗi log thành thời gian, mức, tiêu đề, số đo chính và phần dữ liệu gốc có thể mở.
- Chỉ dừng bám live sau hành động cuộn thật của người dùng, không dừng do reflow hoặc cập nhật DOM.
- Cung cấp nút nổi “Về log mới nhất” khi người dùng đang xem lịch sử.

## Recommendations implemented

1. Mặc định `followLatest=true`; cuộn lại theo `latestVisibleLog.id` để hoạt động cả khi bộ đệm luôn có 160 bản ghi.
2. Telemetry được tóm tắt thành bốn ô: điện áp, dòng, công suất và motor.
3. Hardware profile và signal monitor được đổi thành câu tiếng Việt dễ hiểu.
4. JSON/raw log được giữ nguyên trong phần `Xem dữ liệu gốc` và trong file tải xuống.
5. Thêm trạng thái rõ ràng `Đang theo dõi log mới nhất`, `Bạn đang xem log cũ`, `Đã tạm dừng`.
6. Bổ sung điều khiển bàn phím, focus ring, bố cục hai cột ở vùng hẹp và loại bỏ cuộn ngang.

## Acceptance evidence

- Mở lại trang: hiển thị `Đang theo dõi log mới nhất` và bản ghi có thời gian trùng với nhãn `Mới nhất lúc`.
- Nhấn `Home` trong vùng log: hiển thị `Bạn đang xem log cũ` và nút `Về log mới nhất`.
- Bấm `Về log mới nhất`: vùng log trở lại cuối danh sách và tiếp tục nhận bản ghi mới.
- Viewport kiểm tra: 818 × 698 CSS px; document overflow ngang 0 px; terminal overflow ngang 0 px.
- Console: không có warning hoặc error.
- Frontend gate: ESLint, 17 Vitest tests, TypeScript và Vite production build đều đạt.
