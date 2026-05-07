# AWS AI Ops - DevOps Network Manager

[![CI Pipeline](https://github.com/NTVui/aws-network-manager-bot/actions/workflows/devops_pipeline.yml/badge.svg)](https://github.com/NTVui/aws-network-manager-bot/actions/workflows/devops_pipeline.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> AI Agent vận hành hạ tầng AWS với LangGraph + Groq Llama 3.1, tích hợp DevOps Pipeline đầy đủ.

## Tính năng chính

- **AI DevOps Assistant**: Hỏi đáp tự nhiên về hạ tầng AWS bằng tiếng Việt
- **EC2 Management**: Tạo, bật/tắt, xóa máy chủ với 1 click
- **Security Audit**: Tự động phát hiện lỗ hổng Security Groups
- **Cost Analysis**: Theo dõi chi phí thực tế qua Cost Explorer
- **Network Topology**: Vẽ sơ đồ mạng AWS bằng Mermaid
- **Health Score Dashboard**: Đánh giá hạ tầng theo 3 tiêu chí (Security/Cost/Performance)

## Quick Start

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/aws-network-manager-bot.git
cd aws-network-manager-bot

# Setup virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials in .env
cp .env.example .env
# Edit .env with your AWS keys

# Run app
streamlit run src/app.py
```

## Testing

```bash
# Run all tests
python -m pytest

# Run with coverage report
python -m pytest --cov=src --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_ec2_tools.py -v
```

## Tech Stack

- **Frontend**: Streamlit + Plotly
- **AI**: LangGraph + Groq (Llama 3.1)
- **Cloud**: AWS (EC2, CloudWatch, CloudTrail, Cost Explorer, SSM)
- **Testing**: pytest + moto (mock AWS)
- **CI/CD**: GitHub Actions