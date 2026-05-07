"""AI Agent core logic - dùng LangGraph + Groq Llama."""
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage

from src.config import GROQ_API_KEY, GROQ_MODEL
from src.tools import ALL_TOOLS

# Re-export để app.py dùng
from src.tools.monitoring_tools import get_cpu_history_data
from src.tools.network_tools import get_network_topology_raw, build_mermaid_diagram
from src.tools.ec2_tools import create_ec2_instance
from src.tools.stress_test_tools import run_stress_test, check_stress_test_result
from src.utils.helpers import calculate_monthly_cost as get_cost_estimate


_PROMPT = (
    "Bạn là chuyên gia DevOps vận hành hạ tầng AWS. Trả lời bằng tiếng Việt chuyên nghiệp, súc tích.\n\n"
    
    "QUY TẮC CHỌN TOOL:\n"
    "1. Hỏi về danh sách máy chủ, IP, VPC, trạng thái → 'get_ec2_status'.\n"
    "2. Hỏi về CPU, hiệu năng → 'get_cpu_usage'.\n"
    "3. Hỏi về CHI PHÍ ƯỚC TÍNH (giá theo cấu hình) → 'get_ec2_status' rồi tính theo công thức Cost = Price × 720.\n"
    "4. Hỏi CHI PHÍ THỰC TẾ (đã dùng bao nhiêu, bill, hóa đơn) → 'get_actual_cost'.\n"
    "5. Hỏi TỐI ƯU CẤU HÌNH (nâng/hạ cấp, có lãng phí không) → 'recommend_instance_optimization'.\n"
    "6. Security Group của 1 máy cụ thể → 'get_security_groups_of_instance'.\n"
    "7. Audit toàn hệ thống → 'audit_security_groups'.\n"
    "8. VPC, Subnet, Network → 'get_network_topology'.\n"
    "9. Bật/Tắt máy → 'manage_ec2_power'. Xóa máy → 'terminate_ec2_instance'.\n"
    "10. Stress test hiệu năng → 'run_stress_test'.\n"
    "11. Audit log hoạt động AWS → 'get_recent_aws_activities'.\n"
    "12. Đăng nhập thất bại (thật) → 'get_failed_login_attempts'.\n"
    "13. Demo failed login (thuyết trình) → 'simulate_failed_login_demo'.\n\n"
    
    "QUY TẮC TRÌNH BÀY KẾT QUẢ (RẤT QUAN TRỌNG):\n"
    "- KHI TOOL TRẢ VỀ DỮ LIỆU CHI TIẾT (danh sách IP, thời gian, username, log...), "
    "BẮT BUỘC trình bày lại TOÀN BỘ chi tiết đó cho người dùng. KHÔNG được tóm tắt chung chung.\n"
    "- Nếu tool trả về danh sách các sự kiện/log → trình bày dưới dạng bảng Markdown "
    "với đầy đủ các cột (thời gian, user, IP, hành động).\n"
    "- Nếu tool trả về cảnh báo brute-force → giữ nguyên chi tiết IP và số lần thử.\n"
    "- Sau khi trình bày dữ liệu chi tiết, mới đưa nhận xét/khuyến nghị.\n"
    "- KHÔNG paraphrase mất thông tin. KHÔNG bỏ qua dữ liệu cụ thể như IP, timestamp, ID.\n\n"
    
    "QUY TẮC TUYỆT ĐỐI:\n"
    "- KHÔNG bịa dữ liệu. Chỉ dùng kết quả thực tế từ tool.\n"
    "- KHÔNG gọi nhầm tool. Đọc kỹ câu hỏi.\n"
    "- Tỷ giá: 1 USD = 26324 VNĐ.\n"
    "- Định dạng dữ liệu chi tiết bằng bảng Markdown khi có thể."
)

_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        llm = ChatGroq(
            temperature=0,
            model_name=GROQ_MODEL,
            groq_api_key=GROQ_API_KEY
        )
        _agent = create_react_agent(llm, ALL_TOOLS, prompt=_PROMPT)
    return _agent


def ask_ai(question):
    # BƯỚC 1: Check xem có thể gọi tool trực tiếp không (bypass AI)
    direct_result = try_direct_tool_call(question)
    if direct_result is not None:
        return direct_result
    
    # BƯỚC 2: Nếu không match, dùng AI agent như bình thường
    try:
        result = _get_agent().invoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": 10}
        )
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                content = msg.content.strip()
                if content and not content.startswith("<"):
                    return content
        return result["messages"][-1].content
    except Exception as e:
        if "recursion limit" in str(e).lower():
            return "Yêu cầu quá phức tạp. Vui lòng hỏi cụ thể hơn."
        return f"Lỗi: {str(e)}"
    
# Map keyword → tool function để bypass AI khi cần
DIRECT_TOOL_MAPPING = {
    # Failed login & audit
    "demo failed login": "simulate_failed_login_demo",
    "báo cáo demo": "simulate_failed_login_demo",
    "demo về failed": "simulate_failed_login_demo",
    "đăng nhập thất bại": "get_failed_login_attempts",
    "failed login": "get_failed_login_attempts",
    "audit log": "get_recent_aws_activities",
    "hoạt động aws": "get_recent_aws_activities",
    
    # Security
    "audit security": "audit_security_groups",
    "kiểm tra bảo mật": "audit_security_groups",
    "lỗ hổng bảo mật": "audit_security_groups",
    
    # Cost
    "chi phí thực tế": "get_actual_cost",
    "chi phí 7 ngày": "get_actual_cost",
    "bill aws": "get_actual_cost",
    "hóa đơn aws": "get_actual_cost",
}


def try_direct_tool_call(question: str):
    """
    Phát hiện câu hỏi cần data chi tiết, gọi tool trực tiếp thay vì qua AI.
    Trả về None nếu không match, ngược lại trả về output tool.
    """
    question_lower = question.lower()
    
    for keyword, tool_name in DIRECT_TOOL_MAPPING.items():
        if keyword in question_lower:
            # Import tool tương ứng
            from src.tools import (
                simulate_failed_login_demo,
                get_failed_login_attempts,
                get_recent_aws_activities,
                audit_security_groups,
                get_actual_cost,
            )
            
            tool_map = {
                "simulate_failed_login_demo": simulate_failed_login_demo,
                "get_failed_login_attempts": get_failed_login_attempts,
                "get_recent_aws_activities": get_recent_aws_activities,
                "audit_security_groups": audit_security_groups,
                "get_actual_cost": get_actual_cost,
            }
            
            tool_func = tool_map.get(tool_name)
            if tool_func:
                try:
                    # Gọi tool với args mặc định
                    if tool_name in ("simulate_failed_login_demo", "audit_security_groups"):
                        result = tool_func.invoke({})
                    elif tool_name == "get_failed_login_attempts":
                        result = tool_func.invoke({"hours_back": 24})
                    elif tool_name == "get_recent_aws_activities":
                        result = tool_func.invoke({"hours_back": 24, "max_events": 15})
                    elif tool_name == "get_actual_cost":
                        result = tool_func.invoke({"days_back": 7})
                    else:
                        return None
                    
                    return result
                except Exception as e:
                    return f"Lỗi khi gọi tool: {str(e)}"
    
    return None