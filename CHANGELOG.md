## [1.1.0] - 2026-06-21

### 🚀 Features

- Possibility to specify a delay in seconds between several consequent executions of procedure
- Possibility to specify a procedure timeout in seconds

### 🐛 Bug Fixes

- Using default value of configuration parameter if it is missing from bureau operation protocol or procedure protocol JSON files
- Replaced package version reading from deprecated pkg_resources to importlib.metadata (#6)

### 💼 Other

- *(deps)* Bump actions/checkout from 4 to 5 (#1)
- *(deps)* Bump actions/setup-python from 3 to 6 (#2)
- *(deps)* Bump actions/upload-artifact from 4 to 5 (#3)
- *(deps)* Bump actions/checkout from 5 to 6 (#4)
- *(deps)* Bump actions/upload-artifact from 5 to 6 (#5)

### 📚 Documentation

- Docstrings and comments for variables and classes in defines.py
- Docstrings and comments for classes in structures.py

### ⚙️ Miscellaneous Tasks

- Added dependabot.yml configuration
- Added default git-cliff configuration file
- Suppressed pylint broad-except and dropped unused json
- Reordered imports in clerk and bureau classes
- Replaced type() with isinstance()
- Corrected author name
- Added possibility to build kontor package locally under Windows
- Removed deprecated license mention in favor of SPDX license expression
- Removed universal build due to Python 2.7 deprecation
- Increased minimum Python version to 3.8
## [1.0.0] - 2025-09-29

### ⚙️ Miscellaneous Tasks

- Version 1.0.0
- Removed deprecated Python 3.7 version support
