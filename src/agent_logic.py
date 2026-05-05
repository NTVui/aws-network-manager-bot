import os
import boto3
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from datetime import datetime, timedelta

load_dotenv()
# 1. Kết nối AWS (Bổ sung CloudWatch)
aws_config = {
    'region_name': os.getenv("AWS_REGION"),
    'aws_access_key_id': os.getenv("AWS_ACCESS_KEY_ID"),
    'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY")
}

ec2 = boto3.client('ec2', **aws_config)
cloudwatch = boto3.client('cloudwatch', **aws_config)

@tool
def get_ec2_status(query=""):
    """Công cụ lấy chi tiết thông tin server EC2 (Trạng thái, VPC, IP...)"""
    try:
        response = ec2.describe_instances()
        status_report = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                # Lấy tên từ Tags
                name = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), "Unnamed-Server")
                
                state = instance['State']['Name']
                inst_id = instance['InstanceId']
                vpc_id = instance.get('VpcId', 'N/A') # Lấy VPC ID
                subnet_id = instance.get('SubnetId', 'N/A')
                pub_ip = instance.get('PublicIpAddress', 'Không có IP Public')

                # Gộp thông tin chi tiết để AI "đọc" được
                detail = (f"- **{name}** ({inst_id}):\n"
                          f"  + Trạng thái: {state}\n"
                          f"  + VPC ID: {vpc_id}\n"
                          f"  + Subnet ID: {subnet_id}\n"
                          f"  + IP Public: {pub_ip}")
                status_report.append(detail)
                
        return "\n".join(status_report) if status_report else "Không tìm thấy server nào."
    except Exception as e:
        return f"Lỗi truy vấn AWS: {str(e)}"

@tool
def get_cpu_usage(instance_id: str):
    """
    Công cụ lấy phần trăm sử dụng CPU trung bình của một máy chủ EC2 trong 30 phút qua.
    Cần truyền vào Instance ID chính xác (ví dụ: i-0abcd1234).
    """
    try:
        # Lấy dữ liệu trong khoảng 30 phút gần nhất
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=30)

        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300, # Lấy mẫu 5 phút một lần
            Statistics=['Average']
        )

        datapoints = response.get('Datapoints', [])
        if not datapoints:
            return f"Không có dữ liệu CPU cho máy chủ {instance_id}. Có thể máy vừa bật hoặc chưa có dữ liệu giám sát."

        # Lấy điểm dữ liệu mới nhất
        latest_point = sorted(datapoints, key=lambda x: x['Timestamp'])[-1]
        cpu_val = round(latest_point['Average'], 2)
        
        return f"Chỉ số CPU trung bình mới nhất của máy {instance_id} là: {cpu_val}%."
    except Exception as e:
        return f"Lỗi khi lấy dữ liệu CloudWatch: {str(e)}"
    
def get_cpu_history_data(instance_id):
    """Trả về danh sách các điểm dữ liệu CPU để vẽ biểu đồ."""
    try:
        res = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=datetime.utcnow() - timedelta(hours=1),
            EndTime=datetime.utcnow(),
            Period=300,
            Statistics=['Average']
        )
        # Sắp xếp theo thời gian và chỉ lấy giá trị Average
        data = sorted(res['Datapoints'], key=lambda x: x['Timestamp'])
        return [d['Average'] for d in data]
    except:
        return []
    
@tool
def manage_ec2_power(instance_id: str, action: str):
    """
    Công cụ để điều khiển nguồn của máy chủ EC2.
    - action: 'START' để bật máy, 'STOP' để tắt máy.
    - instance_id: ID của máy cần điều khiển.
    """
    try:
        if action.upper() == 'START':
            ec2.start_instances(InstanceIds=[instance_id])
            return f"🚀 Đã gửi lệnh BẬT máy chủ {instance_id} thành công."
        elif action.upper() == 'STOP':
            ec2.stop_instances(InstanceIds=[instance_id])
            return f"😴 Đã gửi lệnh TẮT máy chủ {instance_id} thành công."
        else:
            return "Hành động không hợp lệ. Chỉ dùng START hoặc STOP."
    except Exception as e:
        return f"Lỗi điều khiển EC2: {str(e)}"

# Cập nhật danh sách tools của Agent
tools = [get_ec2_status, get_cpu_usage, manage_ec2_power]
# 2. Khởi tạo LLM Groq
llm = ChatGroq(
    temperature=0,
    model_name="llama-3.1-8b-instant",
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# 3. Khởi tạo Agent với LangGraph
agent = create_react_agent(
    llm,
    [get_ec2_status, get_cpu_usage, manage_ec2_power],
    prompt="Bạn là chuyên gia DevOps hỗ trợ vận hành mạng AWS. Trả lời bằng tiếng Việt chuyên nghiệp."
)

def ask_ai(question):
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": question}]})
        return result["messages"][-1].content
    except Exception as e:
        return f"Hệ thống gặp lỗi: {str(e)}"
