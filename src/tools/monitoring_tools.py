"""Tools giám sát hiệu năng (CloudWatch)."""
from datetime import datetime, timedelta
from langchain_core.tools import tool
from src.config import get_aws_client


@tool
def get_cpu_usage(instance_id: str):
    """
    Lấy phần trăm sử dụng CPU trung bình của một EC2 trong 30 phút qua.
    Cần truyền vào Instance ID chính xác (ví dụ: i-0abcd1234).
    """
    try:
        cloudwatch = get_aws_client('cloudwatch')
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=30)

        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Average']
        )

        datapoints = response.get('Datapoints', [])
        if not datapoints:
            return f"Không có dữ liệu CPU cho máy chủ {instance_id}. Có thể máy vừa bật hoặc chưa có dữ liệu giám sát."

        latest_point = sorted(datapoints, key=lambda x: x['Timestamp'])[-1]
        cpu_val = round(latest_point['Average'], 2)
        return f"Chỉ số CPU trung bình mới nhất của máy {instance_id} là: {cpu_val}%."
    except Exception as e:
        return f"Lỗi khi lấy dữ liệu CloudWatch: {str(e)}"


def get_cpu_history_data(instance_id):
    """Trả về danh sách điểm dữ liệu CPU trong 1 giờ qua để vẽ biểu đồ."""
    try:
        cloudwatch = get_aws_client('cloudwatch')
        res = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=datetime.utcnow() - timedelta(hours=1),
            EndTime=datetime.utcnow(),
            Period=300,
            Statistics=['Average']
        )
        data = sorted(res['Datapoints'], key=lambda x: x['Timestamp'])
        return [d['Average'] for d in data]
    except Exception:
        return []