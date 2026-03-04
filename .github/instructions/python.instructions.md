---
applyTo: "**/*.py"
---

# Python Coding Conventions

## Naming Conventions

- Use snake_case for variables and functions
- Use PascalCase for class names
- Use UPPERCASE for constants

## Code Style

- Follow PEP 8 style guidelines
- Limit line length to 88 characters (Black formatter standard)
- Use type hints for function signatures

## Best Practices

- Use list comprehensions for simple transformations
- Prefer f-strings for string formatting
- Use context managers (with statements) for resource management

```python
# Avoid
file = open('data.txt')
content = file.read()
file.close()

# Prefer
with open('data.txt') as file:
    content = file.read()
```