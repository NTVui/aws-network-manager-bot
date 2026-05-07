"""Tools kiểm tra bảo mật (Security Groups)."""
from langchain_core.tools import tool
from src.config import get_aws_client, SENSITIVE_PORTS
from src.utils.helpers import get_instance_name


@tool
def audit_security_groups() -> str:
    """
    Kiểm tra toàn bộ Security Groups trên AWS để phát hiện lỗ hổng bảo mật.
    Tool này KHÔNG cần tham số đầu vào.
    """
    try:
        ec2 = get_aws_client('ec2')
        sgs = ec2.describe_security_groups()['SecurityGroups']
        
        vulnerabilities = []
        for sg in sgs:
            sg_id = sg['GroupId']
            sg_name = sg['GroupName']
            
            for rule in sg.get('IpPermissions', []):
                from_port = rule.get('FromPort')
                to_port = rule.get('ToPort')
                protocol = rule.get('IpProtocol', 'N/A')
                
                is_public_v4 = any(ip.get('CidrIp') == '0.0.0.0/0' for ip in rule.get('IpRanges', []))
                is_public_v6 = any(ip.get('CidrIpv6') == '::/0' for ip in rule.get('Ipv6Ranges', []))
                
                if not (is_public_v4 or is_public_v6):
                    continue
                
                if protocol == '-1':
                    vulnerabilities.append(
                        f"NGHIÊM TRỌNG | SG: {sg_name} ({sg_id}) đang mở TẤT CẢ các cổng ra Internet."
                    )
                    continue
                
                if from_port in SENSITIVE_PORTS:
                    risk_name = SENSITIVE_PORTS[from_port]
                    vulnerabilities.append(
                        f"CẢNH BÁO | SG: {sg_name} ({sg_id}) mở cổng {from_port} - {risk_name} ra Internet."
                    )
                elif from_port is not None and to_port is not None:
                    if (to_port - from_port) > 100:
                        vulnerabilities.append(
                            f"CẢNH BÁO | SG: {sg_name} ({sg_id}) mở dải cổng rộng {from_port}-{to_port} ra Internet."
                        )
        
        if not vulnerabilities:
            return "KẾT QUẢ AUDIT: Tất cả Security Groups đều an toàn."
        
        result = f"KẾT QUẢ AUDIT BẢO MẬT - Phát hiện {len(vulnerabilities)} vấn đề:\n\n"
        result += "\n".join(vulnerabilities)
        result += "\n\nKHUYẾN NGHỊ: Hạn chế CIDR về IP công ty hoặc dùng AWS Systems Manager Session Manager."
        return result
    except Exception as e:
        return f"Lỗi khi audit Security Groups: {str(e)}"


@tool
def get_security_groups_of_instance(instance_name_or_id: str) -> str:
    """
    Lấy thông tin chi tiết Security Groups của MỘT máy chủ EC2 cụ thể.
    Args: instance_name_or_id - Tên máy hoặc Instance ID.
    """
    try:
        ec2 = get_aws_client('ec2')
        all_instances = ec2.describe_instances()
        
        target_instance = None
        for res in all_instances['Reservations']:
            for inst in res['Instances']:
                if inst['State']['Name'] == 'terminated':
                    continue
                if inst['InstanceId'] == instance_name_or_id:
                    target_instance = inst
                    break
                name_tag = get_instance_name(inst)
                if name_tag and name_tag.lower() == instance_name_or_id.lower():
                    target_instance = inst
                    break
            if target_instance:
                break
        
        if not target_instance:
            return f"Không tìm thấy máy chủ '{instance_name_or_id}'."
        
        instance_id = target_instance['InstanceId']
        instance_name = get_instance_name(target_instance)
        sg_ids = [sg['GroupId'] for sg in target_instance.get('SecurityGroups', [])]
        
        if not sg_ids:
            return f"Máy {instance_name} không có Security Group nào."
        
        sgs_detail = ec2.describe_security_groups(GroupIds=sg_ids)['SecurityGroups']
        
        result = f"SECURITY GROUPS của máy {instance_name} ({instance_id}):\n\n"
        for sg in sgs_detail:
            result += f"- {sg['GroupName']} ({sg['GroupId']})\n"
            result += f"  Mô tả: {sg.get('Description', 'N/A')}\n"
            result += f"  VPC: {sg.get('VpcId', 'N/A')}\n"
            result += "  Inbound Rules:\n"
            
            if not sg.get('IpPermissions'):
                result += "    (Không có rule - chặn toàn bộ inbound)\n"
            
            for rule in sg.get('IpPermissions', []):
                proto = rule.get('IpProtocol', 'N/A')
                from_p = rule.get('FromPort', 'All')
                to_p = rule.get('ToPort', 'All')
                cidrs = [ip.get('CidrIp', '') for ip in rule.get('IpRanges', [])]
                cidrs += [ip.get('CidrIpv6', '') for ip in rule.get('Ipv6Ranges', [])]
                cidr_str = ", ".join(cidrs) if cidrs else "N/A"
                
                warning = ""
                if '0.0.0.0/0' in cidrs or '::/0' in cidrs:
                    if proto == '-1':
                        warning = " | NGUY HIỂM: Mở toàn bộ traffic public!"
                    elif from_p in SENSITIVE_PORTS:
                        warning = f" | RỦI RO: {SENSITIVE_PORTS[from_p]} mở public!"
                
                port_display = "All" if proto == '-1' else f"{from_p}-{to_p}" if from_p != to_p else str(from_p)
                result += f"    Port {port_display} | Protocol: {proto} | Source: {cidr_str}{warning}\n"
            result += "\n"
        return result
    except Exception as e:
        return f"Lỗi khi lấy Security Groups: {str(e)}"