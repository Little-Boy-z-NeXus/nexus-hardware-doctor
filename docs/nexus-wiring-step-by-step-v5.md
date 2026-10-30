# NeXus 3 bánh — đấu dây từng bước (v5)

Phiên bản này dành cho cấu hình hiện tại:

- GOOUUU ESP32-S3-N16R8
- 2 × L298N
- 3 × JGB37-520 12 V có encoder Hall A/B
- Tay cầm PS2 và receiver 9 chân
- LiPo OVONIC 3S 11,1 V 2200 mAh 75C, giắc XT60
- Relay 12 V 30 A có jumper HIGH/LOW
- Nút dừng khẩn LA16Y-11ZS, dùng tiếp điểm NC
- Buck 5 V 3 A, 2 cổng USB
- Cầu chì ô tô 4 A để chạy thử kê bánh
- Không dùng INA226, BNO055, BME680 và chưa lắp còi báo pin

## Quy ước màu và cỡ dây

| Màu | Dùng cho | Cỡ dây |
|---|---|---|
| Đỏ | LiPo +, +12 V, VS, motor M+ | 14 AWG ở đường công suất |
| Đen | LiPo − và GND chung | 14 AWG ở đường công suất |
| Đỏ/đen nhỏ | 5 V, 3,3 V và GND logic | 22–24 AWG |
| Cam/xanh dương | Điều khiển L298N và relay | 22–24 AWG |
| Vàng/xanh lá | Encoder A/B | 22–24 AWG |
| Trắng | Motor M− | 14–18 AWG |

Không đưa dòng motor qua breadboard hoặc dây Dupont.

## 0. Trước khi đấu

1. Rút XT60 và rút USB khỏi ESP32.
2. Kê cả ba bánh khỏi mặt bàn.
3. Tháo jumper 5V-EN trên cả hai L298N vì bản này cấp 5 V logic từ buck.
4. Relay để jumper LOW.
5. Dùng đồng hồ continuity xác định đúng hai chân NC của E-STOP: nhả nút thì thông, nhấn nút thì hở.
6. Xác định hai chân công tắc SW1: OFF thì hở, ON thì thông.

## 1. Dây nguồn 12 V — đấu đúng thứ tự này

Các cổng trong cùng một PCT-213 được xem là nối chung. Không nhét hai dây vào cùng một cổng.

| Số dây | Từ | Đến | Ghi chú |
|---:|---|---|---|
| P01 | XT60 dương của pin | Đầu vào đế cầu chì | Dây đỏ 14 AWG |
| P02 | Đầu ra đế cầu chì | PCT +12V-A cổng 1 | Lắp cầu chì 4 A sau khi đấu xong |
| P03 | PCT +12V-A cổng 2 | Relay COM | Dòng motor đi qua tiếp điểm relay |
| P04 | PCT +12V-A cổng 3 | PCT +12V-B cổng 1 | Dây nối cầu giữa hai PCT |
| P05 | PCT +12V-B cổng 2 | Relay DC+ hoặc VCC | Chỉ cấp nguồn cuộn relay |
| P06 | PCT +12V-B cổng 3 | Buck IN+ | Buck luôn có nguồn khi cắm XT60 |
| P07 | Relay NO | PCT MOTOR+ cổng 1 | NC bỏ trống |
| P08 | PCT MOTOR+ cổng 2 | L298N số 1 chân VS hoặc +12V | Motor 1 và motor 2 |
| P09 | PCT MOTOR+ cổng 3 | L298N số 2 chân VS hoặc +12V | Motor 3 |

## 2. GND chung

| Số dây | Từ | Đến | Ghi chú |
|---:|---|---|---|
| G01 | XT60 âm của pin | PCT GND-A cổng 1 | Dây đen 14 AWG |
| G02 | PCT GND-A cổng 2 | L298N số 1 GND | |
| G03 | PCT GND-A cổng 3 | PCT GND-B cổng 1 | Nối cầu |
| G04 | PCT GND-B cổng 2 | L298N số 2 GND | |
| G05 | PCT GND-B cổng 3 | PCT GND-C cổng 1 | Nối cầu |
| G06 | PCT GND-C cổng 2 | Buck IN− | |
| G07 | PCT GND-C cổng 3 | Relay DC− hoặc GND | |

ESP32 nhận GND qua cáp USB từ chính buck. Khi dùng cáp USB tách 5 V cho L298N, dây đen của cáp cũng phải về GND chung.

## 3. Công tắc chính và nút dừng khẩn

SW1 và E-STOP chỉ điều khiển chân IN của relay, không mang dòng ba motor.

| Số dây | Từ | Đến |
|---:|---|---|
| C01 | Relay IN | SW1 chân 1 |
| C02 | SW1 chân 2 | E-STOP chân NC thứ nhất |
| C03 | E-STOP chân NC thứ hai | GND chung |

