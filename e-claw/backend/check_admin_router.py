"""Check admin router dependencies"""

import sys

sys.path.insert(0, "./backend")

# Don't import dependencies
from app.api.v1.admin import router

# Check router dependencies
print("Admin Router Dependencies:")
print(f"Type: {type(router)}")
print(f"Dependencies: {router.dependencies}")
print(f"Depends list: {list(router.dependencies)}")
print(f"\nRouter routes count: {len(router.routes)}")

# Check if there's a global dependency
for dep in router.dependencies:
    print(f"  Dependency: {dep}")
    if hasattr(dep, "dependency"):
        print(f"    Dependency func: {dep.dependency}")
    if hasattr(dep, "use_cache"):
        print(f"    Use cache: {dep.use_cache}")
