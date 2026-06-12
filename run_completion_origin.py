import requests
import time
import socket

# Hàm hỗ trợ tự động tìm IP LAN (Để bạn không phải sửa file thủ công)
def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Cố gắng kết nối tới Teacher Server để HĐH tự chọn đúng Card mạng
        s.connect(('192.168.50.218', 1))
        ip = s.getsockname()[0]
    except Exception:
        # Fallback IP trong trường hợp chưa kết nối tới mạng (Lấy IP Wifi hiện tại)
        ip = '172.16.28.174'
    finally:
        s.close()
    return ip

# Cấu hình hệ thống
TEACHER_BASE_URL = "http://192.168.50.218:8000/api/v1"
STUDENT_ID = "B22DCVT415"
# Tự động lấy IP mạng LAN của máy bạn thay vì phải sửa thủ công
LAN_IP = get_lan_ip()
MY_SERVER_URL = f"http://{LAN_IP}:5050"

HEADERS = {
    "X-Student-ID": STUDENT_ID
}

def register():
    print(f"1. Đang đăng ký Server với URL: {MY_SERVER_URL} ...")
    try:
        res = requests.post(
            f"{TEACHER_BASE_URL}/competition/register",
            headers=HEADERS,
            json={"server_url": MY_SERVER_URL}
        )
        print(res.json())
    except Exception as e:
        print(f"Lỗi khi đăng ký: Không thể kết nối tới {TEACHER_BASE_URL}. Bạn đã kết nối đúng vào mạng WiFi ASUS_E0 chưa?")

def evaluate():
    print("\n2. Yêu cầu bắt đầu chấm điểm (Teacher Server sẽ bắt đầu gọi /upload và /ask của bạn)...")
    try:
        res = requests.post(
            f"{TEACHER_BASE_URL}/competition/evaluate",
            headers=HEADERS
        )
        print(res.json())
    except Exception as e:
        pass

def get_result():
    print("\n3. Theo dõi tiến độ chấm điểm:")
    while True:
        try:
            res = requests.get(
                f"{TEACHER_BASE_URL}/competition/result",
                headers=HEADERS
            )
            data = res.json()
            print(f"Status: {data.get('status')} | Câu hiện tại: {data.get('current_question', 0)}/10 | Điểm: {data.get('score', 0)}")
            
            if data.get('status') == 'completed':
                print("\n🎉 ĐÃ CHẤM XONG!")
                print(f"Kết quả cuối cùng: {data}")
                break
        except Exception as e:
            print(f"Lỗi kết nối tới server thầy giáo. Đang thử lại...")
            
        time.sleep(3) # Cập nhật mỗi 3 giây

if __name__ == "__main__":
    register()
    evaluate()
    get_result()