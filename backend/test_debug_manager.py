from app.services.debugger.debug_manager import DebugManager

execution_result = {
    "success": False,
    "return_code": 1,
    "stdout": """E       assert -1 == 5
E        +  where -1 = add(2, 3)
tests/test_app.py:4: AssertionError""",
    "stderr": "",
}

manager = DebugManager()

report = manager.analyze(execution_result)

print("=" * 60)
print("DEBUG MANAGER TEST")
print("=" * 60)

for key, value in report.items():
    print(f"{key}: {value}")
