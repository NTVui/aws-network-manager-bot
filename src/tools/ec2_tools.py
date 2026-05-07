"""Tools quản lý EC2 instances."""
from langchain_core.tools import tool
from src.config import get_aws_client, PRICING, DEFAULT_AMI
from src.utils.helpers import get_instance_name


@tool
def get_ec2_status():
    """
    Lấy danh sách chi tiết tất cả máy chủ EC2 bao gồm: 
    Tên, ID, Trạng thái, VPC ID + VPC Name, Subnet ID + Subnet Name, 
    AZ, IP Public, IP Private, Instance Type, Giá tiền.
    """
    try:
        ec2 = get_aws_client('ec2')
        response = ec2.describe_instances()
        
        # Lấy thông tin VPCs để map ID → Name
        vpcs_response = ec2.describe_vpcs()
        vpc_map = {}
        for vpc in vpcs_response['Vpcs']:
            vpc_name = next(
                (t['Value'] for t in vpc.get('Tags', []) if t['Key'] == 'Name'),
                'unnamed'
            )
            # Đánh dấu Default VPC
            if vpc.get('IsDefault'):
                vpc_name = f"{vpc_name} (Default VPC)"
            vpc_map[vpc['VpcId']] = {
                'name': vpc_name,
                'cidr': vpc['CidrBlock']
            }
        
        # Lấy thông tin Subnets để map ID → Name
        subnets_response = ec2.describe_subnets()
        subnet_map = {}
        for subnet in subnets_response['Subnets']:
            subnet_name = next(
                (t['Value'] for t in subnet.get('Tags', []) if t['Key'] == 'Name'),
                'unnamed'
            )
            subnet_map[subnet['SubnetId']] = {
                'name': subnet_name,
                'cidr': subnet['CidrBlock'],
                'az': subnet['AvailabilityZone']
            }
        
        # Lấy public subnets (subnet có route đến IGW)
        route_tables = ec2.describe_route_tables()['RouteTables']
        public_subnet_ids = set()
        for rt in route_tables:
            if any(r.get('GatewayId', '').startswith('igw-') for r in rt.get('Routes', [])):
                for assoc in rt.get('Associations', []):
                    if assoc.get('SubnetId'):
                        public_subnet_ids.add(assoc['SubnetId'])
        
        # Build danh sách instances với thông tin enriched
        instances_info = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] == 'terminated':
                    continue
                
                it_type = instance['InstanceType']
                vpc_id = instance.get('VpcId', 'N/A')
                subnet_id = instance.get('SubnetId', 'N/A')
                
                # Enrich VPC info
                vpc_info = vpc_map.get(vpc_id, {})
                vpc_name = vpc_info.get('name', 'N/A')
                vpc_cidr = vpc_info.get('cidr', 'N/A')
                
                # Enrich Subnet info
                subnet_info = subnet_map.get(subnet_id, {})
                subnet_name = subnet_info.get('name', 'N/A')
                subnet_cidr = subnet_info.get('cidr', 'N/A')
                az = subnet_info.get('az', instance.get('Placement', {}).get('AvailabilityZone', 'N/A'))
                subnet_type = "Public" if subnet_id in public_subnet_ids else "Private"
                
                instances_info.append({
                    "Name": get_instance_name(instance),
                    "InstanceId": instance['InstanceId'],
                    "Status": instance['State']['Name'],
                    "InstanceType": it_type,
                    "HourlyPrice": PRICING.get(it_type, 0),
                    # VPC info đầy đủ
                    "VpcId": vpc_id,
                    "VpcName": vpc_name,
                    "VpcCidr": vpc_cidr,
                    # Subnet info đầy đủ
                    "SubnetId": subnet_id,
                    "SubnetName": subnet_name,
                    "SubnetType": subnet_type,
                    "SubnetCidr": subnet_cidr,
                    "AvailabilityZone": az,
                    # IP info
                    "PublicIP": instance.get('PublicIpAddress', 'N/A'),
                    "PrivateIP": instance.get('PrivateIpAddress', 'N/A'),
                })
        
        if not instances_info:
            return "Không tìm thấy máy chủ nào trong vùng us-east-1."
        return instances_info
    except Exception as e:
        return f"Lỗi khi truy xuất dữ liệu AWS: {str(e)}"


@tool
def manage_ec2_power(instance_id: str, action: str):
    """
    Điều khiển nguồn của máy chủ EC2.
    - action: 'START' để bật máy, 'STOP' để tắt máy.
    - instance_id: ID của máy cần điều khiển.
    """
    try:
        ec2 = get_aws_client('ec2')
        if action.upper() == 'START':
            ec2.start_instances(InstanceIds=[instance_id])
            return f"Đã gửi lệnh BẬT máy chủ {instance_id} thành công."
        elif action.upper() == 'STOP':
            ec2.stop_instances(InstanceIds=[instance_id])
            return f"Đã gửi lệnh TẮT máy chủ {instance_id} thành công."
        else:
            return "Hành động không hợp lệ. Chỉ dùng START hoặc STOP."
    except Exception as e:
        return f"Lỗi điều khiển EC2: {str(e)}"


@tool
def create_ec2_instance(instance_type: str, instance_name: str):
    """Tạo EC2 với AMI Amazon Linux 2023 (x86_64), tự động gắn IAM Role cho SSM."""
    try:
        ec2 = get_aws_client('ec2')
        
        # Cấu hình cơ bản
        run_args = {
            'ImageId': DEFAULT_AMI,
            'InstanceType': instance_type,
            'MinCount': 1,
            'MaxCount': 1,
            'TagSpecifications': [{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': instance_name}]
            }]
        }
        
        # Thử gắn IAM Role nếu có
        try:
            iam = get_aws_client('iam')
            iam.get_instance_profile(InstanceProfileName='EC2-SSM-Role')
            run_args['IamInstanceProfile'] = {'Name': 'EC2-SSM-Role'}
        except Exception:
            pass  # Nếu chưa tạo Instance Profile, vẫn tạo máy bình thường
        
        response = ec2.run_instances(**run_args)
        instance_id = response['Instances'][0]['InstanceId']
        return f"✅ Đã tạo thành công {instance_name} ({instance_id}). Trạng thái: Pending."
    except Exception as e:
        return f"❌ Lỗi: {str(e)}. Lưu ý: AMI này chỉ hỗ trợ kiến trúc x86_64."


@tool
def terminate_ec2_instance(instance_id: str):
    """Xóa bỏ hoàn toàn một máy chủ EC2 để ngừng tính phí."""
    try:
        ec2 = get_aws_client('ec2')
        ec2.terminate_instances(InstanceIds=[instance_id])
        return f"Đã gửi lệnh xóa máy chủ {instance_id}. Dữ liệu sẽ bị xóa hoàn toàn."
    except Exception as e:
        return f"Lỗi khi xóa: {str(e)}"