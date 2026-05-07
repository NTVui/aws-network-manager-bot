"""Tools quản lý hạ tầng mạng (VPC, Subnet, Routing)."""
from langchain_core.tools import tool
from src.config import get_aws_client
from src.utils.helpers import get_resource_name


@tool
def get_network_topology() -> str:
    """
    Lấy thông tin chi tiết toàn bộ hạ tầng mạng AWS bao gồm:
    VPC, Subnet (Public/Private), Internet Gateway, NAT Gateway, Route Tables.
    """
    try:
        ec2 = get_aws_client('ec2')
        vpcs = ec2.describe_vpcs()['Vpcs']
        subnets = ec2.describe_subnets()['Subnets']
        igws = ec2.describe_internet_gateways()['InternetGateways']
        nat_gws = ec2.describe_nat_gateways()['NatGateways']
        route_tables = ec2.describe_route_tables()['RouteTables']
        
        # Tìm public subnets
        public_subnet_ids = set()
        for rt in route_tables:
            if any(r.get('GatewayId', '').startswith('igw-') for r in rt.get('Routes', [])):
                for assoc in rt.get('Associations', []):
                    if assoc.get('SubnetId'):
                        public_subnet_ids.add(assoc['SubnetId'])
        
        result = "SƠ ĐỒ HẠ TẦNG MẠNG AWS\n\n"
        result += f"VPCs (Tổng: {len(vpcs)}):\n"
        for vpc in vpcs:
            is_default = " - Default VPC" if vpc.get('IsDefault') else ""
            result += f"  - {get_resource_name(vpc)} ({vpc['VpcId']}) | CIDR: {vpc['CidrBlock']}{is_default}\n"
        
        result += f"\nSubnets (Tổng: {len(subnets)}):\n"
        for s in subnets:
            stype = "Public" if s['SubnetId'] in public_subnet_ids else "Private"
            result += f"  - {get_resource_name(s)} ({s['SubnetId']}) | {stype} | {s['CidrBlock']} | {s['AvailabilityZone']}\n"
        
        result += f"\nInternet Gateways: {len(igws)}\n"
        active_nats = [n for n in nat_gws if n['State'] == 'available']
        result += f"NAT Gateways hoạt động: {len(active_nats)}\n"
        
        return result
    except Exception as e:
        return f"Lỗi: {str(e)}"


def get_network_topology_raw():
    """Trả về dữ liệu network dạng dict để vẽ diagram."""
    try:
        ec2 = get_aws_client('ec2')
        return {
            "vpcs": ec2.describe_vpcs()['Vpcs'],
            "subnets": ec2.describe_subnets()['Subnets'],
            "igws": ec2.describe_internet_gateways()['InternetGateways'],
            "nat_gws": ec2.describe_nat_gateways()['NatGateways'],
            "route_tables": ec2.describe_route_tables()['RouteTables'],
            "instances": ec2.describe_instances()['Reservations']
        }
    except Exception as e:
        return {"error": str(e)}


