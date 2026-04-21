import sys
sys.path.insert(0, r"c:\eswin\emaas\e-claw\backend")
from app.main import app
print("App imported successfully!")
print(f"App title: {app.title}")