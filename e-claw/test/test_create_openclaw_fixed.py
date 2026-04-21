"""
测试创建OpenCLAW实例 - 修复版本
设置KUBECONFIG环境变量
"""
import os
# 必须先设置环境变量，再导入kubernetes相关模块
os.environ['KUBECONFIG'] = r'C:\Users\E0008090\.minikube\config'

import requests
import json

# 1. 登录获取token
print('=== 1. 登录获取Token ===')
resp = requests.post('http://localhost:8000/api/login', json={
    'username': 'admin',
    'password': 'admin123'
})
print('登录响应:', resp.status_code)
if resp.status_code != 200:
    print('登录失败')
    exit(1)

data = resp.json()
token = data.get('access_token')
print('Token:', token[:20] + '...')

# 2. 使用direct端点创建OpenCLAW实例
print('\n=== 2. 创建OpenCLAW实例 ===')
headers = {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
}

instance_data = {
    'name': 'test-openclaw-001',
    'description': 'Test OpenCLAW instance',
    'instance_type': 'openclaw',
    'cpu_cores': 2,
    'memory_gb': 4,
    'disk_gb': 20,
    'gpu_enabled': False,
    'gpu_count': 0,
    'os_type': 'linux',
    'os_version': 'latest'
}

resp = requests.post('http://localhost:8000/api/direct/instances', 
                     json=instance_data, headers=headers)
print('创建实例响应状态:', resp.status_code)
print('响应内容:', resp.text)

if resp.status_code == 200:
    result = resp.json()
    if result.get('status') == 'success':
        print('')
        print('=== 创建成功! ===')
        print('实例ID:', result.get('instance_id'))
        print('实例名称:', result.get('instance_name'))
        print('Pod名称:', result.get('pod_name'))
        print('服务URL:', result.get('service_url'))
        print('访问Token:', result.get('access_token'))
else:
    print('\n创建失败!')
    print('错误信息:', resp.text)