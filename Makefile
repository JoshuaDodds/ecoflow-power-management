VENV?=.venv
PY?=$(VENV)/bin/python
PIP?=$(VENV)/bin/pip

init:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

run-soc:
	$(PY) -u services/soc_bridge.py

run-policy:
	$(PY) -u services/policy_engine.py

run-agent:
	$(PY) -u agents/host_agent.py
