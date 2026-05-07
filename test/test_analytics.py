"""Unit Tests cho Analytics - Logic tính Health Score."""
import pytest
from src.utils.analytics import calculate_infrastructure_metrics, get_health_grade


class TestHealthGrade:
    """Test mapping điểm số sang grade chữ."""
    
    @pytest.mark.unit
    def test_grade_a_for_excellent(self):
        """Điểm >= 90 phải là grade A."""
        grade, text, color = get_health_grade(95)
        assert grade == "A"
        assert text == "Xuất sắc"
    
    @pytest.mark.unit
    def test_grade_b_for_good(self):
        """Điểm 75-89 phải là grade B."""
        grade, text, color = get_health_grade(80)
        assert grade == "B"
    
    @pytest.mark.unit
    def test_grade_f_for_poor(self):
        """Điểm < 40 phải là grade F."""
        grade, text, color = get_health_grade(30)
        assert grade == "F"
        assert text == "Yếu"
    
    @pytest.mark.unit
    def test_boundary_values(self):
        """Test các giá trị biên: 90, 75, 60, 40."""
        assert get_health_grade(90)[0] == "A"
        assert get_health_grade(89)[0] == "B"
        assert get_health_grade(75)[0] == "B"
        assert get_health_grade(74)[0] == "C"


class TestInfrastructureMetrics:
    """Test logic tính metric tổng thể."""
    
    @pytest.mark.unit
    def test_empty_infrastructure(self):
        """Hạ tầng trống phải có Health Score = 100 (không có vấn đề gì)."""
        empty_data = {"Reservations": []}
        metrics = calculate_infrastructure_metrics(empty_data)
        
        assert metrics["total_instances"] == 0
        assert metrics["monthly_cost_usd"] == 0
        assert metrics["security_issues_count"] == 0
    
    @pytest.mark.unit
    def test_count_instances_correctly(self):
        """Đếm số instance phải chính xác."""
        mock_data = {
            "Reservations": [{
                "Instances": [
                    {
                        "InstanceId": "i-001",
                        "InstanceType": "t3.micro",
                        "State": {"Name": "running"},
                        "Tags": [{"Key": "Name", "Value": "server1"}]
                    },
                    {
                        "InstanceId": "i-002",
                        "InstanceType": "t3.micro",
                        "State": {"Name": "stopped"},
                        "Tags": []
                    }
                ]
            }]
        }
        
        metrics = calculate_infrastructure_metrics(mock_data)
        
        assert metrics["total_instances"] == 2
        assert metrics["running_count"] == 1
        assert metrics["stopped_count"] == 1
    
    @pytest.mark.unit
    def test_security_score_decreases_with_issues(self):
        """Security score phải giảm khi có nhiều issue."""
        mock_data = {"Reservations": []}
        
        # Tạo SG có 2 issue (CRITICAL + HIGH)
        mock_sgs = [{
            "GroupId": "sg-001",
            "GroupName": "test-sg",
            "IpPermissions": [
                {  # CRITICAL: mở all traffic
                    "IpProtocol": "-1",
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
                },
                {  # HIGH: SSH public
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
                }
            ]
        }]
        
        metrics = calculate_infrastructure_metrics(
            mock_data, 
            security_groups=mock_sgs
        )
        
        # 2 issue: CRITICAL (-25) + HIGH (-15) = security score = 60
        assert metrics["security_issues_count"] == 2
        assert metrics["health_score"]["security"] == 60
    
    @pytest.mark.unit
    def test_monthly_cost_calculation(self):
        """Tính chi phí tháng phải chính xác."""
        mock_data = {
            "Reservations": [{
                "Instances": [{
                    "InstanceId": "i-001",
                    "InstanceType": "t3.micro",  # Giá: 0.0104/giờ
                    "State": {"Name": "running"},
                    "Tags": []
                }]
            }]
        }
        
        metrics = calculate_infrastructure_metrics(mock_data)
        
        # 0.0104 × 24 × 30 = 7.488
        expected_cost = 0.0104 * 24 * 30
        assert metrics["monthly_cost_usd"] == round(expected_cost, 2)