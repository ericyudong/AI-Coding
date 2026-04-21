"""
测试创建OpenClaw实例 - 修复版本
使用curl直接调用API以避免httpx的问题
"""
import subprocess
import json
import sys

# 1. 先登录获取token
print("=" * 50)
print("1. 登录获取Token")
print("=" * 50)

# 使用curl登录
login_cmd = '''curl -s -X POST "http://localhost:8000/api/login" -H "Content-Type: application/json" -d "{\\"username\\":\\"admin\\",\\"password\\":\\"admin123\\"}"'''

result = subprocess.run(login_cmd, shell=True, capture_output=True, text=True)
print(f"Response: {result.stdout}")

try:
    response_data = json.loads(result.stdout)
    if "access_token" in response_data:
        token = response_data.get("access_token")
        print(f"Token: {token[:20]}...")
    else:
        print(f"登录错误: {response_data.get('message')}")
        sys.exit(1)
except Exception as e:
    print(f"Error parsing response: {e}")
    sys.exit(1)

# 2. 创建实例
print("\n" + "=" * 50)
print("2. 创建OpenCLAW实例")
print("=" * 50)

# 使用curl创建实例
instance_data = {
    "name": "test-openclaw-001",
    "description": "Test OpenCLAW instance",
    "instance_type": "openclaw",
    "cpu_cores": 2,
    "memory_gb": 4,
    "disk_gb": 20,
    "gpu_enabled": False,
    "gpu_count": 0,
    "os_type": "linux",
    "os_version": "latest"
}

# 转换数据为curl JSON格式
import json
instance_json = json.dumps(instance_data)

create_cmd = f'''curl -s -X POST "http://localhost:8000/api/v1/instances" -H "Content-Type: application/json" -H "Authorization: Bearer {token}" -d '{instance_json}' -w "\\nStatus: %{http_code}"'''

print(f"Command: {create_cmd}")
result = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)
print(f"Response: {result.stdout}")

if "Status: 201" in result.stdout or '"id"' in result.stdout:
    print("\n实例创建成功!")
else:
    print("\n实例创建失败!")