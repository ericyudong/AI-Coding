"""
测试创建OpenCLAW实例 - 使用httpx避免requests库的local_kw问题
"""
import httpx
import json

# 1. 先登录获取token
login_url = "http://localhost:8000/api/login"
login_data = {"username": "admin", "password": "admin123"}

print("=" * 50)
print("1. 登录获取Token")
print("=" * 50)

token = None
try:
    with httpx.Client() as client:
        response = client.post(login_url, json=login_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            if "access_token" in response_data:
                token = response_data.get("access_token")
                print(f"Token: {token[:20]}...")
            else:
                print(f"登录错误: {response_data.get('message')}")
                token = None
        else:
            print("登录失败!")
            token = None
            
except Exception as e:
    print(f"Error: {e}")
    token = None

if not token:
    print("无法获取token，测试终止")
    exit(1)

# 2. 创建实例
print("\n" + "=" * 50)
print("2. 创建OpenCLAW实例")
print("=" * 50)

create_url = "http://localhost:8000/api/v1/instances"

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

try:
    with httpx.Client() as client:
        create_response = client.post(
            create_url,
            json=instance_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        print(f"Status: {create_response.status_code}")
        print(f"Response: {create_response.text}")
        
        if create_response.status_code == 201:
            result = create_response.json()
            print(f"\n实例创建成功!")
            print(f"  实例ID: {result.get('id')}")
            print(f"  实例名称: {result.get('name')}")
            print(f"  状态: {result.get('status')}")
        else:
            print(f"\n实例创建失败!")
            
except Exception as e:
    print(f"Error: {e}")