# Contributing to LPS2

Thank you for considering contributing to LPS2! This document provides comprehensive guidelines and instructions to make the contribution process smooth and effective.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
  - [Development Environment Setup](#development-environment-setup)
  - [Project Structure](#project-structure)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Pull Requests](#pull-requests)
- [Development Workflow](#development-workflow)
  - [Branching Strategy](#branching-strategy)
  - [Commit Messages](#commit-messages)
  - [Code Review Process](#code-review-process)
- [Coding Standards](#coding-standards)
  - [Python Conventions](#python-conventions)
  - [JavaScript Conventions](#javascript-conventions)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Security Considerations](#security-considerations)
- [License](#license)
- [Getting Help](#getting-help)

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

## Getting Started

### Development Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/LPS2.git
   cd LPS2
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   - Copy `ENV_EXAMPLE.txt` to `.env`
   - Update the values in `.env` with your specific configuration

5. **Start the development server**
   ```bash
   ./scripts/run_dev.sh
   ```

### Project Structure

- `src/app.py`: Main application entry point
- `src/config.py`: Configuration management
- `src/routes/`: API endpoints
- `src/static/`: Frontend assets
- `src/utils/`: Utility functions and modules
- `scripts/`: Development and deployment scripts
- `dev_certs/`: Development certificates

## How to Contribute

### Reporting Bugs

Before reporting a bug, please:
- Check the [issue tracker](https://github.com/yourusername/LPS2/issues) to see if the issue has already been reported.
- Use the provided bug report template and fill out all the required information.
- Provide a clear, concise description of the issue.
- Include steps to reproduce the bug.
- Specify the environment (OS, browser, Python version).
- Include screenshots if applicable.

### Suggesting Enhancements

We welcome suggestions for enhancing LPS2. To suggest an enhancement:
- Check if the enhancement has already been suggested in the issue tracker.
- Use the provided feature request template.
- Clearly describe the feature and its benefits.
- Provide examples of how the feature would be used.

### Pull Requests

To submit a pull request:
1. Fork the repository.
2. Create a branch following our [branching strategy](#branching-strategy).
3. Make your changes.
4. Ensure your code passes all tests.
5. Submit a pull request using our PR template.
6. Update the PR with any requested changes from reviewers.

## Development Workflow

### Branching Strategy

We follow a simplified GitFlow workflow:
- `main`: Production-ready code
- `develop`: Latest development changes
- Feature branches: `feature/description-of-feature`
- Bug fix branches: `fix/issue-number-description`
- Release branches: `release/version-number`

### Commit Messages

Follow these guidelines for commit messages:
- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests after the first line
- Structure your commit message like this:
  ```
  [type]: Short summary (72 chars or less)

  More detailed explanatory text, if necessary.

  Resolves: #123
  ```
  Where `type` can be: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, or `chore`

### Code Review Process

All submissions require review. We use GitHub pull requests for this purpose:
1. Submit a pull request with a clear title and description.
2. Wait for maintainers to review your PR.
3. Address any requested changes.
4. Once approved, a maintainer will merge your PR.
5. Your contribution will be part of the next release.

## Coding Standards

### Python Conventions

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guidelines
- Use type hints for function parameters and return values
- Document all functions, classes, and modules using docstrings
- Organize imports in the following order:
  - Standard library imports
  - Related third-party imports
  - Local application imports
- Maximum line length: 100 characters
- Use descriptive variable names

Example:
```python
import os
from typing import Dict, List, Optional

import requests

from utils.security_utils import sanitize_input


def process_data(input_data: Dict[str, any], options: Optional[List[str]] = None) -> Dict[str, any]:
    """
    Process the input data according to specified options.
    
    Args:
        input_data: Dictionary containing input data
        options: Optional list of processing options
        
    Returns:
        Dict containing processed data
    """
    # Implementation
    return processed_data
```

### JavaScript Conventions

- Follow [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript)
- Use ES6+ features where appropriate
- Use camelCase for variables and functions
- Use PascalCase for classes and components
- Use descriptive variable names
- Add JSDoc comments for functions

Example:
```javascript
/**
 * Fetches user data from the API
 * @param {number} userId - The ID of the user
 * @returns {Promise<Object>} User data object
 */
async function fetchUserData(userId) {
  try {
    const response = await fetch(`/api/users/${userId}`);
    return await response.json();
  } catch (error) {
    console.error('Error fetching user data:', error);
    throw error;
  }
}
```

## Testing Guidelines

- Write unit tests for all new features and bug fixes
- Aim for at least 80% code coverage
- Test both success and failure cases
- Use descriptive test names that explain what's being tested
- Structure tests using the Arrange-Act-Assert pattern

Example:
```python
import unittest
from utils.security_utils import validate_password


class TestSecurityUtils(unittest.TestCase):
    def test_validate_password_with_valid_password(self):
        # Arrange
        valid_password = "Secure123!"
        
        # Act
        result = validate_password(valid_password)
        
        # Assert
        self.assertTrue(result)
        
    def test_validate_password_with_too_short_password(self):
        # Arrange
        short_password = "Sh0rt!"
        
        # Act
        result = validate_password(short_password)
        
        # Assert
        self.assertFalse(result)
```

Run tests before submitting a PR:
```bash
python -m unittest discover tests
```

## Documentation

Good documentation is essential to LPS2's usability:

- Document all public APIs, classes, and functions
- Update the README.md when adding new features
- Add examples for complex functionality
- Keep documentation up-to-date with code changes
- Use clear, concise language

## Security Considerations

Security is a priority for LPS2:

- Never commit sensitive data (tokens, passwords, etc.)
- Always sanitize user inputs
- Follow the principle of least privilege
- Use parameterized queries to prevent SQL injection
- Validate and sanitize all data from external sources
- Report security vulnerabilities privately to the maintainers

Run security checks before submitting:
```bash
./scripts/vuln_scan.sh
```

## License

By contributing to LPS2, you agree that your contributions will be licensed under the project's license. All new files should include the appropriate license header.

## Getting Help

If you need help with contributing:
- Join our community discussion on [Discord/Slack]
- Ask questions in the GitHub Discussions section
- Contact the maintainers via email at [email address]

Thank you for contributing to LPS2!

## How to Contribute

### Reporting Bugs

If you find a bug in the project:

1. Check if the bug has already been reported in the [Issues](https://github.com/guerilla7/LPS2/issues).
2. If not, open a new issue with a clear title and description.
3. Include steps to reproduce the bug, expected behavior, and actual behavior.
4. If possible, add screenshots, logs, or other relevant information.

### Suggesting Enhancements

If you have ideas for new features or improvements:

1. Check if the enhancement has already been suggested in the [Issues](https://github.com/guerilla7/LPS2/issues).
2. If not, open a new issue with a clear title and description.
3. Explain why this enhancement would be useful to most LPS2 users.
4. Outline how the enhancement might be implemented.

### Pull Requests

1. Fork the repository and create a new branch from `main`.
2. Make your changes in the new branch.
3. Add or update tests as necessary.
4. Ensure your code follows the project's coding standards.
5. Ensure all tests pass.
6. Submit a pull request to the `main` branch.

## Development Setup

### Prerequisites

- Python 3.8+
- pip
- Docker (optional, for containerized development)

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/guerilla7/LPS2.git
   cd LPS2
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Run the development server:
   ```bash
   ./scripts/run_dev.sh
   ```

4. Visit http://localhost:5000 in your browser.

### Testing

Run the tests with:
```bash
pytest
```

## Coding Standards

- Follow PEP 8 guidelines for Python code.
- Write docstrings for all functions, classes, and modules.
- Include type hints where appropriate.
- Keep code modular and maintainable.
- Write tests for new features and bug fixes.

## Documentation

- Update documentation when making changes to the API, CLI, or configuration.
- Use clear, concise language.
- Include examples where helpful.

## License

By contributing to LPS2, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).

## Questions?

If you have any questions or need help, feel free to reach out to the maintainers or open an issue.

Thank you for contributing to LPS2!