import streamlit as st
import boto3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from src.utils.analytics import calculate_infrastructure_metrics, get_health_grade
from src.config import PRICING
import os
from src.agent_logic import (
    ask_ai, get_cost_estimate, get_cpu_history_data,
    create_ec2_instance, get_network_topology_raw, build_mermaid_diagram,
    run_stress_test, check_stress_test_result
)
from src.styles import apply_custom_style

# Page config
st.set_page_config(
    page_title="AWS DevOps Console",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS
apply_custom_style()

REGION = "us-east-1"
ec2_client = boto3.client(
    'ec2',
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

# === HEADER (clean, không icon) ===
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.markdown("# AWS DevOps Console")
    st.caption(f"AI Agent vận hành hạ tầng AWS · Region: {REGION}")
with header_col2:
    st.markdown(
        f"""
        <div style="text-align: right; padding-top: 1rem;">
            <span class="status-badge status-running">Connected</span>
        </div>
        """, 
        unsafe_allow_html=True
    )

st.markdown("---")

with st.sidebar:
    st.markdown("### Navigation")

    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("Dashboard", use_container_width=True):
            st.session_state["active_view"] = "dashboard"
    with nav_col2:
        if st.button("Tạo EC2", use_container_width=True):
            st.session_state["active_view"] = "create_ec2"
            st.session_state.pop("selected_ec2_type", None)

    nav_col3, nav_col4 = st.columns(2)
    with nav_col3:
        if st.button("Network", use_container_width=True):
            st.session_state["active_view"] = "network"
    with nav_col4:
        if st.button("Chi phí", use_container_width=True):
            st.session_state["active_view"] = "cost"

    st.markdown("---")
    st.markdown("### Hệ thống")

    selected_id = None
    ec2_data = None
    try:
        ec2_data = ec2_client.describe_instances()
        instance_options = []
        for res in ec2_data['Reservations']:
            for inst in res['Instances']:
                if inst['State']['Name'] != 'terminated':
                    name = next((t['Value'] for t in inst.get('Tags', []) if t['Key'] == 'Name'), inst['InstanceId'])
                    instance_options.append(f"{name} ({inst['InstanceId']})")

        selected_option = st.selectbox(
            "Instance được chọn",
            instance_options if instance_options else ["Không có máy"],
            label_visibility="visible"
        )
        selected_id = selected_option.split("(")[-1].replace(")", "") if "(" in selected_option else None

    except Exception as e:
        st.error(f"Lỗi kết nối AWS: {e}")

    # Model info
    st.caption("Model AI: Llama 3.1 (Groq)")

    # Điều khiển instance
    if selected_id:
        st.markdown("---")
        st.markdown("### Điều khiển")

        btn_start, btn_stop = st.columns(2)
        with btn_start:
            if st.button("Start", use_container_width=True):
                try:
                    ec2_client.start_instances(InstanceIds=[selected_id])
                    st.success(f"Đã bật {selected_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")
        with btn_stop:
            if st.button("Stop", use_container_width=True):
                try:
                    ec2_client.stop_instances(InstanceIds=[selected_id])
                    st.warning(f"Đã tắt {selected_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")

        st.markdown("---")
        confirm_delete = st.checkbox("Xác nhận xóa máy này")

        if st.button(
            "Terminate Instance",
            use_container_width=True,
            type="primary",
            disabled=not confirm_delete
        ):
            with st.spinner(f"Đang xóa {selected_id}..."):
                try:
                    ec2_client.terminate_instances(InstanceIds=[selected_id])
                    st.success(f"Đã xóa {selected_id}")
                    import time
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    st.markdown("---")
    if st.button("Refresh", use_container_width=True):
        st.rerun()

# 3. Phát hiện thay đổi trạng thái EC2 và thông báo
if ec2_data:
    current_states = {
        inst['InstanceId']: inst['State']['Name']
        for res in ec2_data['Reservations']
        for inst in res['Instances']
        if inst['State']['Name'] != 'terminated'
    }
    prev_states = st.session_state.get("ec2_states", {})

    changed = {
        iid: (prev_states[iid], current_states[iid])
        for iid in current_states
        if iid in prev_states and prev_states[iid] != current_states[iid]
    }
    if changed:
        for iid, (old, new) in changed.items():
            st.toast(f"Instance {iid}: {old} → {new}", icon="🔔")

    st.session_state["ec2_states"] = current_states

# 4. Điều hướng nội dung chính
active_view = st.session_state.get("active_view", "dashboard")

if active_view == "create_ec2":
    st.markdown("## Khởi tạo EC2 Instance")
    st.caption("Chọn cấu hình phù hợp với workload của bạn")
    
    new_server_name = st.text_input(
        "Tên máy chủ", 
        placeholder="Ví dụ: web-server-01",
        key="new_ec2_name"
    )
    
    st.markdown("---")
    st.markdown("**Cấu hình đề xuất**")

    recommendations = {
        "web":     {"type": "t3.micro",       "price": 0.0104,  "label": "🌐 Web Server Cơ bản",              "desc": "2 vCPU, 1GB RAM",                      "free_tier": True},
        "compute": {"type": "c7i-flex.large",  "price": 0.08479, "label": "⚡ Tính toán Mạnh (Media/HPC)",     "desc": "2 vCPU, 4GB RAM",                      "free_tier": True},
        "memory":  {"type": "m7i-flex.large",  "price": 0.09576, "label": "💾 Bộ nhớ Lớn (Database/Cache)",   "desc": "2 vCPU, 8GB RAM",                      "free_tier": True},
        "storage": {"type": "i3.large",        "price": 0.156,   "label": "📦 Lưu trữ Tốc độ Cao",            "desc": "2 vCPU, 15.25GB RAM, 475GB NVMe",      "free_tier": False},
    }

    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    card_cols = {"web": col1, "compute": col2, "memory": col3, "storage": col4}

    for key, data in recommendations.items():
        with card_cols[key]:
            with st.container(border=True):
                st.markdown(f"**{data['label']}**")
                st.caption(f"{data['type']} · {data['desc']}")
                
                hourly_usd = data["price"]
                monthly_usd = round(hourly_usd * 24 * 30, 2)
                monthly_vnd = "{:,.0f}".format(monthly_usd * 25400)
                
                st.markdown(f"**${hourly_usd}/giờ**")
                st.caption(f"~${monthly_usd}/tháng ({monthly_vnd} VNĐ)")
                
                # Free tier badge
                if data["free_tier"]:
                    st.markdown(
                        '<span class="status-badge status-running">FREE TIER</span>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        '<span class="status-badge status-pending">ON-DEMAND</span>',
                        unsafe_allow_html=True
                    )
                
                st.markdown("")  # spacing
                
                if st.button(f"Tạo {data['type']}", key=f"create_{key}", use_container_width=True):
                    if not new_server_name:
                        st.error("Vui lòng nhập tên máy chủ.")
                    else:
                        with st.spinner("Đang tạo instance..."):
                            result = create_ec2_instance.invoke({
                                "instance_type": data["type"],
                                "instance_name": new_server_name
                            })
                        if result.startswith("✅"):
                            st.success(result)
                            st.session_state["active_view"] = "dashboard"
                            st.rerun()
                        else:
                            st.error(result)

    st.markdown("---")
    st.caption("Chi tiết hơn tại: [AWS Instance Types Official Docs](https://aws.amazon.com/ec2/instance-types/)")
elif active_view == "network":
    st.markdown("## Sơ đồ Hạ tầng Mạng")
    st.caption("Mô hình kiến trúc theo AWS Well-Architected Framework")
    
    with st.spinner("Đang tải dữ liệu mạng từ AWS..."):
        topology = get_network_topology_raw()
    
    if "error" in topology:
        st.error(f"Lỗi: {topology['error']}")
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["Sơ đồ", "Cách đọc sơ đồ", "Chi tiết", "Phân tích"])
        
        with tab1:
            col_opt1, col_opt2 = st.columns([1, 3])
            with col_opt1:
                hide_default = st.checkbox(
                    "Ẩn Default VPC", 
                    value=True,
                    help="AWS tự tạo sẵn 1 VPC mặc định. Ẩn để xem rõ VPC bạn tự thiết kế."
                )
            
            st.markdown("### Sơ đồ kiến trúc mạng")
            # Chú thích màu sắc
            with st.container(border=True):
                st.markdown("**🎯 Cách đọc sơ đồ:**")
                leg1, leg2, leg3, leg4 = st.columns(4)
                with leg1:
                    st.markdown("🟦 **Internet**\nMạng công cộng")
                with leg2:
                    st.markdown("🟧 **Cổng Internet (IGW)**\nCửa ra vào mạng")
                with leg3:
                    st.markdown("🟨 **Mạng công khai**\nCó IP public, ai cũng truy cập được")
                with leg4:
                    st.markdown("🟩 **Mạng nội bộ**\nChỉ truy cập từ bên trong VPC")
            
            mermaid_code = build_mermaid_diagram(topology, hide_default_vpc=hide_default)
            
            # Render với kích thước RẤT LỚN
            html_code = f"""
            <div style="background: #FFFFFF; padding: 30px; border: 2px solid #DDD; border-radius: 8px; min-height: 900px;">
                <div class="mermaid" style="text-align: center;">
    {mermaid_code}
                </div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({{
                    startOnLoad: true,
                    theme: 'base',
                    flowchart: {{
                        useMaxWidth: false,
                        htmlLabels: true,
                        curve: 'linear',
                        nodeSpacing: 80,
                        rankSpacing: 120,
                        padding: 30
                    }},
                    themeVariables: {{
                        fontSize: '16px',
                        fontFamily: 'Arial, Helvetica, sans-serif',
                        primaryColor: '#FFFFFF',
                        primaryBorderColor: '#000000',
                        lineColor: '#000000'
                    }}
                }});
            </script>
            """
            st.components.v1.html(html_code, height=1000, scrolling=True)
            
            with st.expander("Xem code Mermaid (copy vào báo cáo)"):
                st.code(mermaid_code, language="mermaid")
                st.caption("Mẹo: Paste code vào https://mermaid.live để xuất ảnh PNG/SVG độ phân giải cao.")
        
        with tab2:
            st.markdown("""
            ## Cách đọc sơ đồ mạng AWS
            
            Để hiểu sơ đồ này, hãy ghi nhớ **mô hình tòa nhà văn phòng** sau đây:
            
            ---
            
            ### 1. INTERNET - Đường phố công cộng
            
            Là mạng Internet toàn cầu mà ai cũng truy cập được. Trong sơ đồ, đây là 
            điểm bắt đầu (trên cùng). Mọi traffic từ bên ngoài muốn vào hệ thống của 
            bạn đều phải đi qua đây.
            
            ---
            
            ### 2. VPC (Virtual Private Cloud) - Tòa nhà riêng
            
            VPC là **không gian mạng riêng** mà bạn thuê của AWS. Hãy xem nó như một 
            **tòa nhà** mà bạn thuê nguyên căn:
            - Có địa chỉ riêng (dải IP CIDR, ví dụ 10.0.0.0/16)
            - Có rào chắn cô lập với các VPC khác
            - Bạn toàn quyền thiết kế bên trong
            
            **Ghi nhớ:** *Một VPC chỉ tồn tại trong một Region. Muốn mở rộng sang 
            region khác phải tạo VPC mới.*
            
            ---
            
            ### 3. INTERNET GATEWAY (IGW) - Cổng chính tòa nhà
            
            Là **cánh cửa duy nhất** kết nối VPC với Internet. Vai trò:
            - Cho phép traffic từ Internet đi vào VPC (inbound)
            - Cho phép traffic từ VPC ra Internet (outbound)
            - Mỗi VPC chỉ gắn được tối đa 1 IGW
            
            **Ghi nhớ:** *Không có IGW = VPC bị cô lập hoàn toàn với thế giới bên ngoài.*
            
            ---
            
            ### 4. PUBLIC SUBNET - Phòng tiếp khách
            
            Là **các phòng có cửa sổ hướng ra đường** trong tòa nhà:
            - Máy chủ trong đây có IP public
            - Ai trên Internet cũng truy cập được (nếu Security Group cho phép)
            - **Đặt ở đây:** Web Server, Load Balancer, Bastion Host
            
            **Đặc điểm kỹ thuật:** Route Table có route 0.0.0.0/0 trỏ đến IGW.
            
            ---
            
            ### 5. PRIVATE SUBNET - Phòng kho/phòng riêng
            
            Là **các phòng kín bên trong** tòa nhà, không có cửa sổ ra đường:
            - Máy chủ trong đây không có IP public
            - Không truy cập trực tiếp được từ Internet
            - **Đặt ở đây:** Database, Internal API, Backend Service
            
            **Đặc điểm kỹ thuật:** Route Table KHÔNG có route đến IGW. Muốn ra 
            Internet phải qua NAT Gateway.
            
            ---
            
            ### 6. EC2 INSTANCE - Nhân viên trong phòng
            
            Là các **máy chủ ảo** đang chạy bên trong subnet. Mỗi máy đảm nhận 
            một vai trò cụ thể (web, database, app, ...).
            
            ---
            
            ## Quy tắc vàng cần nhớ (theo SAA-C03):
            
            **Quy tắc 1:** Public Subnet là subnet có route đến IGW. 
            Private Subnet là subnet KHÔNG có route đến IGW.
            
            **Quy tắc 2:** Để hệ thống chống chịu lỗi (High Availability), 
            phải tạo subnet ở ít nhất 2 Availability Zone khác nhau.
            
            **Quy tắc 3:** Web Server đặt ở Public Subnet. Database đặt ở 
            Private Subnet. Đây là mô hình bảo mật chuẩn (Defense in Depth).
            
            **Quy tắc 4:** Một Subnet chỉ thuộc về một Availability Zone duy nhất. 
            Không có chuyện 1 subnet trải qua 2 AZ.
            
            **Quy tắc 5:** NAT Gateway dùng cho Private Subnet ra Internet 
            (ví dụ: tải update phần mềm) nhưng không cho phép Internet đi vào.
            """)
        
        with tab3:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**VPCs ({len(topology['vpcs'])})**")
                for vpc in topology['vpcs']:
                    name = next((t['Value'] for t in vpc.get('Tags', []) if t['Key'] == 'Name'), 'unnamed')
                    badge = " - Default" if vpc.get('IsDefault') else " - Custom"
                    st.info(f"**{name}**{badge}\n\n`{vpc['VpcId']}`\n\nCIDR: `{vpc['CidrBlock']}`")
                
                st.write(f"**Internet Gateways ({len(topology['igws'])})**")
                for igw in topology['igws']:
                    vpc_attached = igw['Attachments'][0]['VpcId'] if igw.get('Attachments') else 'Detached'
                    st.success(f"`{igw['InternetGatewayId']}` → VPC: `{vpc_attached}`")
            
            with col2:
                st.write(f"**Subnets ({len(topology['subnets'])})**")
                public_ids = set()
                for rt in topology['route_tables']:
                    if any(r.get('GatewayId', '').startswith('igw-') for r in rt.get('Routes', [])):
                        for assoc in rt.get('Associations', []):
                            if assoc.get('SubnetId'):
                                public_ids.add(assoc['SubnetId'])
                
                for subnet in topology['subnets']:
                    name = next((t['Value'] for t in subnet.get('Tags', []) if t['Key'] == 'Name'), 'unnamed')
                    is_public = subnet['SubnetId'] in public_ids
                    badge = "Public" if is_public else "Private"
                    st.info(
                        f"**{name}** - {badge}\n\n"
                        f"`{subnet['SubnetId']}`\n\n"
                        f"CIDR: `{subnet['CidrBlock']}` | AZ: `{subnet['AvailabilityZone']}`"
                    )
        
        with tab4:
            st.write("**Phân tích Hạ tầng:**")
            
            total_vpcs = len(topology['vpcs'])
            total_subnets = len(topology['subnets'])
            active_nats = len([n for n in topology['nat_gws'] if n['State'] == 'available'])
            custom_vpcs = len([v for v in topology['vpcs'] if not v.get('IsDefault')])
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tổng VPCs", total_vpcs, f"{custom_vpcs} Custom")
            m2.metric("Subnets", total_subnets)
            m3.metric("Internet GWs", len(topology['igws']))
            m4.metric("NAT GWs", active_nats)
            
            st.markdown("---")
            st.write("**Khuyến nghị:**")
            
            if any(v.get('IsDefault') for v in topology['vpcs']):
                st.warning("Bạn đang dùng Default VPC. Production nên tạo Custom VPC riêng để kiểm soát mạng tốt hơn.")
            
            if active_nats == 0:
                st.warning("Không có NAT Gateway. Private Subnet sẽ không có internet outbound.")
            else:
                st.info(f"Đang có {active_nats} NAT Gateway hoạt động (~$32/tháng/NAT). Cân nhắc tắt nếu không dùng.")
            
            if len(topology['igws']) > 0:
                st.success("Internet Gateway đã được cấu hình.")

elif active_view == "cost":
    st.markdown("## Phân tích Chi phí")
    st.caption("Theo dõi chi phí thực tế và đề xuất tối ưu")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        days = st.selectbox("Khoảng thời gian:", [7, 14, 30], index=0)
    
    if st.button("Tải dữ liệu chi phí"):
        from src.tools.cost_tools import get_actual_cost
        with st.spinner("Đang lấy dữ liệu từ AWS Cost Explorer..."):
            result = get_actual_cost.invoke({"days_back": days})
            st.text(result)
    
    st.markdown("---")
    st.write("**Phân tích tối ưu cho từng máy:**")
    
    if selected_id:
        if st.button(f"Phân tích máy {selected_id}"):
            from src.tools.cost_tools import recommend_instance_optimization
            with st.spinner("AI đang phân tích..."):
                result = recommend_instance_optimization.invoke({"instance_id": selected_id})
                st.text(result)
    else:
        st.info("Chọn máy ở sidebar để phân tích.")

else:  # active_view == "dashboard"
    # Lấy thêm data cho analytics
    try:
        sg_data = ec2_client.describe_security_groups()['SecurityGroups']
        subnets_data = ec2_client.describe_subnets()['Subnets']
        rt_data = ec2_client.describe_route_tables()['RouteTables']
    except Exception:
        sg_data, subnets_data, rt_data = [], [], []
    
    # Tính metrics
    metrics = calculate_infrastructure_metrics(
        ec2_data, 
        security_groups=sg_data,
        subnets=subnets_data,
        route_tables=rt_data
    )
    # === CHATBOT SECTION ===
    st.markdown('<div class="section-header">Trợ lý DevOps</div>', unsafe_allow_html=True)

    with st.container(border=True):
        user_input = st.text_input(
            "Câu hỏi:", 
            placeholder="Ví dụ: Kiểm tra bảo mật hệ thống, hoặc Máy may1 đang ở VPC nào?",
            label_visibility="collapsed"
        )

    if user_input:
        with st.spinner("Đang xử lý..."):
            ai_response = ask_ai(user_input)
            with st.container(border=True):
                st.markdown("**Trả lời:**")
                st.write(ai_response)

    # === MONITORING SECTION ===
    st.markdown('<div class="section-header">Giám sát tài nguyên</div>', unsafe_allow_html=True)
    st.caption(f"Real-time monitoring · Instance: {selected_id if selected_id else 'Chưa chọn'}")

    mon_col1, mon_col2 = st.columns([2, 1])

    with mon_col1:
        st.markdown("**CPU Utilization (1 giờ qua)**")
        if selected_id:
            cpu_history = get_cpu_history_data(selected_id)
            if cpu_history:
                # Vẽ Plotly chart đẹp hơn
                fig_cpu = go.Figure()
                fig_cpu.add_trace(go.Scatter(
                    y=cpu_history,
                    mode='lines+markers',
                    line=dict(color='#1E40AF', width=2),
                    marker=dict(size=6, color='#1E40AF'),
                    fill='tozeroy',
                    fillcolor='rgba(30, 64, 175, 0.1)',
                    hovertemplate='CPU: %{y:.2f}%<extra></extra>'
                ))
                fig_cpu.update_layout(
                    height=280,
                    margin=dict(t=10, b=30, l=40, r=10),
                    xaxis=dict(
                        title="Thời gian (5 phút/điểm)",
                        showgrid=True,
                        gridcolor='#F1F5F9'
                    ),
                    yaxis=dict(
                        title="CPU (%)",
                        showgrid=True,
                        gridcolor='#F1F5F9',
                        range=[0, max(max(cpu_history) * 1.2, 10)]
                    ),
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font=dict(family='Inter', size=12, color='#334155')
                )
                st.plotly_chart(fig_cpu, use_container_width=True)
            else:
                st.info("Đang đợi dữ liệu CloudWatch (cần ~5 phút sau khi máy bật).")
        else:
            st.info("Chọn máy chủ ở sidebar để xem dữ liệu.")

    # Lấy trạng thái instance
    current_status = "N/A"
    current_type = "N/A"
    if selected_id and ec2_data:
        for res in ec2_data['Reservations']:
            for inst in res['Instances']:
                if inst['InstanceId'] == selected_id:
                    current_status = inst['State']['Name']
                    current_type = inst['InstanceType']

    with mon_col2:
        st.markdown("**Thông tin Instance**")
        if selected_id:
            # Status badge
            status_class = "status-running" if current_status == "running" else "status-stopped"
            st.markdown(
                f'<span class="status-badge {status_class}">{current_status.upper()}</span>',
                unsafe_allow_html=True
            )
            st.markdown("")
            
            # Info table
            st.markdown(f"**Instance ID:** `{selected_id}`")
            st.markdown(f"**Loại:** `{current_type}`")
            
            from src.config import PRICING
            if current_type in PRICING:
                hourly = PRICING[current_type]
                monthly = hourly * 24 * 30
                st.markdown(f"**Giá/giờ:** ${hourly}")
                st.markdown(f"**Giá/tháng:** ${monthly:.2f}")
        else:
            st.caption("Chưa có thông tin")
    # ============== DASHBOARD ANALYTICS ==============
    st.markdown("---")
    st.subheader("📊 Tổng quan Hạ tầng")

    # === SECTION 1: 4 Metric Cards ===
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric(
            label="Tổng số máy chủ",
            value=metrics["total_instances"],
            delta=f"{metrics['running_count']} đang chạy",
            delta_color="normal"
        )

    with m2:
        cost_vnd_formatted = "{:,.0f}".format(metrics["monthly_cost_vnd"])
        st.metric(
            label="Chi phí dự kiến/tháng",
            value=f"${metrics['monthly_cost_usd']}",
            delta=f"{cost_vnd_formatted} VNĐ",
            delta_color="off"
        )

    with m3:
        saving_vnd = metrics["potential_savings_usd"] * 25400
        st.metric(
            label="Tiềm năng tiết kiệm",
            value=f"${metrics['potential_savings_usd']}",
            delta=f"{metrics['stopped_count']} máy đang dừng",
            delta_color="inverse"
        )

    with m4:
        sg_status = "An toàn" if metrics["security_issues_count"] == 0 else f"{metrics['security_issues_count']} rủi ro"
        st.metric(
            label="Trạng thái bảo mật",
            value=sg_status,
            delta="Cần kiểm tra" if metrics["security_issues_count"] > 0 else "OK",
            delta_color="inverse" if metrics["security_issues_count"] > 0 else "normal"
        )

    st.markdown("---")

    # === SECTION 2 & 3: Pie chart cost + Donut subnet ===
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.write("**💰 Phân bổ Chi phí theo Máy chủ**")
    
        if metrics["cost_per_instance"]:
            cost_df = pd.DataFrame(metrics["cost_per_instance"])
        
            fig_cost = px.pie(
                cost_df,
                values='monthly_cost',
                names='name',
                hover_data=['type'],
                color_discrete_sequence=px.colors.sequential.Blues_r
            )
            fig_cost.update_traces(
                textposition='inside', 
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>Loại: %{customdata[0]}<br>Chi phí: $%{value}/tháng<extra></extra>'
            )
            fig_cost.update_layout(
                showlegend=True,
                height=350,
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_cost, use_container_width=True)
        
            # Top máy tốn tiền nhất
            top_cost = max(metrics["cost_per_instance"], key=lambda x: x['monthly_cost'])
            st.caption(f"💡 Máy tốn nhất: **{top_cost['name']}** (${top_cost['monthly_cost']}/tháng)")
        else:
            st.info("Chưa có máy nào đang chạy.")

    with chart_col2:
        st.write("**🌐 Phân loại Subnet (Public vs Private)**")
    
        total_subnets = metrics["public_subnet_count"] + metrics["private_subnet_count"]
        if total_subnets > 0:
            subnet_df = pd.DataFrame([
                {"type": "Public Subnet", "count": metrics["public_subnet_count"]},
                {"type": "Private Subnet", "count": metrics["private_subnet_count"]}
            ])
        
            fig_subnet = go.Figure(data=[go.Pie(
                labels=subnet_df['type'],
                values=subnet_df['count'],
                hole=0.5,
                marker=dict(colors=['#FFA500', '#10B981'])
            )])
            fig_subnet.update_traces(
                textposition='outside',
                textinfo='label+value',
                hovertemplate='<b>%{label}</b><br>Số lượng: %{value}<extra></extra>'
            )
            fig_subnet.update_layout(
                showlegend=False,
                height=350,
                margin=dict(t=20, b=20, l=20, r=20),
                annotations=[dict(
                    text=f'<b>{total_subnets}</b><br>Subnets',
                    x=0.5, y=0.5,
                    font_size=20,
                    showarrow=False
                )]
            )
            st.plotly_chart(fig_subnet, use_container_width=True)
        
            ratio = metrics["private_subnet_count"] / total_subnets * 100 if total_subnets > 0 else 0
            st.caption(f"💡 Tỷ lệ Private: **{ratio:.0f}%** (best practice: >= 60%)")
        else:
            st.info("Chưa có dữ liệu subnet.")

    st.markdown("---")

    # === SECTION 4: Health Score ===
    st.subheader("🏆 Health Score - Điểm Sức Khỏe Hạ tầng")

    hs = metrics["health_score"]
    grade, grade_text, grade_color = get_health_grade(hs["total"])

    # Layout: gauge bên trái, breakdown bên phải
    hs_col1, hs_col2 = st.columns([1, 1])

    with hs_col1:
        # Gauge chart cho tổng điểm
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=hs["total"],
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': f"<b>Hạng {grade} - {grade_text}</b>", 'font': {'size': 20, 'color': grade_color}},
            number={'suffix': "/100", 'font': {'size': 40}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1},
                'bar': {'color': grade_color},
                'steps': [
                    {'range': [0, 40], 'color': "#FEE2E2"},
                    {'range': [40, 60], 'color': "#FED7AA"},
                    {'range': [60, 75], 'color': "#FEF3C7"},
                    {'range': [75, 90], 'color': "#DBEAFE"},
                    {'range': [90, 100], 'color': "#D1FAE5"}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 3},
                    'thickness': 0.8,
                    'value': hs["total"]
                }
            }
        ))
        fig_gauge.update_layout(height=300, margin=dict(t=60, b=20, l=20, r=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with hs_col2:
        st.write("**📋 Chi tiết điểm thành phần:**")
    
        # Bar chart các thành phần
        components_df = pd.DataFrame([
            {"category": "🔒 Bảo mật (40%)", "score": hs["security"], "weight": 40},
            {"category": "💰 Chi phí (30%)", "score": hs["cost"], "weight": 30},
            {"category": "⚡ Hiệu năng (30%)", "score": hs["performance"], "weight": 30}
        ])
    
        fig_bar = go.Figure(go.Bar(
            x=components_df['score'],
            y=components_df['category'],
            orientation='h',
            marker=dict(
                color=components_df['score'],
                colorscale=[[0, '#EF4444'], [0.5, '#F59E0B'], [1, '#10B981']],
                cmin=0, cmax=100,
                showscale=False
            ),
            text=components_df['score'].apply(lambda x: f'{x}/100'),
            textposition='outside'
        ))
        fig_bar.update_layout(
            height=280,
            xaxis=dict(range=[0, 110], title="Điểm"),
            yaxis=dict(autorange="reversed"),
            margin=dict(t=20, b=40, l=20, r=20)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ============================================
    # CHI TIẾT BREAKDOWN ĐIỂM SỐ
    # ============================================
    st.markdown("### 📊 Chi tiết tính điểm")

    # Tabs cho 3 thành phần
    detail_tab1, detail_tab2, detail_tab3 = st.tabs([
        f"🔒 Bảo mật ({hs['security']}/100)",
        f"💰 Chi phí ({hs['cost']}/100)",
        f"⚡ Hiệu năng ({hs['performance']}/100)"
    ])

    # === TAB 1: BẢO MẬT - Hiển thị CHI TIẾT từng vấn đề ===
    with detail_tab1:
        st.write(f"**Cách tính:** Bắt đầu từ 100 điểm, trừ điểm theo mức độ nghiêm trọng của mỗi vấn đề.")
        st.caption("Quy tắc: CRITICAL = -25đ | HIGH = -15đ | MEDIUM = -10đ")
    
        if metrics["security_issues_detail"]:
            st.error(f"⚠️ Phát hiện **{metrics['security_issues_count']} vấn đề** bảo mật. Điểm bị trừ: **{100 - hs['security']} điểm**")
        
            # Bảng chi tiết
            sec_table = []
            for issue in metrics["security_issues_detail"]:
                severity_icon = {
                    "CRITICAL": "🔴 NGHIÊM TRỌNG",
                    "HIGH": "🟠 CAO",
                    "MEDIUM": "🟡 TRUNG BÌNH"
                }.get(issue["severity"], issue["severity"])
            
                penalty = {"CRITICAL": -25, "HIGH": -15, "MEDIUM": -10}.get(issue["severity"], 0)
            
                sec_table.append({
                    "Mức độ": severity_icon,
                    "Trừ điểm": penalty,
                    "Security Group": f"{issue['sg_name']}",
                    "Cổng": issue["port"],
                    "Vấn đề": issue["issue"],
                    "Rủi ro": issue["risk"]
                })
        
            sec_df = pd.DataFrame(sec_table)
            st.dataframe(sec_df, use_container_width=True, hide_index=True)
        
            # Cách khắc phục
            st.write("**🔧 Hướng dẫn khắc phục:**")
            for idx, issue in enumerate(metrics["security_issues_detail"], 1):
                with st.expander(f"Vấn đề #{idx}: {issue['issue']} ({issue['sg_name']})"):
                    st.write(f"**Security Group:** `{issue['sg_id']}` ({issue['sg_name']})")
                    st.write(f"**Mức độ:** {issue['severity']}")
                    st.write(f"**Rủi ro:** {issue['risk']}")
                    st.write(f"**Cách fix:** {issue['fix']}")
                
                    # Hướng dẫn fix cụ thể
                    if "22" in issue["port"]:
                        st.info(
                            "**Các bước fix cụ thể:**\n"
                            "1. AWS Console → EC2 → Security Groups\n"
                            f"2. Chọn SG `{issue['sg_name']}`\n"
                            "3. Edit inbound rules → tìm rule cổng 22\n"
                            "4. Đổi Source từ `0.0.0.0/0` thành IP cụ thể (ví dụ: `203.205.45.0/24`)\n"
                            "5. Hoặc xóa rule và dùng AWS Systems Manager Session Manager"
                        )
                    elif issue["port"] == "ALL":
                        st.error(
                            "**KHẨN CẤP - Fix ngay:**\n"
                            "1. Vào AWS Console → EC2 → Security Groups\n"
                            f"2. Chọn SG `{issue['sg_name']}`\n"
                            "3. Edit inbound rules → XÓA rule có Protocol = All và Source = 0.0.0.0/0\n"
                            "4. Tạo lại các rule cụ thể cho từng cổng cần thiết"
                        )
                    else:
                        st.info(
                            f"**Các bước fix:**\n"
                            "1. AWS Console → EC2 → Security Groups\n"
                            f"2. Chọn SG `{issue['sg_name']}`\n"
                            f"3. Edit inbound rule cổng {issue['port']}\n"
                            f"4. Giới hạn Source về IP cụ thể hoặc Security Group khác (không dùng 0.0.0.0/0)"
                        )
        else:
            st.success("✅ **Hoàn hảo!** Không phát hiện vấn đề bảo mật nào. Tất cả Security Groups đều an toàn.")

    # === TAB 2: CHI PHÍ ===
    with detail_tab2:
        st.write(f"**Cách tính:** Trừ điểm theo tỷ lệ máy đang dừng (lãng phí EBS volume).")
        st.caption("Công thức: 100 - (số máy stopped / tổng số máy × 100)")
    
        if hs["cost"] == 100:
            st.success("✅ **Hoàn hảo!** Không có máy nào đang lãng phí tài nguyên.")
        else:
            st.warning(f"⚠️ Điểm bị trừ: **{100 - hs['cost']} điểm**")
    
        st.write("**Chi tiết:**")
        for item in hs["cost_breakdown"]:
            st.write(f"- {item}")
    
        if metrics["stopped_count"] > 0:
            st.write("**📋 Danh sách máy đang dừng:**")
            stopped_list = []
            for res in ec2_data.get('Reservations', []):
                for inst in res['Instances']:
                    if inst['State']['Name'] in ('stopped', 'stopping'):
                        name = next(
                            (t['Value'] for t in inst.get('Tags', []) if t['Key'] == 'Name'),
                            inst['InstanceId'][-6:]
                        )
                        it_type = inst['InstanceType']
                        monthly = PRICING.get(it_type, 0) * 24 * 30
                        stopped_list.append({
                            "Tên máy": name,
                            "Instance ID": inst['InstanceId'],
                            "Loại": it_type,
                            "Trạng thái": inst['State']['Name'],
                            "Chi phí EBS dự kiến/tháng": f"~${monthly * 0.1:.2f}"
                        })
        
            if stopped_list:
                st.dataframe(pd.DataFrame(stopped_list), use_container_width=True, hide_index=True)
        
            st.info(
                "💡 **Khuyến nghị:**\n"
                "- Nếu không dùng nữa: **Terminate** (xóa hẳn) để ngừng tính phí EBS\n"
                "- Nếu dùng thỉnh thoảng: cân nhắc tạo **AMI snapshot** rồi terminate, khi cần thì khôi phục"
            )

    # === TAB 3: HIỆU NĂNG ===
    with detail_tab3:
        st.write(f"**Cách tính:** Trừ 10 điểm cho mỗi máy đang dừng (giảm khả năng phục vụ tải).")
        st.caption("Tối đa trừ 50 điểm. Nếu không có máy chạy, mặc định 50 điểm.")
    
        if hs["performance"] == 100:
            st.success("✅ **Hoàn hảo!** Tất cả máy chủ đang sẵn sàng phục vụ.")
        else:
            st.warning(f"⚠️ Điểm bị trừ: **{100 - hs['performance']} điểm**")
    
        st.write("**Chi tiết:**")
        for item in hs["performance_breakdown"]:
            st.write(f"- {item}")
    
        st.info(
            "💡 **Tăng điểm Hiệu năng bằng cách:**\n"
            "- Đảm bảo các máy quan trọng luôn ở trạng thái Running\n"
            "- Triển khai trên nhiều Availability Zone (AZ) để tăng High Availability\n"
            "- Cân nhắc dùng Auto Scaling Group để tự động bật/tắt máy theo tải"
        )

    # ============================================
    # TỔNG KẾT KHUYẾN NGHỊ ƯU TIÊN
    # ============================================
    st.markdown("---")
    st.write("**🎯 Hành động ưu tiên cần làm:**")

    priority_actions = []

    # Ưu tiên 1: CRITICAL security issues
    critical_issues = [i for i in metrics["security_issues_detail"] if i["severity"] == "CRITICAL"]
    if critical_issues:
        priority_actions.append({
            "level": "🔴 KHẨN CẤP",
            "action": f"Khắc phục {len(critical_issues)} lỗ hổng CRITICAL trong Security Group",
            "impact": "+25đ/lỗi cho điểm Bảo mật"
        })

    # Ưu tiên 2: HIGH security issues
    high_issues = [i for i in metrics["security_issues_detail"] if i["severity"] == "HIGH"]
    if high_issues:
        priority_actions.append({
            "level": "🟠 CAO",
            "action": f"Hạn chế CIDR cho {len(high_issues)} cổng SSH/RDP đang mở public",
            "impact": "+15đ/lỗi cho điểm Bảo mật"
        })

    # Ưu tiên 3: MEDIUM security issues
    medium_issues = [i for i in metrics["security_issues_detail"] if i["severity"] == "MEDIUM"]
    if medium_issues:
        priority_actions.append({
            "level": "🟡 TRUNG BÌNH",
            "action": f"Review {len(medium_issues)} cổng database/dải port mở public",
            "impact": "+10đ/lỗi cho điểm Bảo mật"
        })

    # Ưu tiên 4: Cost optimization
    if metrics["stopped_count"] > 0:
        priority_actions.append({
            "level": "🟢 TIẾT KIỆM",
            "action": f"Terminate {metrics['stopped_count']} máy đang dừng để ngừng tính phí EBS",
            "impact": f"Tiết kiệm ~${metrics['potential_savings_usd']}/tháng"
        })

    if priority_actions:
        action_df = pd.DataFrame(priority_actions)
        st.table(action_df)
    else:
        st.success("🎉 **Hệ thống đang ở trạng thái tối ưu! Không cần hành động gì thêm.**")

st.markdown("---")
st.subheader("📋 Bảng tổng hợp Máy chủ")

# Tạo bảng đầy đủ
instance_table = []
for res in ec2_data.get('Reservations', []):
    for inst in res['Instances']:
        if inst['State']['Name'] == 'terminated':
            continue
        name = next(
            (t['Value'] for t in inst.get('Tags', []) if t['Key'] == 'Name'),
            inst['InstanceId'][-6:]
        )
        it_type = inst['InstanceType']
        hourly = PRICING.get(it_type, 0)
        monthly = round(hourly * 24 * 30, 2)
        
        instance_table.append({
            "Tên": name,
            "Instance ID": inst['InstanceId'],
            "Loại": it_type,
            "Trạng thái": inst['State']['Name'],
            "Public IP": inst.get('PublicIpAddress', 'N/A'),
            "Private IP": inst.get('PrivateIpAddress', 'N/A'),
            "VPC": inst.get('VpcId', 'N/A'),
            "Giá/giờ ($)": hourly,
            "Giá/tháng ($)": monthly
        })

if instance_table:
    df_instances = pd.DataFrame(instance_table)
    st.dataframe(
        df_instances,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Trạng thái": st.column_config.TextColumn("Trạng thái", width="small"),
            "Giá/tháng ($)": st.column_config.NumberColumn(
                "Giá/tháng ($)",
                format="$%.2f"
            )
        }
    )
    
    # Footer tổng cộng
    total_monthly = sum(row["Giá/tháng ($)"] for row in instance_table 
                        if row["Trạng thái"] == "running")
    st.caption(
        f"**Tổng chi phí dự kiến (chỉ máy đang chạy): "
        f"${total_monthly:.2f}/tháng (~{total_monthly * 25400:,.0f} VNĐ)**"
    )
else:
    st.info("Chưa có máy chủ nào.")



