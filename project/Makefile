CLUSTER     := dlb
K3D_SERVERS := 1
K3D_AGENTS  := 2
CONTEXT     := k3d-$(CLUSTER)
NS          := dlb
IMAGE       := dlb-worker:latest

.PHONY: all setup deploy build import undeploy test experiments fault results clean help

all: setup deploy

define require_tool
	@command -v $(1) >/dev/null 2>&1 || { \
		echo "ERROR: Missing required tool '$(1)'."; \
		echo "Install it from the README prerequisites and re-run."; \
		exit 1; \
	}
endef

check-setup-tools:
	$(call require_tool,k3d)
	$(call require_tool,kubectl)
	$(call require_tool,helm)

check-build-tools:
	$(call require_tool,docker)

check-import-tools: check-build-tools
	$(call require_tool,k3d)

check-deploy-tools:
	$(call require_tool,kubectl)

check-test-tools:
	$(call require_tool,kubectl)
	$(call require_tool,k6)

## ── Cluster ──────────────────────────────────────────────────────────────────

setup: check-setup-tools
	@echo "==> Creating k3d cluster '$(CLUSTER)'"
	k3d cluster create $(CLUSTER) \
	  --servers $(K3D_SERVERS) \
	  --agents  $(K3D_AGENTS) \
	  --port    "8080:80@loadbalancer" \
	  --k3s-arg "--disable=traefik@server:*"
	@echo "==> Installing kube-prometheus-stack"
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
	helm repo update
	helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
	  --namespace monitoring --create-namespace \
	  --set grafana.adminPassword=admin \
	  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false \
	  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
	@echo "==> Waiting for monitoring stack to be ready"
	kubectl -n monitoring rollout status deployment/monitoring-grafana --timeout=180s
	@echo "==> Setup complete"

clean:
	@echo "==> Deleting k3d cluster '$(CLUSTER)'"
	k3d cluster delete $(CLUSTER)

## ── Build & Deploy ───────────────────────────────────────────────────────────

build: check-build-tools
	@echo "==> Building worker image"
	docker build -t $(IMAGE) worker/

import: check-import-tools build
	@echo "==> Importing image into k3d"
	k3d image import $(IMAGE) -c $(CLUSTER)

deploy: check-deploy-tools import
	@echo "==> Applying k8s manifests"
	kubectl apply -f k8s/00-namespace.yaml            --context $(CONTEXT)
	kubectl apply -f k8s/10-worker-deploy.yaml         --context $(CONTEXT)
	kubectl apply -f k8s/11-worker-slow-deploy.yaml    --context $(CONTEXT)
	kubectl apply -f k8s/20-worker-svc.yaml            --context $(CONTEXT)
	kubectl apply -f k8s/43-envoy-config-rr.yaml       --context $(CONTEXT)
	kubectl apply -f k8s/41-envoy-deploy.yaml          --context $(CONTEXT)
	kubectl apply -f k8s/42-envoy-svc.yaml             --context $(CONTEXT)
	kubectl apply -f k8s/50-envoy-servicemonitor.yaml  --context $(CONTEXT)
	kubectl apply -f k8s/51-worker-servicemonitor.yaml --context $(CONTEXT)
	kubectl apply -f k8s/61-prometheus-rules.yaml      --context $(CONTEXT)
	@echo "==> Waiting for workers to be ready"
	kubectl -n $(NS) rollout status deployment/dlb-worker      --timeout=120s --context $(CONTEXT)
	kubectl -n $(NS) rollout status deployment/dlb-worker-slow --timeout=120s --context $(CONTEXT)
	kubectl -n $(NS) rollout status deployment/dlb-envoy       --timeout=60s  --context $(CONTEXT)
	@echo "==> Deploy complete. Run 'make test' to verify."

undeploy:
	kubectl delete namespace $(NS) --context $(CONTEXT) --ignore-not-found

## ── HPA (optional extension) ─────────────────────────────────────────────────

hpa:
	kubectl apply -f k8s/60-hpa.yaml --context $(CONTEXT)

## ── Grafana ───────────────────────────────────────────────────────────────────

grafana-password:
	@kubectl -n monitoring get secret monitoring-grafana \
	  -o jsonpath="{.data.admin-password}" --context $(CONTEXT) | base64 --decode
	@echo ""

grafana-port-forward:
	kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80 --context $(CONTEXT)

## ── Testing & Experiments ────────────────────────────────────────────────────

test: check-test-tools
	@echo "==> Running quick sanity test (20s)"
	bash quick-test.sh

experiments: check-test-tools
	@echo "==> Running full experiment suite (all policies × all scenarios)"
	@mkdir -p results
	bash experiments/run_all.sh

fault: check-test-tools
	@echo "==> Running fault injection for all policies"
	@mkdir -p results
	@for policy in rr least-request ring-hash maglev; do \
	  bash experiments/fault_injection.sh $$policy; \
	done

## ── Analysis ──────────────────────────────────────────────────────────────────

results:
	@echo "==> Generating figures and tables"
	@cd analysis && python3 -m pip install -q -r requirements.txt
	python3 analysis/plot_results.py
	python3 analysis/summary_table.py
	@echo "==> Outputs in results/"

## ── Info ──────────────────────────────────────────────────────────────────────

status:
	@echo "=== Cluster ==="
	kubectl get nodes --context $(CONTEXT)
	@echo ""
	@echo "=== DLB pods ==="
	kubectl -n $(NS) get pods -o wide --context $(CONTEXT)
	@echo ""
	@echo "=== Services ==="
	kubectl -n $(NS) get svc --context $(CONTEXT)

help:
	@echo "Targets:"
	@echo "  make setup        Create k3d cluster and install Prometheus/Grafana"
	@echo "  make deploy       Build worker image, import into k3d, apply manifests"
	@echo "  make test         20-second sanity load test"
	@echo "  make experiments  Full experiment suite (all policies × scenarios)"
	@echo "  make fault        Fault injection for all policies"
	@echo "  make results      Generate figures and LaTeX/Markdown tables"
	@echo "  make hpa          Apply HorizontalPodAutoscaler (optional)"
	@echo "  make status       Show cluster and pod status"
	@echo "  make clean        Delete the k3d cluster"
