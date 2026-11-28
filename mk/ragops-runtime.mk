# Member 1 RAGOps Runtime Makefile targets
# Included by root Makefile.

PROFILE ?= rahbar-a03
RUNTIME_TAG ?= $(TAG)

.PHONY: ragops-runtime-images ragops-runtime-load ragops-runtime-apply ragops-runtime-test

ragops-runtime-images: ## build Member 1 runtime images (api + indexer with ragops)
	docker build -t rahbar-api:$(RUNTIME_TAG) api
	docker build -f indexer/Dockerfile --build-arg CORPUS_SRC=$(CORPUS_SRC) -t rahbar-indexer:$(RUNTIME_TAG) .
	docker build -t rahbar-ui:$(RUNTIME_TAG) ui

ragops-runtime-load: ## load Member 1 runtime images into minikube profile
	minikube -p $(PROFILE) image load rahbar-api:$(RUNTIME_TAG)
	minikube -p $(PROFILE) image load rahbar-indexer:$(RUNTIME_TAG)
	minikube -p $(PROFILE) image load rahbar-ui:$(RUNTIME_TAG)

ragops-runtime-apply: ## apply runtime kustomization and helper shell pod
	kubectl apply -k k8s/ragops-runtime
	kubectl apply -f k8s/tools/runtime-shell.yaml

ragops-runtime-test: ## run Member 1 offline runtime unit tests
	"$(BIN)/pytest" tests/ragops/runtime -v
