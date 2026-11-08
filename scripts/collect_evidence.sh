#!/usr/bin/env bash
# ==============================================================================
# scripts/collect_evidence.sh
# Automated Evidence Collection Script for Track A (Platform & Delivery)
# CS4032 Assignment 02 - RAHBAR: Grounded RAG on Kubernetes
# ==============================================================================
set -euo pipefail

NAMESPACE="rahbar"
EVIDENCE_DIR="docs/evidence"
mkdir -p "${EVIDENCE_DIR}"

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RESET="\033[0m"

log_info() {
    echo -e "${CYAN}[INFO]${RESET} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${RESET} $1"
}

log_section() {
    echo -e "\n${BOLD}${YELLOW}=== $1 ===${RESET}"
}

# ------------------------------------------------------------------------------
# 1. Endpoints: Scale API to 5 and capture 5 IPs
# ------------------------------------------------------------------------------
capture_endpoints() {
    log_section "1. Capturing Endpoints (5 replicas)"
    log_info "Scaling deployment/api to 5 replicas..."
    kubectl scale deployment/api --replicas=5 -n "${NAMESPACE}"
    kubectl rollout status deployment/api -n "${NAMESPACE}" --timeout=90s

    log_info "Writing endpoints output to ${EVIDENCE_DIR}/get-endpoints.txt..."
    kubectl get endpoints api -n "${NAMESPACE}" -o wide | tee "${EVIDENCE_DIR}/get-endpoints.txt"

    log_info "Scaling deployment/api back to 3 replicas..."
    kubectl scale deployment/api --replicas=3 -n "${NAMESPACE}"
    kubectl rollout status deployment/api -n "${NAMESPACE}" --timeout=90s
    log_success "Endpoints evidence captured successfully!"
}

# ------------------------------------------------------------------------------
# 2. HPA: Horizontal Pod Autoscaler status & numeric target
# ------------------------------------------------------------------------------
capture_hpa() {
    log_section "2. Capturing HPA Status"
    log_info "Writing HPA output to ${EVIDENCE_DIR}/get-hpa.txt..."
    kubectl get hpa api-hpa -n "${NAMESPACE}" | tee "${EVIDENCE_DIR}/get-hpa.txt"
    log_success "HPA evidence captured successfully!"
}

# ------------------------------------------------------------------------------
# 3. Rollout & Rollout Undo
# ------------------------------------------------------------------------------
capture_rollout() {
    log_section "3. Testing Deployment Rollout and Rollback"
    ORIGINAL_IMAGE=$(kubectl get deployment/api -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].image}')
    log_info "Current active image: ${ORIGINAL_IMAGE}"

    TMP_LOG="${EVIDENCE_DIR}/rollout-undo.txt"
    echo "# Rollout and Rollout Undo Evidence" > "${TMP_LOG}"
    echo "# Initial Image: ${ORIGINAL_IMAGE}" >> "${TMP_LOG}"

    log_info "Updating deployment image to test tag rahbar-api:v2-test..."
    kubectl set image deployment/api api=rahbar-api:v2-test -n "${NAMESPACE}"
    echo -e "\n--- Rollout Status for v2-test ---" >> "${TMP_LOG}"
    kubectl rollout status deployment/api -n "${NAMESPACE}" --timeout=20s >> "${TMP_LOG}" 2>&1 || true

    echo -e "\n--- Deployment History ---" >> "${TMP_LOG}"
    kubectl rollout history deployment/api -n "${NAMESPACE}" >> "${TMP_LOG}"

    log_info "Rolling back deployment to previous revision..."
    kubectl rollout undo deployment/api -n "${NAMESPACE}"
    echo -e "\n--- Rollout Status after Undo ---" >> "${TMP_LOG}"
    kubectl rollout status deployment/api -n "${NAMESPACE}" --timeout=60s >> "${TMP_LOG}"

    RESTORED_IMAGE=$(kubectl get deployment/api -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].image}')
    echo -e "\n--- Restored Image ---" >> "${TMP_LOG}"
    echo "Active image after undo: ${RESTORED_IMAGE}" >> "${TMP_LOG}"
    cat "${TMP_LOG}"
    log_success "Rollout and undo evidence captured in ${TMP_LOG}!"
}

