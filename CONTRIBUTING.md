# Contributing to HeadlineImageSelector

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/HeadlineImageSelector.git`
3. Create a virtual environment: `python3 -m venv venv && source venv/bin/activate`
4. Install development dependencies: `pip install -e ".[dev]"`

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run tests: `pytest tests/`
4. Format code: `black src/`
5. Lint: `ruff src/`
6. Commit with descriptive messages
7. Push to your fork
8. Open a pull request

## Code Style

- Follow PEP 8 guidelines
- Use Black for formatting (line length: 100)
- Add docstrings to all public functions and classes
- Keep functions focused and single-purpose

## Testing

- Write tests for new features
- Ensure all tests pass before submitting PR
- Aim for >80% code coverage

## Pull Request Process

1. Update README.md if adding features
2. Add your changes to the relevant section
3. Ensure CI passes
4. Request review from maintainers

## Questions?

Open a GitHub Discussion or issue for any questions.
