"""Analytics helper - tính toán metrics cho Dashboard."""
from src.config import PRICING, USD_TO_VND


def calculate_infrastructure_metrics(ec2_data, security_groups=None, subnets=None, route_tables=None):
    """
    Tính toán các metric tổng quan của hạ tầng.
    
    Returns dict gồm:
        - total_instances, running_count, stopped_count
        - monthly_cost_usd, monthly_cost_vnd
        - potential_savings_usd
        - cost_per_instance: list dict cho pie chart
        - public_subnet_count, private_subnet_count
        - security_issues_count
        - health_score: dict {total, security, cost, performance}
    """
    metrics = {
        # Phần 1: Số lượng máy
        "total_instances": 0,
        "running_count": 0,
        "stopped_count": 0,
        
        # Phần 2: Chi phí
        "monthly_cost_usd": 0,
        "monthly_cost_vnd": 0,
        "potential_savings_usd": 0,
        "cost_per_instance": [],
        
        # Phần 3: Mạng
        "public_subnet_count": 0,
        "private_subnet_count": 0,
        
        # Phần 4: Bảo mật
        "security_issues_count": 0,
        "security_issues_detail": [],
        
        # Phần 5: Health Score
        "health_score": {
            "total": 0,
            "security": 0,
            "cost": 0,
            "performance": 0
        }
    }
    
    # === Phần 1 & 2: Đếm máy + tính chi phí ===
    total_running_cost = 0
    total_stopped_cost = 0  # Máy stopped nhưng vẫn tốn EBS
    
    for res in ec2_data.get('Reservations', []):
        for inst in res['Instances']:
            state = inst['State']['Name']
            if state == 'terminated':
                continue
            
            metrics["total_instances"] += 1
            it_type = inst['InstanceType']
            hourly_price = PRICING.get(it_type, 0)
            monthly = hourly_price * 24 * 30
            
            inst_name = next(
                (t['Value'] for t in inst.get('Tags', []) if t['Key'] == 'Name'),
                inst['InstanceId'][-6:]
            )
            
            if state == 'running':
                metrics["running_count"] += 1
                total_running_cost += monthly
                metrics["cost_per_instance"].append({
                    "name": inst_name,
                    "type": it_type,
                    "monthly_cost": round(monthly, 2)
                })
            elif state in ('stopped', 'stopping'):
                metrics["stopped_count"] += 1
                total_stopped_cost += monthly
    
    # Tổng chi phí dự kiến (chỉ tính máy running)
    metrics["monthly_cost_usd"] = round(total_running_cost, 2)
    metrics["monthly_cost_vnd"] = total_running_cost * USD_TO_VND
    
    # Tiết kiệm tiềm năng = chi phí của máy đã stop (nếu xóa hẳn)
    metrics["potential_savings_usd"] = round(total_stopped_cost, 2)
    
    # === Phần 3: Phân loại Subnets ===
    if subnets and route_tables:
        public_subnet_ids = set()
        for rt in route_tables:
            if any(r.get('GatewayId', '').startswith('igw-') for r in rt.get('Routes', [])):
                for assoc in rt.get('Associations', []):
                    if assoc.get('SubnetId'):
                        public_subnet_ids.add(assoc['SubnetId'])
        
        for subnet in subnets:
            if subnet['SubnetId'] in public_subnet_ids:
                metrics["public_subnet_count"] += 1
            else:
                metrics["private_subnet_count"] += 1
    
    # === Phần 4: Audit Security Groups (CHI TIẾT) ===
    if security_groups:
        SENSITIVE_PORTS = {
            22: "SSH (quản trị Linux)",
            3389: "RDP (quản trị Windows)",
            3306: "MySQL Database",
            5432: "PostgreSQL Database",
            27017: "MongoDB",
            6379: "Redis",
            21: "FTP (không mã hóa)",
            23: "Telnet (không mã hóa)"
        }
        
        for sg in security_groups:
            sg_name = sg.get('GroupName', 'unnamed')
            sg_id = sg.get('GroupId', 'N/A')
            
            for rule in sg.get('IpPermissions', []):
                from_port = rule.get('FromPort')
                to_port = rule.get('ToPort')
                protocol = rule.get('IpProtocol', '')
                
                is_public = any(
                    ip.get('CidrIp') == '0.0.0.0/0' 
                    for ip in rule.get('IpRanges', [])
                ) or any(
                    ip.get('CidrIpv6') == '::/0' 
                    for ip in rule.get('Ipv6Ranges', [])
                )
                
                if not is_public:
                    continue
                
                # Phân loại issue với mức độ nguy hiểm
                if protocol == '-1':
                    metrics["security_issues_count"] += 1
                    metrics["security_issues_detail"].append({
                        "severity": "CRITICAL",
                        "sg_name": sg_name,
                        "sg_id": sg_id,
                        "port": "ALL",
                        "issue": "Mở TẤT CẢ traffic ra Internet",
                        "risk": "Cực kỳ nguy hiểm - hacker có thể truy cập mọi cổng",
                        "fix": "Xóa rule này ngay hoặc giới hạn CIDR về IP công ty"
                    })
                elif from_port in SENSITIVE_PORTS:
                    severity = "HIGH" if from_port in (22, 3389) else "MEDIUM"
                    metrics["security_issues_count"] += 1
                    metrics["security_issues_detail"].append({
                        "severity": severity,
                        "sg_name": sg_name,
                        "sg_id": sg_id,
                        "port": str(from_port),
                        "issue": f"Cổng {from_port} - {SENSITIVE_PORTS[from_port]} mở public",
                        "risk": f"Hacker có thể brute-force {SENSITIVE_PORTS[from_port].split('(')[0].strip()}",
                        "fix": f"Giới hạn CIDR hoặc dùng AWS SSM Session Manager"
                    })
                elif from_port is not None and to_port is not None and (to_port - from_port) > 100:
                    metrics["security_issues_count"] += 1
                    metrics["security_issues_detail"].append({
                        "severity": "MEDIUM",
                        "sg_name": sg_name,
                        "sg_id": sg_id,
                        "port": f"{from_port}-{to_port}",
                        "issue": f"Mở dải cổng rộng {from_port}-{to_port}",
                        "risk": "Có thể chứa nhiều cổng nhạy cảm",
                        "fix": "Chỉ mở các cổng cụ thể cần dùng"
                    })
    
   # === Phần 5: Tính Health Score (CHI TIẾT) ===
    # Security score (40%): trừ điểm theo mức độ nguy hiểm
    sec_score = 100
    sec_breakdown = []
    
    for issue in metrics["security_issues_detail"]:
        if issue["severity"] == "CRITICAL":
            penalty = 25
        elif issue["severity"] == "HIGH":
            penalty = 15
        else:  # MEDIUM
            penalty = 10
        sec_score -= penalty
        sec_breakdown.append(f"-{penalty}đ: {issue['issue']} ({issue['sg_name']})")
    
    sec_score = max(0, sec_score)
    
    # Cost score (30%) - giải thích lý do
    cost_breakdown = []
    if metrics["total_instances"] > 0:
        wasted_ratio = metrics["stopped_count"] / metrics["total_instances"]
        cost_score = max(0, 100 - int(wasted_ratio * 100))
        if metrics["stopped_count"] > 0:
            cost_breakdown.append(
                f"-{int(wasted_ratio * 100)}đ: Có {metrics['stopped_count']}/{metrics['total_instances']} máy đang stopped (lãng phí EBS)"
            )
        else:
            cost_breakdown.append("Không có máy lãng phí")
    else:
        cost_score = 100
        cost_breakdown.append("Chưa có máy nào")
    
    # Performance score (30%) - giải thích lý do
    perf_breakdown = []
    if metrics["running_count"] > 0:
        penalty = min(metrics["stopped_count"] * 10, 50)
        perf_score = 100 - penalty
        if metrics["stopped_count"] > 0:
            perf_breakdown.append(f"-{penalty}đ: {metrics['stopped_count']} máy stopped làm giảm khả năng phục vụ")
        else:
            perf_breakdown.append("Tất cả máy đang chạy")
    else:
        perf_score = 50
        perf_breakdown.append("-50đ: Không có máy nào đang chạy")
    
    total_score = int(sec_score * 0.4 + cost_score * 0.3 + perf_score * 0.3)
    
    metrics["health_score"] = {
        "total": total_score,
        "security": sec_score,
        "cost": cost_score,
        "performance": perf_score,
        # THÊM PHẦN BREAKDOWN
        "security_breakdown": sec_breakdown,
        "cost_breakdown": cost_breakdown,
        "performance_breakdown": perf_breakdown
    }
    
    return metrics


def get_health_grade(score):
    """Chuyển score 0-100 thành grade chữ."""
    if score >= 90:
        return "A", "Xuất sắc", "#10B981"  # Xanh lá
    elif score >= 75:
        return "B", "Tốt", "#3B82F6"  # Xanh dương
    elif score >= 60:
        return "C", "Khá", "#F59E0B"  # Vàng
    elif score >= 40:
        return "D", "Cần cải thiện", "#F97316"  # Cam
    else:
        return "F", "Yếu", "#EF4444"  # Đỏ