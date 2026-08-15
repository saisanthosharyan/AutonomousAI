from app.project.project_scanner import ProjectScanner, ScannedFile


PROJECT_PATH = (
    r"C:\Users\iamar\OneDrive\Desktop"
    r"\Autodev-AI\generated_projects\fixer_test_python"
)


def main():

    print("=" * 60)
    print("PROJECT SCANNER TEST")
    print("=" * 60)

    scanner = ProjectScanner()

    files = scanner.scan(PROJECT_PATH)

    print()
    print("Scanner result type:")
    print(type(files))

    print()
    print("Number of files:")
    print(len(files))

    print()
    print("Files:")
    print("-" * 60)

    for file in files:

        print(
            f"Path     : {file.path}"
        )

        print(
            f"Language : {file.language}"
        )

        print(
            f"Config   : {file.is_config}"
        )

        print("-" * 60)

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    assert isinstance(
        files,
        list,
    ), "Scanner must return a list."

    assert all(
        isinstance(file, ScannedFile)
        for file in files
    ), "Every scanned item must be ScannedFile."

    assert len(files) > 0, (
        "Scanner did not find any files."
    )

    print()
    print("=" * 60)
    print("PROJECT SCANNER TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()