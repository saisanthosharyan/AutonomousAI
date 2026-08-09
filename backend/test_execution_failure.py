from app.services.execution.execution_manager import ExecutionManager

PROJECT_PATH = (
    r"C:\Users\iamar\OneDrive\Desktop\Autodev-AI"
    r"\generated_projects\fixer_test_python"
)

print("=" * 60)
print("AUTODEV AI - FAILURE EXECUTION TEST")
print("=" * 60)

manager = ExecutionManager()

print("\nSTEP 1 - Detecting project type...")

project_type = manager.detect_project_type(PROJECT_PATH)

print(f"Detected project type: {project_type}")

assert project_type == "python"

print("Project type detection PASSED")

print("\nSTEP 2 - Executing broken project...")

result = manager.run(PROJECT_PATH)

print("\n" + "=" * 60)
print("EXECUTION RESULT")
print("=" * 60)

print(f"Success       : {result.success}")
print(f"Project Type  : {result.project_type}")
print(f"Return Code   : {result.return_code}")
print(f"Execution Time: {result.execution_time} seconds")

print("\nSTDOUT:")
print(result.stdout)

print("\nSTDERR:")
print(result.stderr)

print("\n" + "=" * 60)

if not result.success:
    print("FAILURE DETECTION PASSED")
else:
    print("ERROR: Broken project unexpectedly passed")

print("=" * 60)