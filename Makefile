PYTHON ?= python

.PHONY: test test-lab8 proof run-agent run-planner evaluate-routing compile

test:
	$(PYTHON) -m pytest tests --ignore=tests/test_lab8_planner.py -q

test-lab8:
	$(PYTHON) -m unittest -v tests.test_lab8_planner

proof:
	$(PYTHON) -m scripts.prove_planner_mcp

run-agent:
	$(PYTHON) labs/lab6_todo/agent_todo.py

run-planner:
	$(PYTHON) labs/lab8_langgraph/agent_langgraph.py

evaluate-routing:
	$(PYTHON) scripts/evaluate_skill_routing.py --suite-version semantic-v3 --routing-mode hybrid --progress

compile:
	$(PYTHON) -m compileall -q labs scripts tests
