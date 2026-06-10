#!/bin/bash
set -e

echo "================================================"
echo "  NovaPay Demo Environment Setup"
echo "  Datadog APJ Royal Rumble 2026"
echo "================================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

# ---------------------------------------------------------------------------
# Check prerequisites
# ---------------------------------------------------------------------------
info "Checking prerequisites..."
command -v docker    &>/dev/null || error "Docker is required.    Install: https://docs.docker.com/get-docker/"
command -v minikube  &>/dev/null || error "Minikube is required.  Install: https://minikube.sigs.k8s.io/docs/start/"
command -v kubectl   &>/dev/null || error "kubectl is required.   Install: https://kubernetes.io/docs/tasks/tools/"
command -v helm      &>/dev/null || error "Helm is required.      Install: https://helm.sh/docs/intro/install/"
command -v python3   &>/dev/null || error "Python 3 is required.  Install: https://www.python.org/downloads/"
log "All prerequisites found"

# ---------------------------------------------------------------------------
# Datadog API Key
# ---------------------------------------------------------------------------
if [ -z "$DD_API_KEY" ]; then
    echo ""
    warn "DD_API_KEY environment variable is not set."
    read -rp "Enter your Datadog API Key: " DD_API_KEY
    export DD_API_KEY
fi

if [ -z "$DD_API_KEY" ]; then
    error "DD_API_KEY is required to continue."
fi

# ---------------------------------------------------------------------------
# Step 1: Start minikube
# ---------------------------------------------------------------------------
info "Starting minikube..."
if minikube status &>/dev/null; then
    log "Minikube already running"
else
    minikube start --cpus=4 --memory=8192 --driver=docker
    log "Minikube started"
fi

# ---------------------------------------------------------------------------
# Step 2: Enable addons
# ---------------------------------------------------------------------------
info "Enabling minikube addons..."
minikube addons enable metrics-server 2>/dev/null || true
log "Addons enabled"

# ---------------------------------------------------------------------------
# Step 3: Install Datadog Agent via Helm
# ---------------------------------------------------------------------------
info "Installing Datadog Agent via Helm..."
helm repo add datadog https://helm.datadoghq.com 2>/dev/null || true
helm repo update

kubectl create namespace novapay  2>/dev/null || warn "Namespace novapay already exists"
kubectl create namespace datadog  2>/dev/null || warn "Namespace datadog already exists"

kubectl create secret generic datadog-secret \
    --namespace datadog \
    --from-literal api-key="$DD_API_KEY" \
    2>/dev/null || kubectl patch secret datadog-secret \
        --namespace datadog \
        --type='json' \
        -p="[{\"op\":\"replace\",\"path\":\"/data/api-key\",\"value\":\"$(echo -n "$DD_API_KEY" | base64)\"}]"

helm upgrade --install datadog-agent datadog/datadog \
    --namespace datadog \
    --values k8s/datadog/datadog-values.yaml \
    --set datadog.apiKeyExistingSecret=datadog-secret \
    --set datadog.clusterName=novapay-demo-local \
    --wait --timeout=120s

log "Datadog Agent installed"

# ---------------------------------------------------------------------------
# Step 4: Build Docker images inside minikube's Docker daemon
# ---------------------------------------------------------------------------
info "Building NovaPay service images (inside minikube Docker)..."
eval "$(minikube docker-env)"

docker build -t novapay-payments:latest services/payments/ && log "payments image built"
docker build -t novapay-fraud:latest     services/fraud/    && log "fraud image built"
docker build -t novapay-lending:latest   services/lending/  && log "lending image built"

# ---------------------------------------------------------------------------
# Step 5: Deploy services to Kubernetes
# ---------------------------------------------------------------------------
info "Deploying NovaPay services to Kubernetes..."
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/payments/
kubectl apply -f k8s/fraud/
kubectl apply -f k8s/lending/

info "Waiting for rollouts to complete..."
kubectl rollout status deployment/novapay-payments -n novapay --timeout=120s
kubectl rollout status deployment/novapay-fraud    -n novapay --timeout=120s
kubectl rollout status deployment/novapay-lending  -n novapay --timeout=120s
log "All services deployed"

# ---------------------------------------------------------------------------
# Step 6: Port forwarding (background)
# ---------------------------------------------------------------------------
info "Setting up port forwarding (background processes)..."
pkill -f "kubectl port-forward" 2>/dev/null || true
sleep 1

kubectl port-forward svc/novapay-payments 8001:8001 -n novapay &>/dev/null &
kubectl port-forward svc/novapay-fraud    8003:8003 -n novapay &>/dev/null &
kubectl port-forward svc/novapay-lending  8002:8002 -n novapay &>/dev/null &
log "Port forwarding active (PIDs stored; kill with: pkill -f 'kubectl port-forward')"

# ---------------------------------------------------------------------------
# Step 7: Verify services
# ---------------------------------------------------------------------------
info "Verifying services (waiting 8s for port-forward to stabilise)..."
sleep 8

check_service() {
    local name=$1
    local url=$2
    if curl -sf "$url" >/dev/null 2>&1; then
        log "$name is healthy"
    else
        warn "$name not yet ready — try: curl $url"
    fi
}

check_service "Payments service" "http://localhost:8001/health"
check_service "Fraud service"    "http://localhost:8003/health"
check_service "Lending service"  "http://localhost:8002/health"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "================================================"
echo "  NovaPay Demo Environment Ready!"
echo "  Datadog APJ Royal Rumble 2026"
echo "================================================"
echo ""
echo "  Service URLs:"
echo "    Payments:  http://localhost:8001"
echo "    Fraud:     http://localhost:8003"
echo "    Lending:   http://localhost:8002"
echo ""
echo "  Swagger / OpenAPI Docs:"
echo "    http://localhost:8001/docs"
echo "    http://localhost:8003/docs"
echo "    http://localhost:8002/docs"
echo ""
echo "  Datadog:"
echo "    APM Services:   https://app.datadoghq.com/apm/services"
echo "    CI Visibility:  https://app.datadoghq.com/ci/test-runs"
echo "    Dashboards:     https://app.datadoghq.com/dashboard/lists"
echo ""
echo "  Start traffic generator:"
echo "    python3 scripts/generate_traffic.py"
echo ""
echo "  Run tests with CI Visibility:"
echo "    cd services/payments && pytest --ddtrace --cov=app -v tests/"
echo "    cd services/fraud    && pytest --ddtrace --cov=app -v tests/"
echo "    cd services/lending  && pytest --ddtrace --cov=app -v tests/"
echo ""
echo "  Stop port forwarding:"
echo "    pkill -f 'kubectl port-forward'"
echo ""
