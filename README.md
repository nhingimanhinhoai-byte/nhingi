# License Manager (Offline)

Đây là ứng dụng desktop quản lý license cá nhân. Dữ liệu được lưu bằng SQLite ngay trên máy, không cần server hay Internet để vận hành.

## Chạy thử từ mã nguồn

1. Cài Python 3.11+ từ [python.org](https://www.python.org/downloads/windows/) và chọn **Add Python to PATH** khi cài.
2. Nhấp đúp `license_manager.py`, hoặc mở Command Prompt tại thư mục này và chạy:

   ```bat
   py license_manager.py
   ```

Không cần cài thêm thư viện để chạy ứng dụng.

## Tạo file `LicenseManager.exe` trên Windows

1. Cài Python như hướng dẫn trên.
2. Nhấp đúp `build_windows.bat`.
3. Chờ cửa sổ lệnh báo `Da tao: dist\LicenseManager.exe`.
4. File có thể gửi cho người dùng nằm tại `dist\LicenseManager.exe`; người dùng chỉ cần click đúp để chạy.

`build_windows.bat` sẽ tự cài PyInstaller, rồi đóng gói app thành một file `.exe` không hiện cửa sổ lệnh.

## Dữ liệu và backup

- Database nằm tại: `%USERPROFILE%\LicenseManager\license_manager.db`.
- Trong app chọn **Backup** để tạo file JSON trước khi đổi máy hoặc cài lại Windows.
- Dùng **Khôi phục** để nạp file JSON đó. Khôi phục sẽ thay thế dữ liệu đang có.

## MQL5

Nhập Account, Broker, ngày bắt đầu và số ngày, sau đó nhấn **COPY LICENSE**. App tạo đoạn `#define` MQL5 để dán vào EA.
