import re

# Read the file
with open('e-claw/backend/app/api/v1/admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace TenantCreate class to add status field
old_class = '''class TenantCreate(BaseModel):
    name: str
    code: str
    description: str = ""
    total_quota: int = 1000000'''

new_class = '''class TenantCreate(BaseModel):
    name: str
    code: str
    description: str = ""
    total_quota: int = 1000000
    status: str = "active"'''

content = content.replace(old_class, new_class)

# Write back
with open('e-claw/backend/app/api/v1/admin.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")