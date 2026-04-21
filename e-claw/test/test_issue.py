"""Test creating an issue"""
import requests

# Login to get token
login_resp = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    data={"username": "admin", "password": "admin123"},
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)
print(f"Login status: {login_resp.status_code}")
token = login_resp.json()["access_token"]
print(f"Token: {token[:20]}...")

# Get projects first
projects_resp = requests.get(
    "http://localhost:8000/api/v1/projects",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"\nProjects status: {projects_resp.status_code}")
projects = projects_resp.json()
print(f"Projects: {projects}")

if projects:
    project_id = projects[0]["id"]
    # Create issue
    issue_resp = requests.post(
        f"http://localhost:8000/api/v1/projects/{project_id}/issues",
        json={
            "title": "Test Issue",
            "description": "This is a test issue",
            "issue_type": "task",
            "priority": "medium"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"\nCreate issue status: {issue_resp.status_code}")
    print(f"Response: {issue_resp.text}")