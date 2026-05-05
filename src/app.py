import streamlit as st
import boto3
import os
from datetime import datetime, timedelta
from src.agent_logic import ask_ai, get_cpu_history_data # Đảm bảo hàm này đã có trong agent_logic.py

# 1. Cấu hình trang
st.set_page_config(page_title="AWS AI Ops Dashboard", page_icon="☁️", layout="wide")

# Khởi tạo client EC2 để lấy danh sách máy cho Sidebar
REGION = "us-east-1"
ec2_client = boto3.client(
    'ec2',
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

st.title("🤖 AI Agent Vận hành Mạng AWS")
st.markdown(f"*Đang hoạt động tại Region: **{REGION}***")
st.markdown("---")

# 2. Giao diện Sidebar
with st.sidebar:
    st.header("⚙️ Cấu hình hệ thống")
    st.info("Model: Llama 3.1 (Groq Speed)")
    
    # Lấy danh sách Instance ID thực tế để người dùng chọn
    try:
        response = ec2_client.describe_instances()
        instance_ids = []
        for res in response['Reservations']:
            for inst in res['Instances']:
                if inst['State']['Name'] != 'terminated':
                    name = next((t['Value'] for t in inst.get('Tags', []) if t['Key'] == 'Name'), inst['InstanceId'])
                    instance_ids.append(f"{name} ({inst['InstanceId']})")
        
        selected_option = st.selectbox("🎯 Chọn Instance để giám sát:", instance_ids if instance_ids else ["Không tìm thấy máy"])
        selected_id = selected_option.split("(")[-1].replace(")", "") if "(" in selected_option else None
        
    except Exception as e:
        st.error(f"Lỗi kết nối AWS: {e}")
        selected_id = None

    st.success("Kết nối AWS: OK")
    if st.button("🔄 Làm mới Dashboard"):
        st.rerun()

# 3. Khu vực Chatbot
st.subheader("💬 Trợ lý ảo DevOps")
container = st.container(border=True)
with container:
    user_input = st.text_input("Hỏi về hạ tầng của bạn:", placeholder="Ví dụ: Kiểm tra CPU của máy chủ may1 giúp tôi.")

if user_input:
    with st.spinner("🚀 AI đang phân tích dữ liệu AWS..."):
        response = ask_ai(user_input)
        st.markdown("### 💡 Câu trả lời:")
        st.write(response)

# 4. Khu vực Biểu đồ Real-time
st.markdown("---")
st.subheader(f"📊 Giám sát tài nguyên (Real-time: {selected_id if selected_id else 'N/A'})")

col1, col2 = st.columns(2)

with col1:
    st.write("**CPU Utilization (%) - 1 Giờ qua**")
    if selected_id:
        # Gọi hàm lấy dữ liệu thực từ CloudWatch
        cpu_history = get_cpu_history_data(selected_id)
        if cpu_history:
            st.line_chart(cpu_history)
        else:
            st.warning("Đang đợi dữ liệu từ CloudWatch (thường mất 5 phút)...")
    else:
        st.info("Vui lòng chọn máy chủ ở Sidebar.")

# --- Tìm trạng thái thực tế của máy được chọn ---
current_status = "N/A"
if selected_id:
    for res in response['Reservations']:
        for inst in res['Instances']:
            if inst['InstanceId'] == selected_id:
                current_status = inst['State']['Name'].capitalize() # Lấy trạng thái thực: Running, Stopped...

# --- Phần hiển thị cột 2 ---
with col2:
    st.write("**Thông tin nhanh**")
    if selected_id:
        # Thay "Running" bằng biến current_status vừa lấy được
        color_delta = "Ổn định" if current_status == "Running" else "Không hoạt động"
        
        st.metric(label="Trạng thái máy chủ", value=current_status, delta=color_delta)
        st.caption("Gợi ý: Bạn có thể hỏi AI về cách tối ưu hóa chi phí cho máy này.")
    else:
        st.write("Chưa có dữ liệu.")