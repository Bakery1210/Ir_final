"""
Competition Client - Đăng ký, chấm điểm và theo dõi kết quả
MSSV: B22DCVT415
Schema: Theo slide Modified 2
"""

import requests
import time
import socket
import sys
import os


# ============================================================
# CẤU HÌNH
# ============================================================
TEACHER_BASE_URL = "http://192.168.50.218:8000/api/v1"
STUDENT_ID = "B22DCVT415"
STUDENT_SERVER_PORT = 5050
MAX_SUBMISSIONS = 5  # Giới hạn 5 lần nộp
TOTAL_QUESTIONS = 100  # 100 câu hỏi

HEADERS = {
    "X-Student-ID": STUDENT_ID,
    "Content-Type": "application/json"
}


# ============================================================
# ERROR HELPER
# ============================================================
def print_error(title: str, error: Exception, suggestions: list):
    """In thông báo lỗi chi tiết kèm cách sửa."""
    print(f"\n  {'='*50}")
    print(f"  ❌ LỖI: {title}")
    print(f"  {'='*50}")
    print(f"  Chi tiết: {type(error).__name__}: {error}")
    print(f"\n  💡 CÁCH SỬA:")
    for i, s in enumerate(suggestions, 1):
        print(f"     {i}. {s}")
    print(f"  {'='*50}\n")


def diagnose_connection_error(e: Exception, target: str) -> list:
    """Phân tích lỗi kết nối và đưa ra gợi ý cụ thể."""
    error_str = str(e).lower()
    suggestions = []

    if "connection refused" in error_str or "refused" in error_str:
        if "localhost" in target or "127.0.0.1" in target:
            suggestions = [
                "Student Server chưa chạy!",
                "Mở Terminal mới → source .venv/bin/activate → python3 student_server.py",
                f"Kiểm tra: curl http://localhost:{STUDENT_SERVER_PORT}/",
            ]
        else:
            suggestions = [
                f"Teacher Server ({TEACHER_BASE_URL}) không phản hồi",
                "Kiểm tra: Đã kết nối WiFi ASUS_E0 chưa?",
                f"Thử ping: ping 192.168.50.218",
                "Teacher Server có thể chưa bật hoặc đang restart",
            ]
    elif "timeout" in error_str or "timed out" in error_str:
        suggestions = [
            "Request bị timeout — mạng chậm hoặc server quá tải",
            "Kiểm tra kết nối mạng: ping 192.168.50.218",
            "Đợi 30 giây rồi thử lại",
            "Nếu đang evaluate: Teacher Server đang chờ Student Server trả lời",
        ]
    elif "name or service not known" in error_str or "nodename" in error_str or "getaddrinfo" in error_str:
        suggestions = [
            "Không thể phân giải tên miền/IP",
            "Kiểm tra URL Teacher Server có đúng không",
            f"URL hiện tại: {TEACHER_BASE_URL}",
            "Kiểm tra kết nối mạng",
        ]
    elif "network is unreachable" in error_str or "network unreachable" in error_str:
        suggestions = [
            "Mạng không thể truy cập",
            "Kiểm tra đã kết nối WiFi chưa",
            "Thử disconnect rồi reconnect WiFi ASUS_E0",
        ]
    else:
        suggestions = [
            f"Lỗi kết nối: {e}",
            "Kiểm tra kết nối mạng WiFi ASUS_E0",
            f"Thử: curl {TEACHER_BASE_URL}/competition/result -H 'X-Student-ID: {STUDENT_ID}'",
        ]

    return suggestions


