

# General Code Review Standards

## Code Quality Essentials

- Functions should be focused and appropriately sized
- Use clear, descriptive naming conventions
- Ensure proper error handling throughout
- Remove dead code and unused imports


## Review Style

- Be specific and actionable in feedback
- Explain the "why" behind recommendations
- Acknowledge good patterns when you see them
- Ask clarifying questions when code intent is unclear


## Security Standards

- Never hardcode credentials or API keys
- Validate all user inputs
- Use parameterized queries to prevent SQL injection

## Documentation Expectations

- All public functions must include doc comments
- Complex algorithms should have explanatory comments
- README files must be kept up to date

## Naming Conventions

Use descriptive, intention-revealing names.

```javascript
// Avoid
const d = new Date();
const x = users.filter(u => u.active);

// Prefer
const currentDate = new Date();
const activeUsers = users.filter(user => user.isActive);
```

## Error Handling

Always handle errors gracefully and provide meaningful messages.


```javascript
try {
const data = await fetchData();
} catch (error) {
  console.error('Failed to fetch data:', error);
}
```


## Code Formatting

- Use consistent indentation (e.g., 2 or 4 spaces)
- Limit line length to 80-120 characters  
- Use blank lines to separate logical sections of code


```javascript
function calculateTotal(items) {
  let total = 0;

  items.forEach(item => {
    total += item.price * item.quantity;
  });

  return total;
}
```


## Testing Standards

- Write unit tests for all new features
- Use descriptive test names  
- Tests should cover edge cases and error conditions
- Test names should clearly describe what they test


```javascript
test('should calculate total price correctly', () => {
  const items = [
    { price: 10, quantity: 2 },
    { price: 5, quantity: 3 }
  ];
  expect(calculateTotal(items)).toBe(35);
});
```
