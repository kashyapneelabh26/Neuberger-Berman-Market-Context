.PHONY: install run run-crewai run-langchain test
install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
run:
	. .venv/bin/activate && export AGENT_BACKEND=none && export MOCK=true && uvicorn app.main:app --reload
run-crewai:
	. .venv/bin/activate && export AGENT_BACKEND=crewai && export MOCK=false && uvicorn app.main:app --reload
run-langchain:
	. .venv/bin/activate && export AGENT_BACKEND=langchain && export MOCK=false && uvicorn app.main:app --reload
run-langgraph:
	. .venv/bin/activate && export AGENT_BACKEND=langgraph && export MOCK=false && uvicorn app.main:app --reload
test:
	. .venv/bin/activate && pytest -q
