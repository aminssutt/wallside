# ragscale - research harness. `make help` lists targets.
# Native runs use uv (fast on Apple Silicon: MPS for local models); `make docker-*` runs the same in Docker.

UV ?= uv
RUN := $(UV) run ragscale
COMPOSE := docker compose -f docker-compose.yml
LOCAL_MODELS ?= bge-m3 multilingual-e5-large-instruct

.PHONY: help install install-local test corpus embed embed-ctx dataset smoke dev e1 e2 e3 prod-replica analyze docker-build docker-test docker-run

help:
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | column -t -s "$$(printf '\t')"

install: ## Install the harness (API + lexical + analysis)
	$(UV) sync --extra dev

install-local: ## Also install local neural models (torch, sentence-transformers, FlagEmbedding)
	$(UV) sync --extra dev --extra local

test: ## Unit tests (no data, no API)
	$(UV) run pytest -q

corpus: ## Extract chunks + Gemini vectors from backend/data/guides
	$(RUN) corpus

embed: ## Encode the corpus with local embedding models (resumable)
	$(RUN) embed $(LOCAL_MODELS)

embed-ctx: ## Encode chunks with contextual headers (bge-m3+ctx)
	$(RUN) embed bge-m3+ctx

dataset: ## Generate the gold question set (Gemini API)
	$(RUN) dataset --name questions_v1

smoke: ## 40-question end-to-end check, API-free
	$(RUN) run configs/smoke.yaml --overwrite && $(RUN) analyze smoke

dev: ## Development runs on the dev split
	$(RUN) run configs/dev_lexical.yaml && $(RUN) analyze dev_lexical

e1: ## E1 corpus-size scaling
	$(RUN) run configs/e1_scaling.yaml && $(RUN) analyze e1_scaling

e2: ## E2 technique comparison at full scale
	$(RUN) run configs/e2_techniques.yaml && $(RUN) analyze e2_techniques

prod-replica: ## Production retrieval code on the gold set (backend venv + Gemini API)
	../backend/.venv/bin/python scripts/prod_replica.py --variants native_plain native_model
	$(RUN) import-prod

analyze: ## make analyze NAME=<run>
	$(RUN) analyze $(NAME)

docker-build: ## Build the research image
	$(COMPOSE) build

docker-test: ## Unit tests inside Docker
	$(COMPOSE) run --rm --entrypoint pytest ragscale -q

docker-run: ## make docker-run CONFIG=configs/e1_scaling.yaml
	$(COMPOSE) run --rm ragscale run $(CONFIG)
