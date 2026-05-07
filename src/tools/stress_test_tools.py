"""Tools chạy stress test trên EC2 thông qua SSM."""
import time
from datetime import datetime, timedelta
from langchain_core.tools import tool
from src.config import get_aws_client


@tool
def run_stress_test(instance_id: str, duration_seconds: int = 60) -> str:
    """
    Chạy stress test trên một EC2 instance để kiểm tra hiệu năng và giám sát.
    Sử dụng AWS Systems Manager (SSM) - không cần SSH key.
    
    Args:
        instance_id: ID máy chủ EC2 cần test
        duration_seconds: Thời gian chạy stress test (mặc định 60 giây)
    
    Yêu cầu: EC2 phải có IAM Role 'AmazonSSMManagedInstanceCore' và SSM Agent.
    """
    try:
        ssm = get_aws_client('ssm')
        ec2 = get_aws_client('ec2')
        
        # Kiểm tra instance có online và quản lý được qua SSM không
        try:
            instance_info = ec2.describe_instances(InstanceIds=[instance_id])
            state = instance_info['Reservations'][0]['Instances'][0]['State']['Name']
            if state != 'running':
                return f"Máy {instance_id} đang ở trạng thái '{state}'. Cần BẬT máy trước khi stress test."
        except Exception:
            return f"Không tìm thấy máy {instance_id}."
        
        # Lệnh stress test: cài stress nếu chưa có, rồi chạy với 4 worker CPU
        commands = [
            "if ! command -v stress &> /dev/null; then sudo yum install -y stress 2>/dev/null || sudo apt-get install -y stress 2>/dev/null; fi",
            f"stress --cpu 4 --timeout {duration_seconds}s",
            "echo 'Stress test completed.'"
        ]
        
        # Gửi lệnh qua SSM
        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': commands},
            TimeoutSeconds=duration_seconds + 60,
            Comment=f"AI Stress Test - {duration_seconds}s"
        )
        
        command_id = response['Command']['CommandId']
        
        return (
            f"ĐÃ KHỞI CHẠY STRESS TEST trên máy {instance_id}\n"
            f"Command ID: {command_id}\n"
            f"Thời gian: {duration_seconds} giây\n"
            f"Cấu hình: 4 CPU worker chạy 100% load\n\n"
            f"GỢI Ý: Sau khi test xong (~{duration_seconds}s), gọi 'get_cpu_usage' "
            f"để xem CPU spike, hoặc xem biểu đồ real-time trên Dashboard.\n\n"
            f"LƯU Ý: Nếu lệnh không chạy, kiểm tra:\n"
            f"1. EC2 có IAM Role 'AmazonSSMManagedInstanceCore' chưa\n"
            f"2. SSM Agent đã được cài và chạy chưa (Amazon Linux 2023 có sẵn)\n"
            f"3. Security Group cho phép outbound HTTPS (port 443) ra Internet"
        )
    except Exception as e:
        if "InvalidInstanceId" in str(e):
            return f"Máy {instance_id} chưa được đăng ký với SSM. Cần gắn IAM Role 'AmazonSSMManagedInstanceCore'."
        return f"Lỗi khi chạy stress test: {str(e)}"


@tool
def check_stress_test_result(command_id: str, instance_id: str) -> str:
    """
    Kiểm tra kết quả của một stress test đã chạy trước đó.
    Args: command_id (lấy từ run_stress_test) và instance_id.
    """
    try:
        ssm = get_aws_client('ssm')
        response = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id
        )
        
        status = response['Status']
        output = response.get('StandardOutputContent', '')
        error = response.get('StandardErrorContent', '')
        
        result = f"TRẠNG THÁI STRESS TEST: {status}\n\n"
        if output:
            result += f"OUTPUT:\n{output[:500]}\n\n"
        if error:
            result += f"LỖI:\n{error[:500]}\n"
        
        if status == 'Success':
            result += "\nStress test hoàn tất thành công. Hãy kiểm tra biểu đồ CPU để thấy spike."
        elif status == 'InProgress':
            result += "\nStress test vẫn đang chạy. Vui lòng đợi thêm."
        elif status == 'Failed':
            result += "\nStress test thất bại. Kiểm tra log lỗi."
        
        return result
    except Exception as e:
        return f"Lỗi: {str(e)}"