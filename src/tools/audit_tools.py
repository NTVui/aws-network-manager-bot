"""Tools kiểm toán hoạt động hệ thống (CloudTrail)."""
import json
from datetime import datetime, timedelta, timezone
from langchain_core.tools import tool
from src.config import get_aws_client


@tool
def get_recent_aws_activities(hours_back: int = 24, max_events: int = 15) -> str:
    """
    Lấy lịch sử các hoạt động trên AWS account trong N giờ qua từ CloudTrail.
    Bao gồm: ai gọi API gì, lúc nào.
    
    LƯU Ý: CloudTrail có độ trễ 5-15 phút - sự kiện vừa xảy ra sẽ chưa hiện ngay.
    
    Args:
        hours_back: Số giờ muốn xem (mặc định 24)
        max_events: Số sự kiện tối đa (mặc định 15, tối đa 50)
    """
    try:
        cloudtrail = get_aws_client('cloudtrail')
        
        # Giới hạn max_events để tránh timeout
        max_events = min(max_events, 50)
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)
        
        # Gọi API với MaxResults nhỏ để nhanh hơn
        response = cloudtrail.lookup_events(
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=max_events
        )
        
        events = response.get('Events', [])
        if not events:
            return (
                f"Không có hoạt động nào trong {hours_back} giờ qua.\n\n"
                f"LƯU Ý: CloudTrail có độ trễ 5-15 phút. "
                f"Nếu vừa thực hiện thao tác, hãy đợi vài phút rồi thử lại."
            )
        
        SENSITIVE_ACTIONS = {
            'TerminateInstances': 'Xóa máy chủ',
            'DeleteSecurityGroup': 'Xóa Security Group',
            'AuthorizeSecurityGroupIngress': 'Mở cổng firewall',
            'CreateUser': 'Tạo IAM User mới',
            'DeleteUser': 'Xóa IAM User',
            'CreateAccessKey': 'Tạo Access Key',
            'StopLogging': 'Tắt CloudTrail',
            'ConsoleLogin': 'Đăng nhập Console',
        }
        
        result = f"BÁO CÁO KIỂM TOÁN AWS ({hours_back} GIỜ QUA)\n"
        result += f"Tổng số sự kiện: {len(events)}\n"
        result += f"Lưu ý: CloudTrail có độ trễ 5-15 phút.\n\n"
        
        result += "CHI TIẾT HOẠT ĐỘNG:\n"
        result += "-" * 60 + "\n"
        
        suspicious_actions = []
        event_types = {}
        
        for event in events:
            event_name = event.get('EventName', 'Unknown')
            event_time = event['EventTime'].strftime('%H:%M:%S')
            username = event.get('Username', 'N/A')
            
            event_types[event_name] = event_types.get(event_name, 0) + 1
            
            warning = ""
            if event_name in SENSITIVE_ACTIONS:
                warning = f" [{SENSITIVE_ACTIONS[event_name]}]"
                suspicious_actions.append(f"{event_time} - {event_name} bởi {username}")
            
            result += f"{event_time} | {event_name} | User: {username}{warning}\n"
        
        result += "\nTHỐNG KÊ TOP 5 HÀNH ĐỘNG:\n"
        for event_name, count in sorted(event_types.items(), key=lambda x: -x[1])[:5]:
            result += f"  - {event_name}: {count} lần\n"
        
        if suspicious_actions:
            result += "\nHÀNH ĐỘNG NHẠY CẢM PHÁT HIỆN:\n"
            for action in suspicious_actions[:5]:
                result += f"  ! {action}\n"
        
        return result
    except Exception as e:
        if "AccessDenied" in str(e):
            return "Lỗi: Tài khoản IAM cần quyền 'cloudtrail:LookupEvents'."
        if "Throttl" in str(e):
            return "Lỗi: AWS đang giới hạn tốc độ. Đợi 30 giây rồi thử lại."
        return f"Lỗi: {str(e)}"


