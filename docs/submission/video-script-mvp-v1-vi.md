# NeXus MVP V1 — kịch bản video Devpost 2:50

Kịch bản này dành riêng cho MVP một motor: **GOOUUU ESP32-S3-N16R8 + INA226 R100 + L298N + JGB37-520 encoder**. Không dùng hình ảnh hoặc lời thoại của bản xe ba bánh.

## Thông điệp chấm giải

- Lĩnh vực: **Physical AI**.
- NVIDIA: `nvidia/Nemotron-3-Ultra-550b-a55b`.
- Hạ tầng: Nebius Token Factory / Nebius AI Cloud.
- Điểm khác biệt: phần cứng được chuẩn hoá thành JSON Hardware-as-Code; AI chỉ đề xuất, còn policy quyết định và hệ thống phải xác minh bằng mẫu telemetry mới.
- Phần cứng thật phải xuất hiện liên tục ít nhất từ **00:20 đến 01:35** — tổng cộng 75 giây.

## Kịch bản quay

| Thời gian | Hình ảnh cần quay | Lời thoại tiếng Anh đọc nguyên văn |
| --- | --- | --- |
| **00:00–00:12** | Logo NeXus, tên đội và dòng chữ `Physical AI · Nebius × NVIDIA`. Cắt nhanh sang motor và dashboard. | **“Hardware failures are difficult because software usually cannot see the wiring, power path, or physical motion. NeXus is an AI doctor that makes real hardware understandable and safely diagnosable.”** |
| **00:12–00:20** | Hiện sơ đồ kiến trúc: `Hardware → Telemetry → Backend → NVIDIA Nemotron on Nebius → Safety Policy → Verify`. | **“It combines live telemetry with NVIDIA Nemotron running through Nebius, while deterministic safety policy remains in control.”** |
| **00:20–00:40** | Góc rộng phần cứng thật, nguồn motor đang tắt. Chỉ lần lượt vào ESP32, INA226 R100, L298N, JGB37-520 encoder, cầu chì/công tắc nguồn. | **“This is our real MVP: a GOOUUU ESP32-S3, an INA226 R100 power monitor, an L298N driver, and a twelve-volt JGB37 motor with a Hall encoder. The motor rail has a physical switch, and the controller starts with PWM disabled.”** |
| **00:40–00:58** | Mở trang Hardware, chọn `Rig 1 motor · live`. Hiện BOM, profile ID và bảng dây. Đặt cửa sổ cạnh phần cứng. | **“Every component, pin, connection, safety limit, and telemetry field is defined in one versioned JSON hardware profile. Firmware, backend, and browser use the same source of truth, so a mismatched sensor or firmware is reported explicitly.”** |
| **00:58–01:18** | Nâng bánh/motor khỏi mặt bàn. Bật nguồn 12 V. Chỉ vào số đo voltage/current, trạng thái COM13; chạy motor ở PWM thấp và cho camera thấy motor quay cùng RPM trên UI. Sau đó dừng. | **“Now the backend reads real serial data from COM13, stores the raw log, and streams it to the browser. Voltage and current show electrical behavior, while the encoder provides independent evidence that the motor actually moves.”** |
| **01:18–01:35** | Tắt nguồn motor. Khi an toàn, tháo SDA hoặc SCL của INA226 để tạo lỗi tín hiệu; giữ cả phần cứng và UI trong khung hình. | **“For a controlled fault, I disconnect one I-squared-C signal wire with motor power off. NeXus immediately distinguishes a missing sensor acknowledgement from a normal powered-off motor rail and tells the operator exactly which pins to inspect.”** |
| **01:35–02:05** | Chuyển sang AI Doctor, chọn rõ `Live Nebius`, không chọn Simulator. Hỏi: `The motor stopped. Diagnose it from the latest device telemetry and wiring graph.` Hiện câu trả lời, evidence ID và hypothesis. | **“I ask the AI Doctor to diagnose the stopped motor. The request goes to NVIDIA Nemotron Three Ultra through Nebius Token Factory. Nemotron receives only the machine-readable graph, fresh device evidence, and allowlisted read-only tools. It ranks grounded hypotheses instead of inventing measurements.”** |
| **02:05–02:28** | Hiện timeline/audit: telemetry → Nemotron → policy → tool → verify. Phóng to model/provider metadata đã redacted; tuyệt đối không hiện API key. | **“The model never controls electrical limits or talks directly to the motor. Its proposal enters a bounded orchestrator; deterministic policy approves or rejects each tool, and every observation, model call, decision, and verification is recorded under one trace.”** |
| **02:28–02:43** | Cắm lại SDA/SCL khi nguồn motor vẫn tắt. Đợi INA226 trở lại healthy, sau đó bật nguồn và chạy lại test PWM thấp; chỉ vào mẫu telemetry mới và RPM. | **“After reconnecting the wire, NeXus requires a newer telemetry sample before declaring recovery. The sensor returns, the supervised motor test runs, and encoder RPM confirms physical motion.”** |
| **02:43–02:50** | Logo, URL GitHub public, giấy phép, dòng `NeXus — AI doctor for physical hardware`. | **“NeXus reduces hardware debugging time without giving AI unsafe authority: one real machine today, and a reusable Physical AI platform next.”** |

