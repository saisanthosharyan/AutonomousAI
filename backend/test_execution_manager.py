from app.services.execution.execution_manager import ExecutionManager

PROJECT_PATH = r"C:\Users\iamar\OneDrive\Desktop\Autodev-AI\generated_projects\python_cli_calculator_20260729_133547"

print("=" * 60)
print("AUTODEV AI - EXECUTION MANAGER TEST")
print("=" * 60)

manager = ExecutionManager()

print("\nSTEP 1 - Detecting project type...")

project_type = manager.detect_project_type(PROJECT_PATH)

print(f"Detected project type: {project_type}")

assert project_type == "python"

print("Project type detection PASSED")

print("\nSTEP 2 - Executing generated project...")

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

if result.success:
    print("EXECUTION MANAGER TEST PASSED")
else:
    print("EXECUTION MANAGER TEST FAILED")

print("=" * 60)