def build_mermaid_diagram(topology_data, hide_default_vpc=True):
    """Tạo Mermaid diagram phong cách học thuật."""
    """
    Tạo Mermaid diagram phong cách học thuật, rõ ràng, không icon.
    Mỗi node giải thích chức năng bằng từ ngữ dễ hiểu.
    """
    if "error" in topology_data:
        return f"graph TD\n   Error[Lỗi: {topology_data['error']}]"
    
    # Lọc Default VPC
    vpcs_to_show = topology_data['vpcs']
    if hide_default_vpc:
        vpcs_to_show = [v for v in vpcs_to_show if not v.get('IsDefault')]
        if not vpcs_to_show:
            vpcs_to_show = topology_data['vpcs']
    
    # Tìm public subnets
    public_subnet_ids = set()
    for rt in topology_data['route_tables']:
        has_igw = any(r.get('GatewayId', '').startswith('igw-') for r in rt.get('Routes', []))
        if has_igw:
            for assoc in rt.get('Associations', []):
                if assoc.get('SubnetId'):
                    public_subnet_ids.add(assoc['SubnetId'])
    
    # Bắt đầu vẽ - phong cách clean, đường nét đậm
    mermaid = "graph TB\n"
    mermaid += "   classDef internetStyle fill:#4A90E2,stroke:#2E5C8A,stroke-width:3px,color:#fff,font-size:18px\n"
    mermaid += "   classDef igwStyle fill:#FF6600,stroke:#CC7700,stroke-width:3px,color:#fff,font-size:16px\n"
    mermaid += "   classDef publicStyle fill:#FFE082,stroke:#F57F17,stroke-width:2px,color:#333,font-size:14px\n"
    mermaid += "   classDef privateStyle fill:#A5D6A7,stroke:#2E7D32,stroke-width:2px,color:#333,font-size:14px\n"
    mermaid += "   classDef vpcStyle fill:#F3E5F5,stroke:#6A1B9A,stroke-width:3px,color:#4A148C\n"
    mermaid += "   classDef ec2Style fill:#FFCDD2,stroke:#C62828,stroke-width:2px,color:#333,font-size:13px\n"
    mermaid += "\n"
    
    # Internet
    mermaid += '   Internet["INTERNET"]:::internetStyle\n\n'
    
    # Vẽ từng VPC
    for vpc in vpcs_to_show:
        vpc_id_safe = vpc['VpcId'].replace('-', '_')
        vpc_name = next(
            (t['Value'] for t in vpc.get('Tags', []) if t['Key'] == 'Name'), 
            'VPC chính'
        )
        
        mermaid += f'   subgraph VPC_{vpc_id_safe}["VPC: {vpc_name} - Mạng riêng của bạn (Dải IP: {vpc["CidrBlock"]})"]\n'
        mermaid += f"      direction TB\n"
        
        # IGW
        igw_node_id = None
        for igw in topology_data['igws']:
            if igw.get('Attachments') and igw['Attachments'][0]['VpcId'] == vpc['VpcId']:
                igw_node_id = igw['InternetGatewayId'].replace('-', '_')
                mermaid += f'      {igw_node_id}["INTERNET GATEWAY<br/><br/>Cửa ra Internet duy nhất<br/>Không có nó - mạng bị cô lập"]:::igwStyle\n'
        
        # Subnets
        vpc_subnets = [s for s in topology_data['subnets'] if s['VpcId'] == vpc['VpcId']]
        
        for subnet in vpc_subnets:
            subnet_id_safe = subnet['SubnetId'].replace('-', '_')
            subnet_name = next(
                (t['Value'] for t in subnet.get('Tags', []) if t['Key'] == 'Name'), 
                subnet['SubnetId'][-8:]
            )
            is_public = subnet['SubnetId'] in public_subnet_ids
            
            # Đếm EC2 trong subnet
            instance_list = []
            for res in topology_data['instances']:
                for inst in res['Instances']:
                    if inst['State']['Name'] == 'terminated':
                        continue
                    if inst.get('SubnetId') == subnet['SubnetId']:
                        inst_name = next(
                            (t['Value'] for t in inst.get('Tags', []) if t['Key'] == 'Name'),
                            inst['InstanceId'][-6:]
                        )
                        instance_list.append((
                            inst['InstanceId'].replace('-', '_'), 
                            inst_name, 
                            inst['State']['Name']
                        ))
            
            # Label theo loại subnet
            if is_public:
                type_title = "PUBLIC SUBNET (Mạng công khai)"
                desc1 = "Có IP public - lộ ra Internet"
                desc2 = "Đặt: Web Server, Load Balancer"
                css_class = "publicStyle"
            else:
                type_title = "PRIVATE SUBNET (Mạng nội bộ)"
                desc1 = "Không có IP public - được bảo vệ"
                desc2 = "Đặt: Database, Backend Service"
                css_class = "privateStyle"
            
            label = (
                f"{type_title}<br/>"
                f"<br/>"
                f"Tên: {subnet_name}<br/>"
                f"Dải IP: {subnet['CidrBlock']}<br/>"
                f"Vùng: {subnet['AvailabilityZone']}<br/>"
                f"<br/>"
                f"<i>{desc1}</i><br/>"
                f"<i>{desc2}</i>"
            )
            mermaid += f'      {subnet_id_safe}["{label}"]:::{css_class}\n'
            
            # EC2 instances
            for inst_id, inst_name, inst_state in instance_list:
                state_text = "Đang chạy" if inst_state == "running" else "Đã tắt"
                mermaid += f'      {inst_id}["EC2 Server<br/>Tên: {inst_name}<br/>Trạng thái: {state_text}"]:::ec2Style\n'
                mermaid += f"      {subnet_id_safe} --> {inst_id}\n"
        
        mermaid += "   end\n\n"
        
        # Kết nối Internet -> IGW -> Public Subnet
        if igw_node_id:
            mermaid += f'   Internet ==>|"Đi vào VPC qua đây"| {igw_node_id}\n'
            for subnet in vpc_subnets:
                if subnet['SubnetId'] in public_subnet_ids:
                    subnet_id_safe = subnet['SubnetId'].replace('-', '_')
                    mermaid += f'   {igw_node_id} ==>|"Định tuyến traffic"| {subnet_id_safe}\n'
    
        return mermaid
    