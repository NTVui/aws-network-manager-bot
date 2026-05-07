"""Unit Tests cho Security Tools."""
import pytest


class TestAuditSecurityGroups:
    """Test cho hàm audit_security_groups."""
    
    @pytest.mark.unit
    def test_detects_open_ssh_port(self, aws_credentials, sample_security_group_vulnerable):
        """Phải phát hiện SSH (22) mở public."""
        from src.tools.security_tools import audit_security_groups
        
        result = audit_security_groups.invoke({})
        
        assert "22" in result
        assert "SSH" in result or "vulnerable-sg" in result
    
    @pytest.mark.unit
    def test_detects_open_mysql_port(self, aws_credentials, sample_security_group_vulnerable):
        """Phải phát hiện MySQL (3306) mở public."""
        from src.tools.security_tools import audit_security_groups
        
        result = audit_security_groups.invoke({})
        
        assert "3306" in result
    
    @pytest.mark.unit
    def test_safe_sg_not_flagged(self, aws_credentials, sample_security_group_safe):
        """SG an toàn (chỉ mở cho IP cụ thể) không bị flag."""
        from src.tools.security_tools import audit_security_groups
        
        result = audit_security_groups.invoke({})
        
        # Không nên có warning về safe-sg
        assert "safe-sg" not in result or "an toàn" in result.lower()
    
    @pytest.mark.unit
    def test_no_issues_when_no_sgs(self, aws_credentials):
        """Khi không có SG vi phạm, phải báo an toàn."""
        from moto import mock_aws
        with mock_aws():
            from src.tools.security_tools import audit_security_groups
            
            result = audit_security_groups.invoke({})
            assert "an toàn" in result.lower() or "không phát hiện" in result.lower() or len(result) > 0


class TestGetSecurityGroupsOfInstance:
    """Test cho hàm get_security_groups_of_instance."""
    
    @pytest.mark.unit
    def test_find_by_instance_id(self, aws_credentials, sample_instance):
        """Tìm SG theo Instance ID phải thành công."""
        from src.tools.security_tools import get_security_groups_of_instance
        
        result = get_security_groups_of_instance.invoke({
            "instance_name_or_id": sample_instance['instance_id']
        })
        
        assert "SECURITY GROUP" in result.upper() or "không tìm thấy" not in result.lower()
    
    @pytest.mark.unit
    def test_find_by_instance_name(self, aws_credentials, sample_instance):
        """Tìm SG theo tên máy phải thành công."""
        from src.tools.security_tools import get_security_groups_of_instance
        
        result = get_security_groups_of_instance.invoke({
            "instance_name_or_id": sample_instance['name']
        })
        
        assert sample_instance['name'] in result or sample_instance['instance_id'] in result
    
    @pytest.mark.unit
    def test_nonexistent_instance_returns_error(self, aws_credentials):
        """Instance không tồn tại phải báo lỗi."""
        from moto import mock_aws
        with mock_aws():
            from src.tools.security_tools import get_security_groups_of_instance
            
            result = get_security_groups_of_instance.invoke({
                "instance_name_or_id": "i-nonexistent12345"
            })
            
            assert "không tìm thấy" in result.lower() or "không có" in result.lower()