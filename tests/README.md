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
python3 -m unittest tests.test_config_validation
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

- **test_config_validation.py**: Tests for `utils/config_validator.py`
  - Required environment variable validation
  - MQTT port validation
  - JSON format validation
  - Configuration summary generation

## Test Results

All tests should pass:
```
Ran 15 tests in 0.008s
OK
```
