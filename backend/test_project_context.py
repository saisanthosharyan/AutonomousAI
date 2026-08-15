from app.project.project_context import ProjectContext


PROJECT_PATH = (
    r"C:\Users\iamar\OneDrive\Desktop"
    r"\Autodev-AI\generated_projects\fixer_test_python"
)


def main():

    print("=" * 60)
    print("PROJECT CONTEXT TEST")
    print("=" * 60)

    context = ProjectContext()

    result = context.build(PROJECT_PATH)

    print()
    print("Project:")
    print(result.summary.project_name)

    print()
    print("Root:")
    print(result.summary.root)

    print()
    print("Total files:")
    print(result.summary.total_files)

    print()
    print("Total directories:")
    print(result.summary.total_directories)

    print()
    print("Languages:")
    print(result.summary.languages)

    print()
    print("Frameworks:")
    print(result.summary.frameworks)

    print()
    print("Dependencies:")
    print(result.summary.dependencies)

    print()
    print("Scanned files:")
    print("-" * 60)

    for file in result.scanned_files:

        print(
            f"{file.path} | "
            f"{file.language}"
        )

    print()
    print("Indexed files:")
    print("-" * 60)

    for path in result.code_index:

        print(path)

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    assert context.ready is True

    assert result.summary.total_files > 0

    assert len(result.scanned_files) > 0

    assert len(result.code_index) > 0

    print()
    print("=" * 60)
    print("PROJECT CONTEXT TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()