# ============================================================
# NETWORK HELPERS
# ============================================================
def get_lan_ip():
    """Tự động tìm IP LAN của máy."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('192.168.50.218', 1))
        ip = s.getsockname()[0]
    except Exception:
        # Fallback: thử tìm IP 192.168.x.x
        try:
            s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s2.connect(('8.8.8.8', 1))
            ip = s2.getsockname()[0]
            s2.close()
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def check_student_server():
    """Kiểm tra Student Server có đang chạy không."""
    try:
        res = requests.get(f"http://localhost:{STUDENT_SERVER_PORT}/", timeout=5)
        data = res.json()
        return True, data
    except requests.exceptions.ConnectionError:
        return False, "Student Server chưa chạy! Mở terminal khác và chạy: python3 student_server.py"
    except requests.exceptions.Timeout:
        return False, "Student Server phản hồi quá chậm. Kiểm tra server có bị treo không."
    except Exception as e:
        return False, f"Lỗi khi kiểm tra Student Server: {e}"


def check_teacher_server():
    """Kiểm tra kết nối tới Teacher Server."""
    try:
        res = requests.get(
            f"{TEACHER_BASE_URL}/competition/result",
            headers=HEADERS,
            timeout=10
        )
        return True, res.json()
    except requests.exceptions.ConnectionError as e:
        return False, f"Không kết nối được Teacher Server. Kiểm tra WiFi ASUS_E0!\nPing thử: ping 192.168.50.218"
    except requests.exceptions.Timeout:
        return False, "Teacher Server không phản hồi (timeout). Server có thể đang quá tải."
    except Exception as e:
        return False, f"Lỗi: {e}"


LAN_IP = get_lan_ip()
MY_SERVER_URL = f"http://{LAN_IP}:{STUDENT_SERVER_PORT}"


# ============================================================
# PRE-FLIGHT CHECK — Kiểm tra hệ thống trước khi chạy
# ============================================================
def preflight_check():
    """Kiểm tra tất cả điều kiện trước khi bắt đầu thi."""
    print(f"\n  {'='*50}")
    print(f"  🔍 KIỂM TRA HỆ THỐNG")
    print(f"  {'='*50}")

    all_ok = True

    # 1. Kiểm tra Student Server
    print(f"\n  [1/3] Student Server (localhost:{STUDENT_SERVER_PORT})...", end=" ")
    ok, info = check_student_server()
    if ok:
        print(f"✅ Running")
        if isinstance(info, dict):
            print(f"        Vector DB: {'✅ Loaded ' + str(info.get('total_chunks', '?')) + ' chunks' if info.get('vector_db_loaded') else '⬜ Trống (sẽ upload lần đầu)'}")
    else:
        print(f"❌ FAILED")
        print(f"        {info}")
        all_ok = False

    # 2. Kiểm tra Teacher Server
    print(f"  [2/3] Teacher Server ({TEACHER_BASE_URL})...", end=" ")
    ok, info = check_teacher_server()
    if ok:
        print(f"✅ Connected")
        if isinstance(info, dict):
            print(f"        Status: {info.get('status', '?')} | Score: {info.get('score', '?')}")
    else:
        print(f"❌ FAILED")
        print(f"        {info}")
        all_ok = False

    # 3. Kiểm tra LAN IP
    print(f"  [3/3] LAN IP detection...", end=" ")
    if LAN_IP == '127.0.0.1':
        print(f"⚠️ Fallback (127.0.0.1)")
        print(f"        Teacher Server có thể không gọi được Student Server!")
        print(f"        💡 Kiểm tra kết nối mạng ASUS_E0")
        all_ok = False
    else:
        print(f"✅ {LAN_IP}")
        print(f"        Student Server URL: {MY_SERVER_URL}")

    print(f"\n  {'='*50}")

    if not all_ok:
        print(f"  ⚠️ Có vấn đề cần sửa trước khi bắt đầu!")
        print(f"  Bạn vẫn muốn tiếp tục? (y/n): ", end="")
        choice = input().strip().lower()
        if choice != 'y':
            return False

    print(f"  ✅ Hệ thống sẵn sàng!")
    print(f"  {'='*50}")
    return True


# ============================================================
# API FUNCTIONS
# ============================================================
def register():
    """Đăng ký Student Server URL lên Teacher Server."""
    print(f"\n  {'='*50}")
    print(f"  📝 ĐĂNG KÝ SERVER")
    print(f"     URL: {MY_SERVER_URL}")
    print(f"     MSSV: {STUDENT_ID}")
    print(f"  {'='*50}")

    # Kiểm tra Student Server trước
    ok, info = check_student_server()
    if not ok:
        print(f"\n  ❌ Student Server chưa chạy!")
        print(f"  💡 CÁCH SỬA:")
        print(f"     1. Mở Terminal mới")
        print(f"     2. cd vào thư mục project")
        print(f"     3. source .venv/bin/activate")
        print(f"     4. python3 student_server.py")
        print(f"     5. Chờ thấy 'Uvicorn running on http://0.0.0.0:{STUDENT_SERVER_PORT}'")
        print(f"     6. Quay lại terminal này và thử lại")
        return False

    try:
        res = requests.post(
            f"{TEACHER_BASE_URL}/competition/register",
            headers=HEADERS,
            json={"server_url": MY_SERVER_URL},
            timeout=15
        )

        if res.status_code == 200:
            data = res.json()
            print(f"  ✅ Đăng ký thành công!")
            print(f"     Response: {data}")
            return True
        else:
            print(f"  ❌ Teacher Server trả về status {res.status_code}")
            print(f"     Response: {res.text}")
            if res.status_code == 422:
                print(f"  💡 Lỗi validation — kiểm tra format request body")
                print(f"     Body gửi đi: {{'server_url': '{MY_SERVER_URL}'}}")
            elif res.status_code == 404:
                print(f"  💡 Endpoint không tồn tại!")
                print(f"     URL: {TEACHER_BASE_URL}/competition/register")
                print(f"     Kiểm tra có /v1/ trong URL chưa!")
            elif res.status_code == 400:
                print(f"  💡 Request không hợp lệ. Kiểm tra lại MSSV header.")
            return False

    except requests.exceptions.ConnectionError as e:
        suggestions = diagnose_connection_error(e, TEACHER_BASE_URL)
        print_error("Không kết nối được Teacher Server", e, suggestions)
        return False
    except requests.exceptions.Timeout as e:
        print_error("Teacher Server không phản hồi", e, [
            "Server có thể đang quá tải",
            "Đợi 30 giây rồi thử lại",
            f"Thử ping: ping 192.168.50.218",
        ])
        return False
    except Exception as e:
        print_error("Lỗi không xác định khi đăng ký", e, [
            f"Chi tiết: {type(e).__name__}: {e}",
            "Thử chạy lại lệnh",
        ])
        return False


def evaluate(document_received: bool = False):
    """Bắt đầu quá trình chấm điểm."""
    print(f"\n  {'='*50}")
    print(f"  🎯 BẮT ĐẦU CHẤM ĐIỂM")
    print(f"     document_received: {document_received}")
    if document_received:
        print(f"     → Chỉ gửi câu hỏi, KHÔNG upload lại tài liệu")
    else:
        print(f"     → Sẽ upload tài liệu trước (~2 phút), sau đó gửi {TOTAL_QUESTIONS} câu hỏi")
    print(f"  {'='*50}")

    # Kiểm tra Student Server
    ok, info = check_student_server()
    if not ok:
        print(f"\n  ❌ Student Server chưa chạy! Không thể evaluate.")
        print(f"  💡 Chạy student_server.py ở terminal khác trước!")
        return None

    # Kiểm tra vector DB nếu document_received=True
    if document_received and isinstance(info, dict) and not info.get('vector_db_loaded'):
        print(f"\n  ⚠️ CẢNH BÁO: document_received=True nhưng Vector DB trống!")
        print(f"  💡 Bạn chưa upload tài liệu lần nào hoặc vector_db bị xóa.")
        print(f"  💡 Nên chọn document_received=False (Chọn 1) để upload trước.")
        print(f"  Bạn vẫn muốn tiếp tục? (y/n): ", end="")
        choice = input().strip().lower()
        if choice != 'y':
            return None

    # Cảnh báo giới hạn nộp
    print(f"\n  ⚠️ LƯU Ý: Mỗi sinh viên chỉ được nộp tối đa {MAX_SUBMISSIONS} lần!")
    print(f"  Xác nhận bắt đầu evaluate? (y/n): ", end="")
    choice = input().strip().lower()
    if choice != 'y':
        print(f"  → Đã hủy evaluate")
        return None

    try:
        print(f"\n  ⏳ Đang gửi request evaluate... (có thể mất vài phút)")

        res = requests.post(
            f"{TEACHER_BASE_URL}/competition/evaluate",
            headers=HEADERS,
            json={"document_received": document_received},
            timeout=600  # 10 phút (upload 2min + 100 câu x 60s)
        )

        if res.status_code == 200:
            data = res.json()
            print(f"\n  ✅ Evaluate hoàn thành!")
            print(f"     Response: {data}")
            return data
        else:
            print(f"\n  ❌ Teacher Server trả về status {res.status_code}")
            print(f"     Response: {res.text[:500]}")

            if res.status_code == 422:
                print(f"  💡 Lỗi validation — kiểm tra request body")
                print(f"     Body gửi: {{'document_received': {document_received}}}")
                print(f"     Schema đúng: EvaluateRequest(document_received: Optional[bool] = False)")
            elif res.status_code == 404:
                print(f"  💡 Endpoint không tồn tại!")
                print(f"     URL: {TEACHER_BASE_URL}/competition/evaluate")
                print(f"     Kiểm tra có /v1/ trong URL!")
            elif res.status_code == 400:
                print(f"  💡 Có thể đã hết lượt nộp ({MAX_SUBMISSIONS} lần)")
                print(f"     Hoặc chưa register trước")
            elif res.status_code == 500:
                print(f"  💡 Teacher Server lỗi nội bộ — liên hệ giáo viên")
            return None

    except requests.exceptions.ConnectionError as e:
        suggestions = diagnose_connection_error(e, TEACHER_BASE_URL)
        # Thêm gợi ý đặc biệt cho evaluate
        suggestions.append("Nếu đang evaluate và bị mất kết nối: thử gọi /result để xem tiến độ")
        print_error("Mất kết nối trong quá trình evaluate", e, suggestions)
        return None
    except requests.exceptions.Timeout:
        print(f"\n  ⏰ Request evaluate bị timeout (>10 phút)")
        print(f"  💡 CÁCH SỬA:")
        print(f"     1. Gọi /result để xem Teacher Server đã chấm đến đâu")
        print(f"     2. Chọn 3 (Xem kết quả) trong menu")
        print(f"     3. Nếu status='completed' → đã xong, không cần evaluate lại")
        print(f"     4. Nếu status='evaluating' → đang chấm, đợi thêm")
        print(f"     5. Nếu status='error' → reset và thử lại")
        return None
    except Exception as e:
        print_error("Lỗi không xác định trong evaluate", e, [
            f"Type: {type(e).__name__}",
            "Thử gọi /result để xem tiến độ (Chọn 3)",
            "Nếu cần, reset (Chọn 4) rồi thử lại",
        ])
        return None


def get_result():
    """Theo dõi tiến độ chấm điểm."""
    print(f"\n  {'='*50}")
    print(f"  📊 THEO DÕI TIẾN ĐỘ CHẤM ĐIỂM")
    print(f"  {'='*50}")

    consecutive_errors = 0
    max_errors = 10

    while True:
        try:
            res = requests.get(
                f"{TEACHER_BASE_URL}/competition/result",
                headers=HEADERS,
                timeout=10
            )

            if res.status_code != 200:
                print(f"\n  ❌ Status {res.status_code}: {res.text[:200]}")
                if res.status_code == 404:
                    print(f"  💡 Chưa đăng ký hoặc endpoint sai. Đăng ký trước (Chọn 5).")
                    return None
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    print(f"\n  ❌ Quá nhiều lỗi liên tiếp ({max_errors}). Dừng polling.")
                    return None
                time.sleep(3)
                continue

            data = res.json()
            consecutive_errors = 0  # Reset error count

            status = data.get('status', 'unknown')
            current = data.get('current_question', 0)
            score = data.get('score', 0)

            # Progress bar
            progress = int((current / TOTAL_QUESTIONS) * 30) if TOTAL_QUESTIONS > 0 else 0
            bar = '█' * progress + '░' * (30 - progress)

            print(f"\r  [{bar}] {current}/{TOTAL_QUESTIONS} | Điểm: {score} | Status: {status}  ", end='', flush=True)

            if status == 'completed':
                print(f"\n\n  {'='*50}")
                print(f"  🎉 ĐÃ CHẤM XONG!")
                print(f"  📊 Kết quả: {data}")
                print(f"  {'='*50}")
                return data
            elif status == 'error':
                print(f"\n\n  ❌ Teacher Server báo lỗi!")
                print(f"  Response: {data}")
                print(f"  💡 CÁCH SỬA:")
                print(f"     1. Reset trạng thái (Chọn 4)")
                print(f"     2. Kiểm tra Student Server có đang chạy không")
                print(f"     3. Evaluate lại (Chọn 1 hoặc 2)")
                return data

        except requests.exceptions.ConnectionError as e:
            consecutive_errors += 1
            print(f"\n  ⚠️ Mất kết nối ({consecutive_errors}/{max_errors})... đang thử lại...")
            if consecutive_errors >= max_errors:
                print(f"\n  ❌ Mất kết nối liên tục. Kiểm tra WiFi ASUS_E0!")
                return None
        except requests.exceptions.Timeout:
            consecutive_errors += 1
            print(f"\n  ⚠️ Timeout ({consecutive_errors}/{max_errors})... đang thử lại...")
        except requests.exceptions.JSONDecodeError as e:
            print(f"\n  ❌ Response không phải JSON: {res.text[:200]}")
            print(f"  💡 Teacher Server có thể đang restart")
        except KeyboardInterrupt:
            print(f"\n\n  ⏹ Đã dừng polling (Ctrl+C). Dùng Chọn 3 để xem lại kết quả.")
            return None

        time.sleep(3)


def reset():
    """Reset trạng thái thi để bắt đầu lại."""
    print(f"\n  {'='*50}")
    print(f"  🔄 RESET TRẠNG THÁI THI")
    print(f"  {'='*50}")

    try:
        res = requests.post(
            f"{TEACHER_BASE_URL}/competition/reset",
            headers=HEADERS,
            timeout=15
        )

        if res.status_code == 200:
            data = res.json()
            print(f"  ✅ Reset thành công!")
            print(f"     Response: {data}")
            return True
        else:
            print(f"  ❌ Status {res.status_code}: {res.text[:300]}")
            if res.status_code == 404:
                print(f"  💡 Endpoint không tồn tại. Kiểm tra URL có /v1/!")
            return False

    except requests.exceptions.ConnectionError as e:
        suggestions = diagnose_connection_error(e, TEACHER_BASE_URL)
        print_error("Không kết nối được Teacher Server", e, suggestions)
        return False
    except requests.exceptions.Timeout:
        print_error("Teacher Server timeout", TimeoutError("timeout"), [
            "Server có thể quá tải. Đợi 30s rồi thử lại.",
        ])
        return False
    except Exception as e:
        print_error("Lỗi khi reset", e, [f"Type: {type(e).__name__}", "Thử lại sau."])
        return False


# ============================================================
# MENU CHÍNH
# ============================================================
def show_menu():
    """Hiển thị menu lựa chọn."""
    print(f"\n  {'='*50}")
    print(f"    🏆 RAG COMPETITION CLIENT — {STUDENT_ID}")
    print(f"    📡 Server URL: {MY_SERVER_URL}")
    print(f"    📌 Giới hạn: {MAX_SUBMISSIONS} lần nộp | {TOTAL_QUESTIONS} câu/lần")
    print(f"  {'='*50}")
    print(f"    1. Đăng ký + Chấm điểm LẦN ĐẦU  (upload + hỏi)")
    print(f"    2. Chấm điểm LẦN SAU             (chỉ hỏi, ko upload)")
    print(f"    3. Xem kết quả hiện tại")
    print(f"    4. Reset trạng thái thi")
    print(f"    5. Chỉ đăng ký (register)")
    print(f"    6. Kiểm tra hệ thống (pre-flight)")
    print(f"    7. Thoát")
    print(f"  {'='*50}")


def main():
    # Hỗ trợ CLI arguments
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "first":
            if register():
                evaluate(document_received=False)
                get_result()
        elif cmd == "again":
            reset()
            evaluate(document_received=True)
            get_result()
        elif cmd == "result":
            get_result()
        elif cmd == "reset":
            reset()
        elif cmd == "register":
            register()
        elif cmd == "check":
            preflight_check()
        elif cmd == "help":
            print(f"\n  Sử dụng: python run_competition.py [command]")
            print(f"  Commands:")
            print(f"    first    — Đăng ký + evaluate lần đầu (upload + hỏi)")
            print(f"    again    — Reset + evaluate lần sau (chỉ hỏi)")
            print(f"    result   — Xem kết quả hiện tại")
            print(f"    reset    — Reset trạng thái thi")
            print(f"    register — Chỉ đăng ký")
            print(f"    check    — Kiểm tra hệ thống")
            print(f"    help     — Hiện hướng dẫn này")
        else:
            print(f"  ❌ Lệnh không hợp lệ: '{cmd}'")
            print(f"  💡 Chạy: python run_competition.py help")
        return

    # Menu tương tác
    while True:
        show_menu()
        try:
            choice = input("    Chọn (1-7): ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n  👋 Tạm biệt!")
            break

        if choice == '1':
            if register():
                evaluate(document_received=False)
                get_result()
        elif choice == '2':
            reset()
            evaluate(document_received=True)
            get_result()
        elif choice == '3':
            get_result()
        elif choice == '4':
            reset()
        elif choice == '5':
            register()
        elif choice == '6':
            preflight_check()
        elif choice == '7':
            print(f"  👋 Tạm biệt!")
            break
        else:
            print(f"  ❌ Lựa chọn không hợp lệ: '{choice}'. Nhập số từ 1-7.")


if __name__ == "__main__":
    main()
