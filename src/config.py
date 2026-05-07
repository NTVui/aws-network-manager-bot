"""Cấu hình chung cho toàn bộ ứng dụng."""
import os
import boto3
from dotenv import load_dotenv

# Load biến môi trường từ .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Cấu hình AWS
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_CONFIG = {
    'region_name': AWS_REGION,
    'aws_access_key_id': os.getenv("AWS_ACCESS_KEY_ID"),
    'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY")
}

# Cấu hình Groq AI
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.1-8b-instant"

# Bảng giá EC2 (USD/giờ - cập nhật 05/2026)
PRICING = {
    "t3.micro": 0.0104,
    "c7i-flex.large": 0.08479,
    "m7i-flex.large": 0.09576,
    "i3.large": 0.156
}

# AMI mặc định cho việc tạo EC2 (Amazon Linux 2023, x86_64)
DEFAULT_AMI = "ami-0eb38b817b93460ac"

# Tỷ giá USD-VND
USD_TO_VND = 26324

# Cổng nhạy cảm cần audit
SENSITIVE_PORTS = {
    22: "SSH (Brute-force Linux)",
    3389: "RDP (Brute-force Windows)",
    3306: "MySQL Database",
    5432: "PostgreSQL Database",
    27017: "MongoDB",
    6379: "Redis",
    21: "FTP (không mã hóa)",
    23: "Telnet (không mã hóa)"
}


def get_aws_client(service_name):
    """Factory function tạo AWS client với config chuẩn."""
    return boto3.client(service_name, **AWS_CONFIG)