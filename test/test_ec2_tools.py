"""Unit Tests cho EC2 Tools."""
import pytest
from moto import mock_aws


class TestGetEC2Status:
    """Test cho hàm get_ec2_status."""
    
    @pytest.mark.unit
    def test_returns_empty_when_no_instances(self, aws_credentials):
        """Khi không có instance nào, phải trả về thông báo không tìm thấy."""
        with mock_aws():
            from src.tools.ec2_tools import get_ec2_status
            
            result = get_ec2_status.invoke({})
            
            assert isinstance(result, str)
            assert "Không tìm thấy" in result
    
    @pytest.mark.unit
    def test_returns_instance_list(self, aws_credentials, sample_instance):
        """Khi có instance, phải trả về list với đầy đủ thông tin."""
        from src.tools.ec2_tools import get_ec2_status
        
        result = get_ec2_status.invoke({})
        
        assert isinstance(result, list)
        assert len(result) >= 1
        
        # Kiểm tra structure của mỗi item
        first = result[0]
        assert "Name" in first
        assert "InstanceId" in first
        assert "Status" in first
        assert "InstanceType" in first
        assert "HourlyPrice" in first
    
    @pytest.mark.unit
    def test_excludes_terminated_instances(self, aws_credentials, ec2_client, sample_instance):
        """Instance đã terminate không được hiện trong danh sách."""
        # Terminate instance
        ec2_client.terminate_instances(InstanceIds=[sample_instance['instance_id']])
        
        from src.tools.ec2_tools import get_ec2_status
        result = get_ec2_status.invoke({})
        
        # Instance đã terminate không được trả về
        if isinstance(result, list):
            for item in result:
                assert item["InstanceId"] != sample_instance['instance_id']
    
    @pytest.mark.unit
    def test_pricing_for_known_instance_type(self, aws_credentials, sample_instance):
        """t3.micro phải có giá 0.0104 USD/giờ."""
        from src.tools.ec2_tools import get_ec2_status
        result = get_ec2_status.invoke({})
        
        # Tìm instance vừa tạo
        target = next(
            (item for item in result if item["InstanceId"] == sample_instance['instance_id']),
            None
        )
        
        assert target is not None
        assert target["InstanceType"] == "t3.micro"
        assert target["HourlyPrice"] == 0.0104


class TestManageEC2Power:
    """Test cho hàm manage_ec2_power (Start/Stop)."""
    
    @pytest.mark.unit
    def test_stop_instance_success(self, aws_credentials, sample_instance):
        """Stop instance đang chạy phải thành công."""
        from src.tools.ec2_tools import manage_ec2_power
        
        result = manage_ec2_power.invoke({
            "instance_id": sample_instance['instance_id'],
            "action": "STOP"
        })
        
        assert "TẮT" in result or "thành công" in result
    
    @pytest.mark.unit
    def test_start_instance_success(self, aws_credentials, sample_instance, ec2_client):
        """Start instance đã stop phải thành công."""
        # Stop trước
        ec2_client.stop_instances(InstanceIds=[sample_instance['instance_id']])
        
        from src.tools.ec2_tools import manage_ec2_power
        result = manage_ec2_power.invoke({
            "instance_id": sample_instance['instance_id'],
            "action": "START"
        })
        
        assert "BẬT" in result or "thành công" in result
    
    @pytest.mark.unit
    def test_invalid_action_returns_error(self, aws_credentials, sample_instance):
        """Action không phải START/STOP phải báo lỗi."""
        from src.tools.ec2_tools import manage_ec2_power
        
        result = manage_ec2_power.invoke({
            "instance_id": sample_instance['instance_id'],
            "action": "RESTART"  # Không hợp lệ
        })
        
        assert "không hợp lệ" in result.lower() or "không hợp" in result


class TestCreateEC2Instance:
    """Test cho hàm create_ec2_instance."""
    
    @pytest.mark.unit
    def test_create_with_valid_params(self, aws_credentials, ec2_client):
        """Tạo EC2 với params hợp lệ phải thành công."""
        from src.tools.ec2_tools import create_ec2_instance
        
        result = create_ec2_instance.invoke({
            "instance_type": "t3.micro",
            "instance_name": "my-new-server"
        })
        
        # Phải có dấu hiệu thành công
        assert "thành công" in result.lower() or "✅" in result
        assert "my-new-server" in result


class TestTerminateEC2Instance:
    """Test cho hàm terminate_ec2_instance."""
    
    @pytest.mark.unit
    def test_terminate_existing_instance(self, aws_credentials, sample_instance):
        """Xóa instance tồn tại phải thành công."""
        from src.tools.ec2_tools import terminate_ec2_instance
        
        result = terminate_ec2_instance.invoke({
            "instance_id": sample_instance['instance_id']
        })
        
        assert "xóa" in result.lower() or "🗑" in result or "đã gửi" in result.lower()