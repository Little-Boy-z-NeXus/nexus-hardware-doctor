# NeXus wiring schematic v8

Bộ bảy sơ đồ này thay thế **INA226 R100** bằng **DFRobot Gravity I2C Digital Wattmeter SEN0291 (INA219, ±8 A)** và thêm **đế mở rộng ESP32/ESP32-S3 có jack DC 5–9 V**.

## Bảy trang

1. Nguồn, cầu chì, relay, E-stop, buck, INA219 và phân phối nguồn.
2. Cách đặt GOOUUU ESP32-S3-N16R8 lên đế mở rộng; INA219 và tay cầm PS2.
3. L298N số 1 cho bánh trước trái và bánh trước phải.
4. L298N số 2 cho bánh sau.
5. Ba encoder Hall A/B và màu dây.
6. Tổng thể xe tam giác, hai hành lang dây và trình tự bật thử.
7. Bảng phân cổng đầy đủ cho bốn PCT-213 và ba PCT-218.

Mở file `nexus-wiring-schematic-v8.html?sheet=1` đến `?sheet=7` để xem từng trang.

## Điểm thay đổi bắt buộc

- Đường công suất: `relay NO → INA219 VIN+ → INA219 VIN− → PCT MOTOR+ → VS của hai L298N`.
- Chân `GND` riêng của SEN0291 nối GND chung. **Không nối VIN− xuống GND.**
- SEN0291 không có dây `VBS/VBUS`; bỏ toàn bộ jumper kiểu INA226 cũ.
- INA219: `VCC→3V3`, `GND→GND`, `SDA→GPIO1`, `SCL→GPIO2`.
- Buck đặt đúng 5.0 V. Một ngõ USB cấp jack DC 5–9 V của đế; ngõ còn lại có thể cấp logic 5 V của hai L298N qua USB breakout.
- Chỉ cắm GOOUUU 40 chân vào đế 44P khi nhãn hai hàng và khoảng cách chân trùng hoàn toàn. **Không căn giữa theo số lỗ và không chừa 3V3/GND**; `3V3` phải trùng `3V3`, `GND` phải trùng `GND`, sau đó kiểm tra toàn bộ GPIO.
- Trước khi nối sensor/PS2/encoder, đo rail `V` của đế phải là **3.3 V**.
- Không dùng đồng thời USB máy tính và nguồn jack của đế trước khi xác minh mạch không backfeed.

## Bố trí ba bánh

- M1: trước trái — L298N #1 kênh A.
- M2: trước phải — L298N #1 kênh B.
- M3: bánh sau — L298N #2 kênh A.

## Nguồn tham chiếu

- Đế mở rộng: <https://dientutuyetnga.com/products/de-ra-chan-mo-rong-esp32-esp32-s3>
- INA219 SEN0291: <https://hshop.vn/cam-bien-cong-suat-tai-dc-dfrobot-gravity-i2c-digital-wattmeter>

> Các sơ đồ là tài liệu lắp ráp. Firmware hiện tại phải được đổi driver INA226 sang INA219 SEN0291 trước khi nạp cho cấu hình này.
