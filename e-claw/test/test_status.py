"""Test update issue status"""
import requests

# Login
login_resp = requests.post('http://localhost:8000/api/v1/auth/login', data={'username': 'admin', 'password': 'admin123'}, headers={'Content-Type': 'application/x-www-form-urlencoded'})
token = login_resp.json()['access_token']

# Get issues
issues_resp = requests.get('http://localhost:8000/api/v1/projects/c9cb3dcc-c516-4479-b8d5-9267711bcb93/issues', headers={'Authorization': f'Bearer {token}'})
issues = issues_resp.json()
print(f'Current issues: {len(issues)}')
for issue in issues:
    print(f'  - {issue["key"]}: {issue["title"]} (status: {issue["status"]})')

if issues:
    # Update first issue status
    issue_id = issues[0]['id']
    update_resp = requests.patch(f'http://localhost:8000/api/v1/issues/{issue_id}', json={'status': 'in_progress'}, headers={'Authorization': f'Bearer {token}'})
    print(f'\nUpdate status: {update_resp.status_code}')
    print(f'Response: {update_resp.text}')