## Thứ tự thao tác trên máy khi quay

1. Giữ motor hoặc bánh xe nâng khỏi mặt bàn; công tắc 12 V ở trạng thái OFF.
2. Chạy backend và frontend; xác nhận `COM13 connected` và đúng profile `nexus-profile-goouuu-esp32-s3-ina226-l298n-jgb37-v1`.
3. Chọn **Rig 1 motor · live** trước khi bắt đầu quay.
4. Xác nhận INA226 healthy, có telemetry `source=device`, timestamp mới và log đang được lưu.
5. Mở sẵn AI Doctor nhưng chỉ chọn **Live Nebius** ở đúng cảnh 01:35.
6. Bật nguồn 12 V, chạy PWM thấp có giám sát, rồi dừng hoàn toàn.
7. Tắt 12 V trước khi tháo SDA/SCL. Không cắm/rút dây khi motor rail đang bật.
8. Sau khi quay lỗi, cắm lại dây khi 12 V vẫn OFF; đợi sensor healthy rồi mới chạy bài test phục hồi.

## Cảnh bắt buộc phải nhìn rõ

- Phần cứng thật chạy ít nhất một phút tổng cộng và motor thực sự quay.
- UI ghi `COM13`, đúng GOOUUU, đúng INA226 R100; không để màn hình bản xe ba bánh xuất hiện.
- Telemetry có `source=device`, voltage/current, PWM, RPM và timestamp mới.
- AI Doctor đang ở chế độ **Live Nebius**, không phải Simulator.
- Tên model NVIDIA Nemotron và nhà cung cấp Nebius xuất hiện ở metadata hoặc phụ đề.
- Timeline có evidence/tool/policy/verify; API key và raw secret không xuất hiện.
- Cuối video hiện URL repository public, giấy phép mã nguồn mở và URL demo nếu có.

## Checklist trước khi bấm Record

- [ ] INA226 trả ACK ở `0x40`; không còn `INA226_I2C_NO_ACK`.
- [ ] Bus voltage và current hợp lý; RPM thay đổi khi motor quay.
- [ ] Motor dừng ngay khi PWM về 0 hoặc tắt công tắc nguồn.
- [ ] Live Nebius gọi thành công và hiện model NVIDIA đúng.
- [ ] Đã đăng xuất/ẩn terminal chứa biến môi trường và API key.
- [ ] Quay ngang 1080p; chữ UI đọc được; âm thanh rõ.
- [ ] Tổng video dưới 03:00; cảnh phần cứng thật ít nhất 01:00.
- [ ] Tải video lên YouTube ở chế độ Public và thử link bằng cửa sổ ẩn danh.

## Câu hỏi dùng trong AI Doctor

```text
The motor stopped. Diagnose the latest source=device telemetry using the active
hardware graph. Use only read-only tools, cite the evidence IDs, and explain the
next safe physical check.
```

Không quay Simulator như bằng chứng Nebius. Nếu live call thất bại, dừng quay, sửa kết nối/API rồi quay lại thay vì dựng một kết quả giả.
