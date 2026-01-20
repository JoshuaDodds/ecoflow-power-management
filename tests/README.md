# Tests

Unit tests for the EcoFlow Power Management system.

## Running Tests

Run all tests:
```bash
python3 -m unittest discover tests
```

Run specific test file:
```bash
python3 -m unittest tests.test_env_loader
python3 -m unittest tests.test_policy_engine
```

Run with verbose output:
```bash
python3 -m unittest discover tests -v
```

## Test Coverage

- **test_env_loader.py**: Tests for `utils/env_loader.py`
  - Multi-line value parsing
  - Single-line value parsing
  - Empty value handling
  
- **test_policy_engine.py**: Tests for `services/policy_engine.py`
  - Attribute initialization
  - JSON configuration parsing
  - Error handling
  - The fix for: `'PolicyEngine' object has no attribute 'agent_shutdown_delay'`
