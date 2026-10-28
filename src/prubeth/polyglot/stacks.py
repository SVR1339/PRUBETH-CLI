"""PRUBETH Language Stack Catalogue & Ecosystem Definitions.

Defines 13 major software engineering language stacks with custom markers,
test frameworks, compilers, and project instruction templates.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any

@dataclass
class LanguageStack:
    id: str
    name: str
    extensions: List[str]
    markers: List[str]
    default_test_cmd: str
    default_build_cmd: str
    default_lint_cmd: str
    default_run_cmd: str
    description: str
    framework_detection_files: Dict[str, str] = field(default_factory=dict)

    def generate_prubeth_md(self, workspace_name: str) -> str:
        """Constructs a deterministic project context directive (PRUBETH.md)."""
        return f"""# Project Instructions (PRUBETH.md)
<!-- Analogous to CLAUDE.md & GEMINI.md: Pinned in prompt prefix for zero cache invalidation -->

## Project Overview
- **Technology Stack**: {self.name}
- **Workspace Root**: `{workspace_name}`
- **Primary Extensions**: {', '.join(self.extensions)}

## Active Commands
- **Run Tests**: `{self.default_test_cmd}`
- **Build / Compile**: `{self.default_build_cmd}`
- **Lint / Analyse**: `{self.default_lint_cmd}`
- **Run Application**: `{self.default_run_cmd}`

