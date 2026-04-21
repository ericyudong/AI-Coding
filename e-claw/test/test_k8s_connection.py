"""Test Kubernetes connection"""
import os
os.environ['KUBECONFIG'] = r'C:\Users\E0008090\.minikube\config'

from kubernetes import client, config

try:
    config.load_kube_config()
    print("Kube config loaded successfully!")
    
    core_v1 = client.CoreV1Api()
    pods = core_v1.list_pod_for_all_namespaces()
    print(f"Found {len(pods.items)} pods in the cluster")
except Exception as e:
    print(f"Error: {e}")