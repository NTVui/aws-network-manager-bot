"""
Fixtures dùng chung cho tất cả test.
Fixture là các "dữ liệu/object setup sẵn" để test có thể tái sử dụng.
@pytest.fixture là decorator của pytest giúp setup data trước khi test chạy. Mỗi test cần data gì chỉ việc khai báo trong tham số là tự động có. Đây là pattern DRY (Don't Repeat Yourself) - không phải copy code setup ở mỗi test.
"""
import os
import pytest
import boto3
from moto import mock_aws


# Set fake credentials TRƯỚC khi import gì khác
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def aws_credentials():
    """Đảm bảo các test không vô tình gọi AWS thật."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def ec2_client(aws_credentials):
    """Tạo EC2 client giả lập với moto."""
    with mock_aws():
        client = boto3.client('ec2', region_name='us-east-1')
        yield client


@pytest.fixture
def sample_instance(ec2_client):
    """Tạo sẵn 1 EC2 instance để test."""
    # Tạo VPC trước
    vpc = ec2_client.create_vpc(CidrBlock='10.0.0.0/16')
    vpc_id = vpc['Vpc']['VpcId']
    
    # Tạo subnet
    subnet = ec2_client.create_subnet(
        VpcId=vpc_id,
        CidrBlock='10.0.1.0/24',
        AvailabilityZone='us-east-1a'
    )
    subnet_id = subnet['Subnet']['SubnetId']
    
    # Tạo instance
    response = ec2_client.run_instances(
        ImageId='ami-0eb38b817b93460ac',
        InstanceType='t3.micro',
        MinCount=1,
        MaxCount=1,
        SubnetId=subnet_id,
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': 'test-server-01'}]
        }]
    )
    
    return {
        'instance_id': response['Instances'][0]['InstanceId'],
        'vpc_id': vpc_id,
        'subnet_id': subnet_id,
        'name': 'test-server-01'
    }


@pytest.fixture
def sample_security_group_vulnerable(ec2_client):
    """Tạo Security Group có lỗ hổng bảo mật để test audit."""
    vpc = ec2_client.create_vpc(CidrBlock='10.0.0.0/16')
    
    sg = ec2_client.create_security_group(
        GroupName='vulnerable-sg',
        Description='SG with security issues',
        VpcId=vpc['Vpc']['VpcId']
    )
    sg_id = sg['GroupId']
    
    # Mở cổng SSH (22) cho 0.0.0.0/0 - LỖ HỔNG
    ec2_client.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        }]
    )
    
    # Mở cổng MySQL (3306) public - LỖ HỔNG
    ec2_client.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            'IpProtocol': 'tcp',
            'FromPort': 3306,
            'ToPort': 3306,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        }]
    )
    
    return sg_id


@pytest.fixture
def sample_security_group_safe(ec2_client):
    """Tạo Security Group an toàn để test."""
    vpc = ec2_client.create_vpc(CidrBlock='10.0.0.0/16')
    
    sg = ec2_client.create_security_group(
        GroupName='safe-sg',
        Description='SG with proper config',
        VpcId=vpc['Vpc']['VpcId']
    )
    sg_id = sg['GroupId']
    
    # Chỉ mở SSH cho IP công ty cụ thể - AN TOÀN
    ec2_client.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': '203.205.45.0/24'}]
        }]
    )
    
    return sg_id