@tool
def get_failed_login_attempts(hours_back: int = 24) -> str:
    """
    Phát hiện các lần đăng nhập thất bại vào AWS Console.
    
    QUAN TRỌNG: CloudTrail có độ trễ 5-15 phút. Nếu vừa fail login xong, 
    hãy đợi ít nhất 10 phút rồi mới gọi tool này.
    
    Args: hours_back - Số giờ kiểm tra (mặc định 24).
    """
    try:
        cloudtrail = get_aws_client('cloudtrail')
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)
        
        # Lấy ConsoleLogin events - giới hạn max 30 để tránh timeout
        response = cloudtrail.lookup_events(
            LookupAttributes=[
                {'AttributeKey': 'EventName', 'AttributeValue': 'ConsoleLogin'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=30
        )
        
        events = response.get('Events', [])
        
        if not events:
            return (
                f"Không tìm thấy sự kiện đăng nhập Console nào trong {hours_back} giờ qua.\n\n"
                f"NGUYÊN NHÂN CÓ THỂ:\n"
                f"1. Thực sự không có ai đăng nhập\n"
                f"2. CloudTrail chưa kịp ghi log (độ trễ 5-15 phút)\n"
                f"3. CloudTrail Trail chưa được bật cho region này\n\n"
                f"GỢI Ý: Đợi 10-15 phút sau khi fail login rồi thử lại."
            )
        
        failed_logins = []
        success_logins = []
        
        for event in events:
            try:
                event_detail = json.loads(event.get('CloudTrailEvent', '{}'))
                response_elements = event_detail.get('responseElements', {})
                source_ip = event_detail.get('sourceIPAddress', 'N/A')
                user_identity = event_detail.get('userIdentity', {})
                user = user_identity.get('userName') or event.get('Username', 'N/A')
                user_type = user_identity.get('type', 'N/A')
                time_str = event['EventTime'].strftime('%Y-%m-%d %H:%M:%S')
                
                login_status = response_elements.get('ConsoleLogin', '')
                
                entry = f"{time_str} | User: {user} ({user_type}) | IP: {source_ip}"
                
                if login_status == 'Failure':
                    failed_logins.append(entry)
                elif login_status == 'Success':
                    success_logins.append(entry)
            except Exception:
                continue
        
        result = f"BÁO CÁO ĐĂNG NHẬP CONSOLE ({hours_back} GIỜ QUA)\n"
        result += f"Tổng sự kiện ConsoleLogin: {len(events)}\n"
        result += f"  - Thành công: {len(success_logins)}\n"
        result += f"  - Thất bại: {len(failed_logins)}\n\n"
        
        if failed_logins:
            result += "PHÁT HIỆN ĐĂNG NHẬP THẤT BẠI:\n"
            result += "-" * 60 + "\n"
            for fail in failed_logins[:10]:
                result += f"  ! {fail}\n"
            
            if len(failed_logins) >= 5:
                result += "\nNGUY HIỂM: >= 5 lần thất bại - khả năng bị BRUTE-FORCE!\n"
                result += "HÀNH ĐỘNG KHẨN CẤP:\n"
                result += "  1. Bật MFA cho tất cả IAM Users\n"
                result += "  2. Đổi password ngay lập tức\n"
                result += "  3. Kiểm tra IP nguồn - block nếu lạ\n"
                result += "  4. Xem xét cấu hình AWS GuardDuty\n"
            elif len(failed_logins) >= 2:
                result += "\nCẢNH BÁO: Có nhiều lần fail login. Khuyến nghị bật MFA."
        else:
            result += "Không có đăng nhập thất bại nào.\n"
        
        if success_logins:
            result += f"\nĐĂNG NHẬP THÀNH CÔNG GẦN ĐÂY:\n"
            for success in success_logins[:5]:
                result += f"  - {success}\n"
        
        return result
    except Exception as e:
        if "Throttl" in str(e):
            return "Lỗi: AWS đang giới hạn tốc độ. Đợi 30 giây rồi thử lại."
        return f"Lỗi: {str(e)}"
    
@tool
def simulate_failed_login_demo() -> str:
    """
    Tạo báo cáo demo về các lần đăng nhập thất bại - DÀNH CHO DEMO/THUYẾT TRÌNH.
    Trả về dữ liệu chi tiết dạng bảng với IP, thời gian, username.
    """
    from datetime import datetime, timedelta
    
    now = datetime.now()
    demo_events = [
        {"time": now - timedelta(minutes=15), "user": "admin", "ip": "203.205.45.12", "country": "China", "status": "Failure"},
        {"time": now - timedelta(minutes=14), "user": "admin", "ip": "203.205.45.12", "country": "China", "status": "Failure"},
        {"time": now - timedelta(minutes=12), "user": "admin", "ip": "203.205.45.12", "country": "China", "status": "Failure"},
        {"time": now - timedelta(minutes=10), "user": "root", "ip": "117.34.89.123", "country": "Russia", "status": "Failure"},
        {"time": now - timedelta(minutes=8), "user": "root", "ip": "117.34.89.123", "country": "Russia", "status": "Failure"},
        {"time": now - timedelta(minutes=5), "user": "admin", "ip": "1.55.234.10", "country": "Vietnam", "status": "Success"},
    ]
    
    failed = [e for e in demo_events if e['status'] == 'Failure']
    success = [e for e in demo_events if e['status'] == 'Success']
    
    # Phân tích pattern
    ip_count = {}
    for e in failed:
        ip_count[e['ip']] = ip_count.get(e['ip'], 0) + 1
    
    # Build output dạng bảng Markdown
    result = "BÁO CÁO ĐĂNG NHẬP CONSOLE [CHẾ ĐỘ DEMO - 1 GIỜ QUA]\n\n"
    result += f"Tổng sự kiện: {len(demo_events)} | Thành công: {len(success)} | Thất bại: {len(failed)}\n\n"
    
    result += "BẢNG CHI TIẾT CÁC SỰ KIỆN ĐĂNG NHẬP:\n"
    result += "| Thời gian | User | IP nguồn | Quốc gia | Trạng thái |\n"
    result += "|-----------|------|----------|----------|------------|\n"
    for e in demo_events:
        time_str = e['time'].strftime('%H:%M:%S')
        status_icon = "FAILED" if e['status'] == 'Failure' else "OK"
        result += f"| {time_str} | {e['user']} | {e['ip']} | {e['country']} | {status_icon} |\n"
    
    result += "\nPHÂN TÍCH MỐI ĐE DỌA THEO IP:\n"
    result += "| IP nguồn | Số lần thất bại | Đánh giá |\n"
    result += "|----------|-----------------|----------|\n"
    for ip, count in sorted(ip_count.items(), key=lambda x: -x[1]):
        if count >= 3:
            assessment = "BRUTE-FORCE ATTACK"
        elif count >= 2:
            assessment = "Đáng nghi"
        else:
            assessment = "Cần theo dõi"
        result += f"| {ip} | {count} lần | {assessment} |\n"
    
    result += "\nKHUYẾN NGHỊ HÀNH ĐỘNG:\n"
    result += "1. **Bật MFA** ngay cho user 'admin' và 'root' (priority cao nhất)\n"
    result += "2. **Đổi password** cho 2 user trên\n"
    result += "3. **Block IP** 203.205.45.12 và 117.34.89.123 qua AWS WAF\n"
    result += "4. **Bật AWS GuardDuty** để phát hiện threat real-time\n"
    result += "5. **Setup CloudWatch Alarm** cảnh báo khi có >3 fail login/giờ\n\n"
    
    result += "[Lưu ý: Đây là dữ liệu demo. CloudTrail thật có độ trễ 5-15 phút]"
    return result