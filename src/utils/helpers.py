"""Các hàm helper dùng chung."""
from src.config import USD_TO_VND


def calculate_monthly_cost(hourly_rate):
    """Tính chi phí tháng từ giá theo giờ."""
    monthly_usd = hourly_rate * 24 * 30
    monthly_vnd = monthly_usd * USD_TO_VND
    return {
        "hourly_usd": hourly_rate,
        "monthly_usd": round(monthly_usd, 2),
        "monthly_vnd": "{:,.0f}".format(monthly_vnd)
    }


def get_instance_name(instance):
    """Lấy tên instance từ tags."""
    return next(
        (tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), 
        instance.get('InstanceId', 'N/A')
    )


def get_resource_name(resource, default='unnamed'):
    """Lấy tên của bất kỳ resource AWS nào có tag Name."""
    return next(
        (t['Value'] for t in resource.get('Tags', []) if t['Key'] == 'Name'), 
        default
    )


def find_instance_by_name_or_id(ec2_client, identifier):
    """Tìm instance theo tên hoặc Instance ID."""
    all_instances = ec2_client.describe_instances()
    
    for res in all_instances['Reservations']:
        for inst in res['Instances']:
            if inst['State']['Name'] == 'terminated':
                continue
            if inst['InstanceId'] == identifier:
                return inst
            name = get_instance_name(inst)
            if name and name.lower() == identifier.lower():
                return inst
    return None