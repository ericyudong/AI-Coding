# Read the admin.py file
with open('e-claw/backend/app/api/v1/admin.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with "total_quota: int = 1000000" in TenantCreate class and add status after it
new_lines = []
found_tenant_create = False
added_status = False

for i, line in enumerate(lines):
    new_lines.append(line)
    # Look for TenantCreate class
    if 'class TenantCreate(BaseModel):' in line:
        found_tenant_create = True
    # In TenantCreate, after total_quota, add status
    if found_tenant_create and not added_status and 'total_quota: int = 1000000' in line:
        # Add status field after this line
        new_lines.append('    status: str = "active"\n')
        added_status = True
        found_tenant_create = False

# Write back
with open('e-claw/backend/app/api/v1/admin.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Added status field: {added_status}")