Khi SW1 ON và E-STOP được nhả, IN bị kéo xuống GND, relay phải đóng COM–NO. Khi nhấn E-STOP hoặc tắt SW1, relay phải nhả và MOTOR+ phải về 0 V. Không đưa +12 V trực tiếp vào chân IN.

## 4. Nguồn 5 V logic

| Số dây | Từ | Đến | Ghi chú |
|---:|---|---|---|
| L01 | Buck USB 1 | Cổng USB của ESP32 | Cấp nguồn và giữ ESP32 ghi log khi motor bị ngắt |
| L02 | Buck USB 2 | Cáp USB-A hy sinh | Chỉ dùng đỏ = +5 V, đen = GND; bọc kín trắng và xanh |
| L03 | Đỏ +5 V của cáp L02 | SPL/PCT 5V cổng vào | |
| L04 | SPL/PCT 5V | L298N số 1 chân 5V | Đã tháo jumper 5V-EN |
| L05 | SPL/PCT 5V | L298N số 2 chân 5V | Đã tháo jumper 5V-EN |
| L06 | Đen GND của cáp L02 | GND chung | Bắt buộc |

Đo buck trước khi cắm ESP32: đầu USB phải khoảng 5,0 V, không được là 12 V.

## 5. Tụ lọc

- Tụ điện phân 1000 µF/25 V số 1: chân dương vào VS của L298N số 1, chân âm có sọc vào GND của L298N số 1.
- Tụ điện phân 1000 µF/25 V số 2: chân dương vào VS của L298N số 2, chân âm có sọc vào GND của L298N số 2.
- Mỗi motor có một tụ gốm 100 nF mắc trực tiếp giữa hai chân motor M+ và M−. Tụ gốm không phân cực.

## 6. Ba motor và encoder

Thứ tự sáu dây motor đã chốt: đỏ, đen, vàng, xanh lá, xanh dương, trắng tương ứng M+, GND encoder, A, B, VCC 3,3 V, M−.

| Motor | Driver | M+ đỏ | M− trắng | Encoder A vàng | Encoder B xanh lá |
|---|---|---|---|---|---|
| M1 | L298N số 1 kênh A | OUT1 | OUT2 | GPIO16 | GPIO17 |
| M2 | L298N số 1 kênh B | OUT3 | OUT4 | GPIO4 | GPIO5 |
| M3 | L298N số 2 kênh A | OUT1 | OUT2 | GPIO9 | GPIO10 |

Tất cả dây encoder xanh dương vào 3V3 ESP32. Tất cả dây encoder đen vào GND chung. Không cấp 5 V cho encoder nếu chưa có datasheet xác nhận.

## 7. Điều khiển L298N từ ESP32

| Chức năng | GPIO ESP32 | Chân L298N |
|---|---:|---|
| Motor 1 PWM | 12 | L298N số 1 ENA |
| Motor 1 chiều 1 | 13 | L298N số 1 IN1 |
| Motor 1 chiều 2 | 14 | L298N số 1 IN2 |
| Motor 2 PWM | 15 | L298N số 1 ENB |
| Motor 2 chiều 1 | 18 | L298N số 1 IN3 |
| Motor 2 chiều 2 | 21 | L298N số 1 IN4 |
| Motor 3 PWM | 6 | L298N số 2 ENA |
| Motor 3 chiều 1 | 7 | L298N số 2 IN1 |
| Motor 3 chiều 2 | 8 | L298N số 2 IN2 |

L298N số 2 kênh B không dùng; không cắm motor vào OUT3/OUT4.

## 8. Receiver PS2

| Dây/nhãn receiver | Nối vào ESP32 |
|---|---|
| VCC đỏ | 3V3 |
| GND đen | GND |
| CLK xám | GPIO41 |
| ATTN cam | GPIO40 |
| CMD xanh lá | GPIO39 |
| DATA xanh dương | GPIO38 |
| ACK | Không nối |
| NC | Không nối |
| VIBR | Không nối |

## 9. Trình tự cấp điện lần đầu

1. Chưa lắp cầu chì, đo điện trở giữa bus +12V và GND: không được gần 0 Ω.
2. Tháo hai dây VS khỏi L298N, lắp cầu chì 4 A, cắm pin và đo buck = 5 V.
3. Cắm ESP32 qua USB của buck; xác nhận firmware boot và PS2 kết nối.
4. Bật/tắt SW1 và nhấn/nhả E-STOP; đo PCT MOTOR+: khoảng điện áp pin khi relay ON và 0 V khi OFF.
5. Tắt nguồn, nối VS hai L298N, chưa nối motor; bật lại và kiểm tra không nóng/bốc mùi.
6. Tắt nguồn, nối từng motor một; thử PWM thấp khi bánh đang kê.
7. Chỉ sau khi ba motor chạy đúng chiều mới đặt xe xuống đất.

Nếu relay không đóng theo logic trên, dừng lại và chụp rõ hai mặt module relay cùng chữ in cạnh từng chân; không thử đoán vị trí chân.
