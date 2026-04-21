"""Test delete issue"""
import requests

# Login
login_resp = requests.post('http://localhost:8000/api/v1/auth/login', data={'username': 'admin', 'password': 'admin123'}, headers={'Content-Type': 'application/x-www-form-urlencoded'})
token = login_resp.json()['access_token']

# Get issues
issues_resp = requests.get('http://localhost:8000/api/v1/projects/c9cb3dcc-c516-4479-b8d5-9267711bcb93/issues', headers={'Authorization': f'Bearer {token}'})
issues = issues_resp.json()
print(f'Current issues: {len(issues)}')
for issue in issues:
    print(f'  - {issue["key"]}: {issue["title"]}')

if issues:
    # Delete the first issue
    issue_id = issues[0]['id']
    delete_resp = requests.delete(f'http://localhost:8000/api/v1/issues/{issue_id}', headers={'Authorization': f'Bearer {token}'})
    print(f'\nDelete status: {delete_resp.status_code}')
    print(f'Response: {delete_resp.text}')