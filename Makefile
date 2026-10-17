MODEL ?= anthropic/claude-haiku-5-5

.PHONY: all dashboard data baseline run consistency test lint

# Everything, in order: labelling first, then the models, then the results.
# Run it again after each step; it picks up where it left off.
all: web/node_modules
	npm --prefix web run build
	uv run petition-router all

web/node_modules: web/package.json web/package-lock.json
	npm --prefix web ci
	@touch web/node_modules

# The labelling and results pages
dashboard: web/node_modules
	npm --prefix web run build
	uv run petition-router serve

# Download the petitions again, for instance to pick up new ones
data:
	uv run petition-router download

# TF-IDF and logistic regression: free, and the score a model has to beat
baseline:
	uv run petition-router run tfidf

# Every petition through a model, e.g. make run MODEL=openai/gpt-5
run:
	uv run petition-router run $(MODEL)

# Ask the same model twice more: once as before, once with the departments listed Z to A
consistency:
	uv run petition-router run $(MODEL)
	uv run petition-router run $(MODEL) --reverse

test: web/node_modules
	uv run pytest
	npm --prefix web test

lint: web/node_modules
	uv run ruff check
	uv run ruff format --check
	npm --prefix web run check