## Architecture & Code Style Guidelines
- **Modularity**: Organise code cleanly into single-responsibility modules.
- **Type Safety**: Enforce strict type definitions, compiler flags, and zero unchecked warnings.
- **Verification Gate**: Never commit or mark tasks complete without verifying `{self.default_test_cmd}` returns exit code 0.
- **Orthography**: Formal British English for comments and architectural documentation.
"""

SUPPORTED_STACKS: Dict[str, LanguageStack] = {
    "python": LanguageStack(
        id="python",
        name="Python 3 (Standard Engineering Stack)",
        extensions=[".py", ".pyi"],
        markers=["pyproject.toml", "setup.py", "requirements.txt", "Pipfile", "poetry.lock"],
        default_test_cmd="pytest -v --tb=short",
        default_build_cmd="python -m build",
        default_lint_cmd="ruff check .",
        default_run_cmd="python main.py",
        description="Python 3 ecosystem with pytest, ruff, black, and virtual environment tooling.",
        framework_detection_files={"pytest.ini": "pytest", "conftest.py": "pytest"}
    ),
    "typescript": LanguageStack(
        id="typescript",
        name="TypeScript (Node.js / Deno / Bun)",
        extensions=[".ts", ".tsx", ".mts", ".cts"],
        markers=["tsconfig.json"],
        default_test_cmd="npm test",
        default_build_cmd="npm run build",
        default_lint_cmd="npx eslint .",
        default_run_cmd="npm start",
        description="Modern TypeScript with tsc compiler, vitest/jest, and strict type checking."
    ),
    "javascript": LanguageStack(
        id="javascript",
        name="JavaScript (Node.js / Web)",
        extensions=[".js", ".jsx", ".mjs", ".cjs"],
        markers=["package.json"],
        default_test_cmd="npm test",
        default_build_cmd="npm run build",
        default_lint_cmd="npx eslint .",
        default_run_cmd="node index.js",
        description="Standard JavaScript ecosystem with Node.js and npm package management."
    ),
    "rust": LanguageStack(
        id="rust",
        name="Rust (Cargo Ecosystem)",
        extensions=[".rs"],
        markers=["Cargo.toml", "Cargo.lock"],
        default_test_cmd="cargo test",
        default_build_cmd="cargo build --release",
        default_lint_cmd="cargo clippy -- -D warnings",
        default_run_cmd="cargo run",
        description="Systems engineering in Rust with cargo build tool, clippy linter, and unit/integration tests."
    ),
    "go": LanguageStack(
        id="go",
        name="Go (Golang Modules)",
        extensions=[".go"],
        markers=["go.mod", "go.sum"],
        default_test_cmd="go test -v ./...",
        default_build_cmd="go build ./...",
        default_lint_cmd="go vet ./...",
        default_run_cmd="go run .",
        description="Concurrent, type-safe Go ecosystem with standard go test and go vet."
    ),
    "java": LanguageStack(
        id="java",
        name="Java (Maven / Gradle)",
        extensions=[".java"],
        markers=["pom.xml", "build.gradle", "build.gradle.kts"],
        default_test_cmd="mvn test",
        default_build_cmd="mvn clean package",
        default_lint_cmd="mvn checkstyle:check",
        default_run_cmd="mvn exec:java",
        description="Enterprise Java ecosystem managed via Apache Maven or Gradle with JUnit testing."
    ),
    "csharp": LanguageStack(
        id="csharp",
        name="C# / .NET Core",
        extensions=[".cs"],
        markers=["*.csproj", "*.sln", "Directory.Build.props"],
        default_test_cmd="dotnet test",
        default_build_cmd="dotnet build",
        default_lint_cmd="dotnet format --verify-no-changes",
        default_run_cmd="dotnet run",
        description="Modern cross-platform .NET application stack with C# and dotnet test runner."
    ),
    "cpp": LanguageStack(
        id="cpp",
        name="C / C++ (CMake / CTest)",
        extensions=[".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"],
        markers=["CMakeLists.txt", "Makefile", "meson.build"],
        default_test_cmd="ctest --output-on-failure",
        default_build_cmd="cmake --build build",
        default_lint_cmd="clang-tidy -p build",
        default_run_cmd="./build/app",
        description="High-performance native C and C++ engineering with CMake build trees and clang-format."
    ),
    "dart": LanguageStack(
        id="dart",
        name="Dart / Flutter",
        extensions=[".dart"],
        markers=["pubspec.yaml", "pubspec.lock"],
        default_test_cmd="dart test",
        default_build_cmd="dart compile exe bin/main.dart",
        default_lint_cmd="dart analyze",
        default_run_cmd="dart run",
        description="Dart and Flutter multiplatform application framework with pub package manager."
    ),
    "php": LanguageStack(
        id="php",
        name="PHP (Composer / PHPUnit)",
        extensions=[".php"],
        markers=["composer.json", "composer.lock"],
        default_test_cmd="./vendor/bin/phpunit",
        default_build_cmd="composer install",
        default_lint_cmd="./vendor/bin/phpstan analyse",
        default_run_cmd="php index.php",
        description="Modern PHP application stack with Composer dependency resolution and PHPUnit testing."
    ),
    "ruby": LanguageStack(
        id="ruby",
        name="Ruby (Bundler / RSpec)",
        extensions=[".rb", ".rake"],
        markers=["Gemfile", "Gemfile.lock", "Rakefile"],
        default_test_cmd="bundle exec rspec",
        default_build_cmd="bundle install",
        default_lint_cmd="bundle exec rubocop",
        default_run_cmd="ruby app.rb",
        description="Ruby ecosystem with Bundler dependency isolation and RSpec behaviour-driven test suites."
    ),
    "kotlin": LanguageStack(
        id="kotlin",
        name="Kotlin (JVM / Multiplatform)",
        extensions=[".kt", ".kts"],
        markers=["build.gradle.kts", "settings.gradle.kts"],
        default_test_cmd="./gradlew test",
        default_build_cmd="./gradlew build",
        default_lint_cmd="./gradlew ktlintCheck",
        default_run_cmd="./gradlew run",
        description="Concise, expressive Kotlin development on the JVM with Gradle multi-project builds."
    ),
    "swift": LanguageStack(
        id="swift",
        name="Swift (Swift Package Manager)",
        extensions=[".swift"],
        markers=["Package.swift"],
        default_test_cmd="swift test",
        default_build_cmd="swift build",
        default_lint_cmd="swiftlint",
        default_run_cmd="swift run",
        description="Modern Apple & server-side Swift with Swift Package Manager (SPM)."
    )
}

def get_stack_by_id(stack_id: str) -> Optional[LanguageStack]:
    """Retrieves a stack definition by normalized identifier."""
    if not stack_id:
        return None
    clean = stack_id.lower().strip()
    # Handle aliases
    alias_map = {
        "ts": "typescript",
        "js": "javascript",
        "py": "python",
        "golang": "go",
        "rs": "rust",
        "c++": "cpp",
        "c": "cpp",
        "cs": "csharp",
        "dotnet": "csharp",
        "flutter": "dart",
        "rb": "ruby"
    }
    canonical = alias_map.get(clean, clean)
    return SUPPORTED_STACKS.get(canonical)

def detect_stack_from_workspace(workspace_root: Path) -> LanguageStack:
    """Inspects workspace files and determines the dominant language stack."""
    if not workspace_root.exists():
        return SUPPORTED_STACKS["python"]

    # Check for marker files in priority order
    priority_order = [
        "rust", "go", "typescript", "csharp", "dart", "java", "kotlin", "swift", "cpp", "php", "ruby", "javascript", "python"
    ]

    for s_id in priority_order:
        stack = SUPPORTED_STACKS[s_id]
        for marker in stack.markers:
            if "*" in marker:
                if list(workspace_root.glob(marker)):
                    return stack
            elif (workspace_root / marker).exists():
                return stack

    # Extension frequency fallback
    counts: Dict[str, int] = {}
    for s_id, stack in SUPPORTED_STACKS.items():
        counts[s_id] = 0
        for ext in stack.extensions:
            counts[s_id] += len(list(workspace_root.glob(f"*{ext}")))
            counts[s_id] += len(list(workspace_root.glob(f"src/**/*{ext}")))

    dominant = max(counts.items(), key=lambda x: x[1])
    if dominant[1] > 0:
        return SUPPORTED_STACKS[dominant[0]]

    # Universal standard engineering default
    return SUPPORTED_STACKS["python"]
