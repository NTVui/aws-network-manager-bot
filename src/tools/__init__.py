"""Package chứa tất cả tools cho AI Agent."""
from src.tools.ec2_tools import (
    get_ec2_status, 
    manage_ec2_power, 
    create_ec2_instance, 
    terminate_ec2_instance
)
from src.tools.network_tools import (
    get_network_topology, 
    get_network_topology_raw, 
    build_mermaid_diagram
)
from src.tools.security_tools import (
    audit_security_groups, 
    get_security_groups_of_instance
)
from src.tools.monitoring_tools import (
    get_cpu_usage, 
    get_cpu_history_data
)
from src.tools.cost_tools import (
    get_actual_cost,
    recommend_instance_optimization
)
from src.tools.stress_test_tools import (
    run_stress_test,
    check_stress_test_result
)
from src.tools.audit_tools import (
    get_recent_aws_activities,
    get_failed_login_attempts
)

from src.tools.audit_tools import (
    get_recent_aws_activities,
    get_failed_login_attempts,
    simulate_failed_login_demo  # THÊM
)
# Tất cả tools để đăng ký với LangGraph agent
ALL_TOOLS = [
    get_ec2_status,
    get_cpu_usage,
    manage_ec2_power,
    get_network_topology,
    create_ec2_instance,
    terminate_ec2_instance,
    audit_security_groups,
    get_security_groups_of_instance,
    get_actual_cost,
    recommend_instance_optimization,
    run_stress_test,
    check_stress_test_result,
    get_recent_aws_activities,
    get_failed_login_attempts,
    simulate_failed_login_demo  
]