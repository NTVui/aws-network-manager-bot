"""Tools phân tích chi phí và tối ưu hóa."""
from datetime import datetime, timedelta
from langchain_core.tools import tool
from src.config import get_aws_client, USD_TO_VND, PRICING


@tool
def get_actual_cost(days_back: int = 7) -> str:
    """
    Lấy chi phí AWS THỰC TẾ trong N ngày qua từ Cost Explorer API.
    Khác với ước tính - đây là số tiền thực sự bị tính phí.
    Args: days_back - Số ngày muốn xem (mặc định 7).
    """
    try:
        ce = get_aws_client('ce')  # Cost Explorer client
        
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Lấy chi phí theo service
        response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )
        
        # Tổng hợp theo service
        service_costs = {}
        total_cost = 0
        
        for result in response['ResultsByTime']:
            for group in result['Groups']:
                service = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                service_costs[service] = service_costs.get(service, 0) + cost
                total_cost += cost
        
        # Sắp xếp theo chi phí giảm dần
        sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)
        
        output = f"CHI PHÍ AWS THỰC TẾ ({days_back} NGÀY QUA)\n"
        output += f"Từ: {start_date} đến {end_date}\n\n"
        output += f"TỔNG CHI PHÍ: ${total_cost:.4f} USD"
        output += f" (~ {total_cost * USD_TO_VND:,.0f} VNĐ)\n\n"
        
        output += "CHI TIẾT THEO DỊCH VỤ:\n"
        for service, cost in sorted_services[:10]:  # Top 10
            if cost > 0:
                pct = (cost / total_cost * 100) if total_cost > 0 else 0
                output += f"  - {service}: ${cost:.4f} ({pct:.1f}%)\n"
        
        # Dự đoán tháng
        if days_back > 0:
            daily_avg = total_cost / days_back
            monthly_estimate = daily_avg * 30
            output += f"\nDỰ ĐOÁN CHI PHÍ THÁNG:\n"
            output += f"  Trung bình/ngày: ${daily_avg:.4f}\n"
            output += f"  Ước tính tháng: ${monthly_estimate:.2f} (~{monthly_estimate * USD_TO_VND:,.0f} VNĐ)\n"
        
        return output
    except Exception as e:
        if "AccessDenied" in str(e):
            return "Lỗi: Tài khoản IAM cần quyền 'ce:GetCostAndUsage' để xem Cost Explorer."
        return f"Lỗi khi lấy dữ liệu chi phí: {str(e)}"


@tool
def recommend_instance_optimization(instance_id: str) -> str:
    """
    Phân tích CPU history của một EC2 và đưa ra gợi ý tối ưu:
    - Nếu CPU < 20%: gợi ý hạ cấp (downsize) để tiết kiệm.
    - Nếu CPU > 80%: gợi ý nâng cấp (upsize) để tăng hiệu năng.
    - Nếu 20-80%: cấu hình hiện tại đang tối ưu.
    Args: instance_id - ID của máy cần phân tích.
    """
    try:
        ec2 = get_aws_client('ec2')
        cloudwatch = get_aws_client('cloudwatch')
        
        # Lấy thông tin instance
        inst_response = ec2.describe_instances(InstanceIds=[instance_id])
        if not inst_response['Reservations']:
            return f"Không tìm thấy máy {instance_id}."
        
        instance = inst_response['Reservations'][0]['Instances'][0]
        current_type = instance['InstanceType']
        current_price = PRICING.get(current_type, 0)
        
        # Lấy CPU 7 ngày qua
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)
        
        cpu_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,  # 1 giờ
            Statistics=['Average', 'Maximum']
        )
        
        datapoints = cpu_response.get('Datapoints', [])
        if not datapoints:
            return f"Chưa đủ dữ liệu CPU cho máy {instance_id}. Cần ít nhất vài giờ chạy."
        
        avg_cpu = sum(d['Average'] for d in datapoints) / len(datapoints)
        max_cpu = max(d['Maximum'] for d in datapoints)
        
        # Logic recommendation
        output = f"PHÂN TÍCH TỐI ƯU MÁY {instance_id}\n\n"
        output += f"Cấu hình hiện tại: {current_type} (${current_price}/giờ)\n"
        output += f"CPU trung bình 7 ngày: {avg_cpu:.2f}%\n"
        output += f"CPU đỉnh điểm: {max_cpu:.2f}%\n\n"
        
        # Đề xuất downsize/upsize
        downsize_map = {
            "c7i-flex.large": "t3.micro",
            "m7i-flex.large": "t3.micro",
            "i3.large": "c7i-flex.large",
        }
        upsize_map = {
            "t3.micro": "c7i-flex.large",
            "c7i-flex.large": "m7i-flex.large",
            "m7i-flex.large": "i3.large",
        }
        
        if avg_cpu < 20 and max_cpu < 50:
            output += "KHUYẾN NGHỊ: HẠ CẤP (Downsize)\n"
            output += f"Lý do: CPU trung bình chỉ {avg_cpu:.1f}% - máy đang quá dư thừa.\n"
            
            if current_type in downsize_map:
                new_type = downsize_map[current_type]
                new_price = PRICING.get(new_type, 0)
                saving = (current_price - new_price) * 24 * 30
                output += f"Đề xuất chuyển sang: {new_type} (${new_price}/giờ)\n"
                output += f"Tiết kiệm ước tính: ${saving:.2f}/tháng (~{saving * USD_TO_VND:,.0f} VNĐ)\n"
            else:
                output += "Đã ở cấu hình thấp nhất, không thể hạ thêm.\n"
        
        elif avg_cpu > 80 or max_cpu > 95:
            output += "KHUYẾN NGHỊ: NÂNG CẤP (Upsize)\n"
            output += f"Lý do: CPU trung bình {avg_cpu:.1f}%, đỉnh {max_cpu:.1f}% - máy đang quá tải.\n"
            
            if current_type in upsize_map:
                new_type = upsize_map[current_type]
                new_price = PRICING.get(new_type, 0)
                extra_cost = (new_price - current_price) * 24 * 30
                output += f"Đề xuất chuyển sang: {new_type} (${new_price}/giờ)\n"
                output += f"Chi phí tăng thêm: ${extra_cost:.2f}/tháng\n"
            else:
                output += "Đã ở cấu hình cao nhất, cân nhắc dùng Auto Scaling.\n"
        
        else:
            output += "KHUYẾN NGHỊ: GIỮ NGUYÊN (Optimal)\n"
            output += f"Cấu hình hiện tại đang tối ưu cho workload của bạn.\n"
            output += f"CPU trong khoảng 20-80% là vùng hoạt động hiệu quả nhất.\n"
        
        return output
    except Exception as e:
        return f"Lỗi khi phân tích: {str(e)}"