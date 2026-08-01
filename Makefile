PYTHON ?= python

.PHONY: test test-lab8 proof run-agent run-planner evaluate-routing replay-v2-incidents replay-v2-questions compile

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

replay-v2-incidents:
	$(PYTHON) scripts/replay_v2_incidents.py --progress

replay-v2-questions:
	$(PYTHON) scripts/replay_v2_questions.py --manifest tests/evaluation/v2_full_question_replay.json --output artifacts/v2_full_question_replay_v3_run.json

compile:
	$(PYTHON) -m compileall -q labs scripts tests
