# NeXus wiring schematic v9

Bộ bảy sơ đồ này dùng **ESP32-S3 DevKitC-compatible N16R8 44 pin**, **DFRobot Gravity I2C Digital Wattmeter SEN0291 (INA219, ±8 A)** và đế mở rộng ESP32-S3 44 pin. Đế chỉ dùng để mở rộng chân; nguồn 5 V đi vào cổng USB-C nối với mạch USB-to-UART/COM của ESP32.

## Bảy trang

1. Nguồn, cầu chì, relay, E-stop, buck, INA219 và phân phối nguồn.
2. Cách đặt ESP32-S3 DevKitC 44 pin lên đế mở rộng; INA219 và tay cầm PS2.
3. L298N số 1 cho bánh trước trái và bánh trước phải.
4. L298N số 2 cho bánh sau.
5. Ba encoder Hall A/B và màu dây.
6. Tổng thể xe tam giác, hai hành lang dây và trình tự bật thử.
7. Bảng phân cổng đầy đủ cho bốn PCT-213 và ba PCT-218.

Mở file `nexus-wiring-schematic-v9.html?sheet=1` đến `?sheet=7` để xem từng trang.

## Điểm thay đổi bắt buộc

- Đường công suất: `relay NO → INA219 IN+ → INA219 IN− → PCT MOTOR+ → VS của hai L298N`.
- Chân `GND` riêng của SEN0291 nối GND chung. **Không nối IN− xuống GND.**
- SEN0291 không có dây `VBS/VBUS`; bỏ toàn bộ jumper kiểu INA226 cũ.
- INA219: `VCC→3V3`, `GND→GND`, `SDA→GPIO1`, `SCL→GPIO2`.
- Buck đặt đúng 5.0 V. Một ngõ USB cấp cổng USB-C UART/COM của ESP32; ngõ còn lại cấp logic 5 V của hai L298N qua USB breakout.
- ESP32-S3 mới có đúng 44 chân: cắm đủ 22 chân mỗi bên, `3V3` trùng `3V3`, `GND` trùng `GND` và toàn bộ GPIO trùng chữ in trên đế.
- Không dùng jack DC của đế trong cấu hình này; tuyệt đối không đưa LiPo 3S/12 V vào jack hoặc chân 5V của ESP32.
- Trước khi nối sensor/PS2/encoder, đo rail `V` của đế phải là **3.3 V**.
- Không dùng đồng thời USB máy tính và USB 5 V từ buck.

## Bố trí ba bánh

- M1: trước trái — L298N #1 kênh A.
- M2: trước phải — L298N #1 kênh B.
- M3: bánh sau — L298N #2 kênh A.

## Nguồn tham chiếu

- Đế mở rộng: <https://dientutuyetnga.com/products/de-ra-chan-mo-rong-esp32-esp32-s3>
- INA219 SEN0291: <https://hshop.vn/cam-bien-cong-suat-tai-dc-dfrobot-gravity-i2c-digital-wattmeter>

Firmware mặc định là `nexus-esp32-s3-devkitc-3wheel-ps2`; driver SEN0291 được cấu hình ở địa chỉ I²C `0x40`, SDA `GPIO1`, SCL `GPIO2`.
