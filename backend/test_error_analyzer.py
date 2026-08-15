from app.services.debugger.error_analyzer import ErrorAnalyzer

result = {
    "success": False,
    "return_code": 1,
    "stdout": """E       assert -1 == 5
E        +  where -1 = add(2, 3)
tests/test_app.py:4: AssertionError""",
    "stderr": "",
}

report = ErrorAnalyzer().analyze(result)

print("=" * 60)
print("ERROR ANALYZER TEST")
print("=" * 60)
print(report)
