# Contributing to Clawdfolio

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/YichengYang-Ethan/clawdfolio.git
cd clawdfolio
pip install -e ".[dev]"
pre-commit install
```

## Workflow

1. **Open an issue first** to discuss the change you'd like to make
2. Fork the repository and create a branch from `main`
3. Write code and add tests for any new functionality
4. Ensure all checks pass:
   ```bash
   ruff check src/ tests/
   mypy src/clawdfolio --ignore-missing-imports
   pytest tests/ -v
   ```
5. Submit a pull request

## Code Style

- **Formatter**: [Ruff](https://github.com/astral-sh/ruff) (line length 88)
- **Type hints**: Required for all public functions
- **Docstrings**: Google style for public APIs
- Pre-commit hooks enforce formatting automatically

## Testing

- Tests live in `tests/` and use pytest
- Run `pytest tests/ -v --cov=src/clawdfolio` for coverage
- New features should include corresponding tests

## Commit Messages

Use concise, imperative-mood messages:
- `fix: resolve RSI calculation edge case`
- `feat: add options chain filtering`
- `docs: update CLI usage examples`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
