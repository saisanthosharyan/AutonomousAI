from app.core.logger import logger


class ErrorAnalyzer:
    """
    Performs lightweight static analysis of execution errors.

    The analyzer does not attempt to replace the AI debugger.
    Instead, it converts raw execution output into useful
    structured information for the FixerAgent.
    """

    ERROR_PATTERNS = {

        # ======================================================
        # Python
        # ======================================================

        "ModuleNotFoundError": (
            "Missing Python module or dependency."
        ),

        "ImportError": (
            "Python import statement failed."
        ),

        "SyntaxError": (
            "Python syntax error."
        ),

        "IndentationError": (
            "Python indentation error."
        ),
        "AssertionError": (
            "A test assertion failed."
        ),

        "NameError": (
            "Python variable or function is undefined."
        ),

        "TypeError": (
            "Invalid object type or function argument."
        ),

        "ValueError": (
            "Invalid value supplied to the program."
        ),

        "AttributeError": (
            "Object attribute or method does not exist."
        ),

        "KeyError": (
            "Dictionary key is missing."
        ),

        "IndexError": (
            "List or array index is out of range."
        ),

        "FileNotFoundError": (
            "Required file or directory was not found."
        ),

        "PermissionError": (
            "Permission denied while accessing a resource."
        ),

        "JSONDecodeError": (
            "Invalid JSON format."
        ),

        "RuntimeError": (
            "Runtime failure occurred."
        ),

        # ======================================================
        # Node.js
        # ======================================================

        "MODULE_NOT_FOUND": (
            "Node.js module or dependency is missing."
        ),

        "SyntaxError: Unexpected": (
            "Node.js JavaScript syntax error."
        ),

        "ReferenceError": (
            "JavaScript variable or function is undefined."
        ),

        "TypeError:": (
            "JavaScript object or value was used incorrectly."
        ),

        "ERR_MODULE_NOT_FOUND": (
            "Node.js ES module could not be found."
        ),

        "ECONNREFUSED": (
            "Connection was refused by the target service."
        ),

        "EADDRINUSE": (
            "The requested port is already in use."
        ),

        # ======================================================
        # Java
        # ======================================================

        "ClassNotFoundException": (
            "Java class or dependency could not be found."
        ),

        "NullPointerException": (
            "Java code attempted to access a null object."
        ),

        "NoSuchMethodError": (
            "Java method does not exist."
        ),

        "Compilation failed": (
            "Java compilation failed."
        ),

        # ======================================================
        # C++
        # ======================================================

        "fatal error:": (
            "C++ compiler encountered a fatal error."
        ),

        "undefined reference": (
            "C++ linker could not resolve a symbol."
        ),

        "error:": (
            "C++ compilation or runtime-related error."
        ),

        # ======================================================
        # General
        # ======================================================

        "TimeoutExpired": (
            "Execution exceeded the configured timeout."
        ),

        "Timeout": (
            "Execution timed out."
        ),

        "ConnectionError": (
            "Network connection failed."
        ),

        "Permission denied": (
            "Permission was denied."
        ),
    }

    RECOMMENDATIONS = {

        "ModuleNotFoundError": (
            "Install the missing Python dependency, "
            "verify requirements.txt, and correct imports."
        ),

        "ImportError": (
            "Check imports, package structure, and "
            "installed dependencies."
        ),

        "SyntaxError": (
            "Fix Python syntax errors and validate "
            "the file before execution."
        ),

        "IndentationError": (
            "Fix indentation and ensure consistent "
            "spaces/tabs."
        ),
        "AssertionError": (
            "Inspect the failed test assertion and fix "
            "the underlying implementation so the expected "
            "behavior is satisfied."
        ),

        "NameError": (
            "Define the missing variable/function or "
            "correct its name."
        ),

        "TypeError": (
            "Check argument types, return values, and "
            "function signatures."
        ),

        "ValueError": (
            "Validate input values before processing."
        ),

        "AttributeError": (
            "Verify object type and available attributes "
            "or methods."
        ),

        "KeyError": (
            "Check dictionary keys before accessing them."
        ),

        "IndexError": (
            "Validate list or array indexes."
        ),

        "FileNotFoundError": (
            "Create the required file or correct the "
            "file path."
        ),

        "PermissionError": (
            "Check file permissions and directory access."
        ),

        "JSONDecodeError": (
            "Validate and correct the JSON format."
        ),

        "MODULE_NOT_FOUND": (
            "Install the missing Node.js package and "
            "verify package.json imports."
        ),

        "ReferenceError": (
            "Define the missing JavaScript variable/function "
            "or correct its name."
        ),

        "ERR_MODULE_NOT_FOUND": (
            "Check the import path and install the required "
            "Node.js dependency."
        ),

        "EADDRINUSE": (
            "Use another port or terminate the process "
            "currently using the port."
        ),

        "ECONNREFUSED": (
            "Verify the target service, port, database, "
            "and network configuration."
        ),

        "ClassNotFoundException": (
            "Check Java classpath and dependencies."
        ),

        "NullPointerException": (
            "Validate objects before accessing their methods "
            "or properties."
        ),

        "NoSuchMethodError": (
            "Verify the method name, parameters, and dependency "
            "versions."
        ),

        "Compilation failed": (
            "Inspect Java compiler errors and correct the "
            "source code or dependencies."
        ),

        "fatal error:": (
            "Fix the C++ compiler error and verify required "
            "headers or libraries."
        ),

        "undefined reference": (
            "Check C++ linking configuration and required "
            "libraries."
        ),

        "TimeoutExpired": (
            "Optimize execution, fix blocking operations, "
            "or increase the timeout when appropriate."
        ),

        "Timeout": (
            "Inspect infinite loops, blocking operations, "
            "or external service calls."
        ),

        "ConnectionError": (
            "Check network connectivity and external endpoints."
        ),
    }

    def analyze(
        self,
        execution_result: dict | None,
    ) -> dict:

        logger.info(
            "Running Error Analyzer..."
        )

        # ======================================================
        # No result
        # ======================================================

        if execution_result is None:

            return self._build_report(
                category="ExecutionError",
                summary="Execution never started.",
                recommendation=(
                    "Verify project generation, project structure, "
                    "entry point, and executor configuration."
                ),
                stdout="",
                stderr="Execution never started.",
                return_code=-1,
            )

        stdout = str(
            execution_result.get(
                "stdout",
                "",
            )
            or ""
        )

        stderr = str(
            execution_result.get(
                "stderr",
                "",
            )
            or ""
        )

        return_code = execution_result.get(
            "return_code",
            -1,
        )

        # ======================================================
        # Success
        # ======================================================

        if execution_result.get("success"):

            return self._build_report(
                category="success",
                summary="Project executed successfully.",
                recommendation="",
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
            )

        # ======================================================
        # Combine output
        # ======================================================

        combined = (
            f"{stdout}\n{stderr}"
        )

        category = "UnknownError"
        summary = (
            "Unable to determine the exact failure reason."
        )

        # ======================================================
        # Pattern detection
        # ======================================================

        for error_name, description in (
            self.ERROR_PATTERNS.items()
        ):

            if error_name.lower() in combined.lower():

                category = error_name
                summary = description

                logger.info(
                    f"Detected error category: {category}"
                )

                break

        recommendation = (
            self.RECOMMENDATIONS.get(
                category,
                (
                    "Inspect stdout, stderr, return code, "
                    "project structure, dependencies, and "
                    "configuration. Repair the root cause "
                    "without removing existing functionality."
                ),
            )
        )

        return self._build_report(
            category=category,
            summary=summary,
            recommendation=recommendation,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
        )

    # ==========================================================
    # REPORT BUILDER
    # ==========================================================

    def _build_report(
        self,
        category: str,
        summary: str,
        recommendation: str,
        stdout: str,
        stderr: str,
        return_code: int,
    ) -> dict:

        return {
            "category": category,
            "summary": summary,
            "recommendation": recommendation,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
        }