# ------------------------------------------------------------------------------
# 4. Pod Resource Utilization (kubectl top pods) under load
# ------------------------------------------------------------------------------
capture_top() {
    log_section "4. Capturing Pod Resource Metrics (kubectl top)"
    log_info "Starting synthetic traffic load on API..."
    
    # Run a quick background loop hitting /healthz to generate active requests
    (
        for _ in $(seq 1 40); do
            kubectl exec -n "${NAMESPACE}" deploy/ui -- wget -qO- http://api:8000/healthz > /dev/null 2>&1 || true
            sleep 0.1
        done
    ) &
    LOAD_PID=$!

    # Trigger a reindex Job to show indexer under load
    log_info "Triggering manual reindex job for load measurement..."
    kubectl delete job load-indexer-top -n "${NAMESPACE}" --ignore-not-found=true > /dev/null 2>&1 || true
    kubectl create job --from=cronjob/reindex load-indexer-top -n "${NAMESPACE}" > /dev/null 2>&1 || true

    sleep 3
    log_info "Collecting kubectl top pods -n ${NAMESPACE}..."
    kubectl top pods -n "${NAMESPACE}" | tee "${EVIDENCE_DIR}/kubectl-top.txt"

    wait "${LOAD_PID}" || true
    kubectl delete job load-indexer-top -n "${NAMESPACE}" --ignore-not-found=true > /dev/null 2>&1 || true
    log_success "Resource utilization evidence captured!"
}

# ------------------------------------------------------------------------------
# 5. Pod Deletion Zero-Downtime Verification
# ------------------------------------------------------------------------------
capture_pod_delete() {
    log_section "5. Zero-Downtime Pod Deletion Test"
    TARGET_POD=$(kubectl get pods -n "${NAMESPACE}" -l app=rahbar-api -o jsonpath='{.items[0].metadata.name}')
    log_info "Selected target pod for deletion: ${TARGET_POD}"

    TMP_LOG="${EVIDENCE_DIR}/pod-delete-zero-downtime.txt"
    echo "# Zero-Downtime Verification: Deleting API Pod under traffic" > "${TMP_LOG}"
    echo "Deleting pod: ${TARGET_POD}" >> "${TMP_LOG}"

    # Query continuously while deleting the pod
    (
        SUCCESSES=0
        FAILURES=0
        for i in $(seq 1 30); do
            HTTP_CODE=$(kubectl exec -n "${NAMESPACE}" deploy/ui -- wget -S -qO- http://api:8000/healthz 2>&1 | awk '/HTTP\// {print $2}' | tail -n 1)
            if [ "${HTTP_CODE}" = "200" ]; then
                SUCCESSES=$((SUCCESSES + 1))
            else
                FAILURES=$((FAILURES + 1))
            fi
            sleep 0.2
        done
        echo "Results during pod churn: ${SUCCESSES} successes (HTTP 200), ${FAILURES} failures" >> "${TMP_LOG}"
    ) &
    PROBE_PID=$!

    sleep 1
    log_info "Deleting pod ${TARGET_POD}..."
    kubectl delete pod "${TARGET_POD}" -n "${NAMESPACE}" --wait=false

    wait "${PROBE_PID}"
    cat "${TMP_LOG}"
    log_success "Zero-downtime test completed!"
}

# ------------------------------------------------------------------------------
# Main Dispatcher
# ------------------------------------------------------------------------------
case "${1:-all}" in
    endpoints)
        capture_endpoints
        ;;
    hpa)
        capture_hpa
        ;;
    rollout)
        capture_rollout
        ;;
    top)
        capture_top
        ;;
    pod-delete)
        capture_pod_delete
        ;;
    all)
        capture_endpoints
        capture_hpa
        capture_rollout
        capture_top
        capture_pod_delete
        echo -e "\n${GREEN}${BOLD}All automated evidence captures completed!${RESET}"
        ;;
    *)
        echo "Usage: $0 [all|endpoints|hpa|rollout|top|pod-delete]"
        exit 1
        ;;
esac

