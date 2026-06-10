# NovaPay Demo Environment — Setup Guide

**Datadog APJ Royal Rumble 2026 — Quality Engineering / Shift-Left Demo**

NovaPay is a fictional fintech platform processing 3M+ transactions/day across South-East Asia. This demo showcases Datadog's Test Optimization, CI Visibility, APM, and Code Coverage capabilities on a realistic three-service microservices architecture.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     NovaPay Platform                    │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   payments   │  │   lending    │  │    fraud     │  │
│  │  :8001       │  │  :8002       │  │  :8003       │  │
│  │  FastAPI     │  │  FastAPI     │  │  FastAPI     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │            Datadog Agent (DaemonSet)               │ │
│  │  APM · Logs · Metrics · Profiling · CI Visibility  │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │   Kubernetes (minikube)  —  namespace: novapay   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker Desktop | 4.x+ (4 GB RAM allocated) | https://docs.docker.com/get-docker/ |
| minikube | v1.33+ | https://minikube.sigs.k8s.io/docs/start/ |
| kubectl | v1.29+ | https://kubernetes.io/docs/tasks/tools/ |
| Helm | v3.14+ | https://helm.sh/docs/intro/install/ |
| Python | 3.11+ | https://www.python.org/downloads/ |
| GitLab account | Free tier works | https://gitlab.com |
| Datadog account | — | https://www.datadoghq.com/free-datadog-trial/ |

You will also need:
- A **Datadog API key** (Organisation Settings → API Keys)
- At least **8 GB free RAM** and **4 CPU cores** for minikube

---

## Quick Start (5 minutes)

```bash
git clone <your-repo-url> novapay
cd novapay
export DD_API_KEY=<your-datadog-api-key>
chmod +x setup.sh
./setup.sh
```

The script will:
1. Validate prerequisites
2. Start minikube (4 CPU / 8 GB RAM)
3. Install the Datadog Agent via Helm
4. Build all three Docker images
5. Deploy services to the `novapay` namespace
6. Set up local port forwarding
7. Run a health check on each service

---

## Manual Setup Steps

### Step 1 — Start minikube

```bash
minikube start --cpus=4 --memory=8192 --driver=docker
minikube addons enable metrics-server
```

### Step 2 — Install Datadog Agent

```bash
helm repo add datadog https://helm.datadoghq.com
helm repo update

kubectl create namespace datadog
kubectl create namespace novapay

# Store the API key as a Kubernetes secret
kubectl create secret generic datadog-secret \
    --namespace datadog \
    --from-literal api-key="$DD_API_KEY"

# Install the Datadog Agent
helm upgrade --install datadog-agent datadog/datadog \
    --namespace datadog \
    --values k8s/datadog/datadog-values.yaml \
    --set datadog.apiKeyExistingSecret=datadog-secret \
    --set datadog.clusterName=novapay-demo-local \
    --wait
```

### Step 3 — Build and Deploy Services

```bash
# Point Docker CLI at minikube's Docker daemon
eval "$(minikube docker-env)"

# Build images
docker build -t novapay-payments:latest services/payments/
docker build -t novapay-fraud:latest     services/fraud/
docker build -t novapay-lending:latest   services/lending/

# Deploy to Kubernetes
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/payments/
kubectl apply -f k8s/fraud/
kubectl apply -f k8s/lending/

# Wait for deployments
kubectl rollout status deployment/novapay-payments -n novapay --timeout=120s
kubectl rollout status deployment/novapay-fraud    -n novapay --timeout=120s
kubectl rollout status deployment/novapay-lending  -n novapay --timeout=120s

# Set up port forwarding
kubectl port-forward svc/novapay-payments 8001:8001 -n novapay &
kubectl port-forward svc/novapay-fraud    8003:8003 -n novapay &
kubectl port-forward svc/novapay-lending  8002:8002 -n novapay &
```

### Step 4 — Run Tests with CI Visibility

```bash
# Each service: install deps, then run pytest with --ddtrace
cd services/payments
pip install -r requirements.txt
DD_SERVICE=novapay-payments \
DD_ENV=ci \
DD_CIVISIBILITY_ENABLED=true \
pytest --ddtrace --cov=app --cov-report=term-missing -v tests/

cd ../fraud
pip install -r requirements.txt
DD_SERVICE=novapay-fraud \
DD_ENV=ci \
DD_CIVISIBILITY_ENABLED=true \
pytest --ddtrace --cov=app --cov-report=term-missing -v tests/

cd ../lending
pip install -r requirements.txt
DD_SERVICE=novapay-lending \
DD_ENV=ci \
DD_CIVISIBILITY_ENABLED=true \
pytest --ddtrace --cov=app --cov-report=term-missing -v tests/
```

After running tests, navigate to **Software Delivery → Test Optimization** in Datadog to see results, flaky tests, and coverage gaps.

### Step 5 — Start Traffic Generation

```bash
# Install requests if not already present
pip install requests

# Run the traffic generator (generates ~30-40 req/min)
python3 scripts/generate_traffic.py
```

---

## GitLab CI Setup

This is the fastest path to a working CI pipeline — no local server needed.

### Step 1 — Push the project to GitLab

```bash
# Create a new repo on gitlab.com, then:
cd novapay
git init
git remote add origin https://gitlab.com/<your-username>/novapay.git
git add .
git commit -m "feat: initial NovaPay platform"
git push -u origin main
```

### Step 2 — Add the Datadog API Key as a CI/CD variable

1. In GitLab, go to your project → **Settings → CI/CD → Variables**
2. Click **Add variable**
3. Key: `DD_API_KEY`
4. Value: your Datadog API key
5. ✅ **Mask variable** (hides it from logs)
6. ✅ **Protect variable** (only available on protected branches)
7. Save

### Step 3 — Trigger the pipeline

Push any commit to `main` (or open a Merge Request) — the pipeline starts automatically.

```bash
git commit --allow-empty -m "trigger: run CI pipeline"
git push
```

Then navigate to **CI/CD → Pipelines** in GitLab to watch it run.

### What you'll see in the pipeline

The `.gitlab-ci.yml` has 4 stages that mirror the demo narrative:

| Stage | Jobs | What it shows |
|-------|------|---------------|
| `test` | payments, fraud, lending (parallel) | Test Optimization — flaky tests, pass/fail |
| `quality-gate` | coverage check across all services | Quality Gate blocking a deploy |
| `build` | Docker images (main branch only) | Build artifacts per commit SHA |
| `deploy` | K8s rollout (main branch only) | Deployment with rollout status |

### GitLab native test reporting

GitLab automatically picks up the JUnit XML and Cobertura coverage reports from each job (no plugin needed). You'll see:

- **Test results tab** on each pipeline run — pass/fail/flaky per test
- **Coverage %** shown on merge requests and pipeline badges
- The quality-gate job will show ✅ or ❌ with the exact coverage per service

### Connecting GitLab CI to Datadog CI Visibility

The pipeline already sets `DD_CIVISIBILITY_ENABLED=true` and `DD_API_KEY` in every test job. GitLab CI is a [supported provider](https://docs.datadoghq.com/continuous_integration/tests/) — Datadog auto-detects the pipeline metadata (branch, commit, pipeline URL) from GitLab's environment variables.

After the first pipeline run, navigate to **Software Delivery → Test Optimization** in Datadog — test results from all three services will appear within ~2 minutes.

---

## Datadog Configuration

### CI Visibility (Test Optimization)

Navigate to **Software Delivery → Test Optimization**.

You will see test runs from all three services. Key things to point out:

- **Flaky tests**: `test_payment_processing_latency_flaky`, `test_fraud_service_connectivity_flaky`, `test_concurrent_payment_processing_flaky`, and the fraud/lending equivalents will appear as flaky.
- **Auto-quarantine**: Enable in **Test Optimization → Settings → Flaky Test Management** to automatically quarantine flaky tests so they don't block CI.
- **Intelligent Test Runner (ITR)**: Skips tests whose code hasn't changed, reducing CI time.
- **Early Flake Detection**: Runs new tests multiple times to catch flakiness before it reaches main.

### Code Coverage

After running `pytest --cov`, coverage data is uploaded via the Cobertura XML report. In Jenkins, coverage is shown on each build. In Datadog:

- Navigate to **Software Delivery → Test Optimization → Code Coverage**
- Filter by service: `novapay-payments`, `novapay-fraud`, `novapay-lending`
- Point out the intentional coverage gaps:
  - `payments`: `_calculate_risk_score()` and `/payments/stats/summary` endpoint have no direct unit tests (visible as uncovered lines)
  - This demonstrates the "shift-left" value — find gaps before production

### Quality Gates

Configure quality gates in **Test Optimization → Settings → Quality Gates**:

1. Create a gate named `NovaPay Coverage Gate`
2. Condition: `code_coverage >= 80%`
3. Applied to: services `novapay-payments`, `novapay-fraud`, `novapay-lending`
4. Action: **Block pipeline**

During the demo, you can temporarily lower coverage (e.g. delete a test file) to trigger the gate and show it blocking the deploy stage in Jenkins.

### APM — Service Map

Navigate to **APM → Service Map** and look for:
- `novapay-payments`
- `novapay-fraud`
- `novapay-lending`

Traces from the traffic generator will show realistic payment flows with latency distributions.

### Synthetic Monitors

Create API tests for health checks:

1. Navigate to **Synthetic Monitoring → New Test → API Test**
2. URL: `http://localhost:8001/health` (or your cluster ingress)
3. Assertion: `status_code == 200`
4. Repeat for fraud (:8003) and lending (:8002)

---

## Demo Script (15–20 minute walkthrough)

### Scene 1 — CI Pipeline in Action (3 min)

> "NovaPay runs 40+ deployments per day. Every commit triggers a full test suite across three microservices — payments, fraud detection, and lending — all wired into Datadog."

1. Trigger a GitLab CI pipeline (push a commit or click **Run pipeline**)
2. Show the parallel test stages running in GitLab CI/CD → Pipelines
3. Navigate to **Test Optimization** and show test results streaming in

### Scene 2 — Flaky Test Detection (4 min)

> "NovaPay's QE team was losing hours each sprint to tests that failed randomly. Datadog identified seven flaky tests in the first week."

1. In Test Optimization, filter by **Flaky** status
2. Show `test_payment_processing_latency_flaky` — click in to see the failure history
3. Show the **auto-quarantine** setting — these tests no longer block the pipeline
4. Show **Early Flake Detection** configuration — new tests are run up to 10 times on first commit

### Scene 3 — Coverage Gaps (4 min)

> "Shift-left means catching problems before they reach production. Here's a coverage gap we found last sprint."

1. Navigate to **Code Coverage** for `novapay-payments`
2. Show that `_calculate_risk_score()` in `main.py` has low coverage
3. Show that the `/payments/stats/summary` endpoint is completely uncovered
4. Point out: "This is the function that determines whether a payment is flagged as fraud risk — and it has no tests."

### Scene 4 — Quality Gate Blocking a Deploy (3 min)

> "This is shift-left in practice. The quality gate caught a coverage drop before it ever reached production."

1. Show the Quality Gate configuration (80% threshold) in Datadog Test Optimization settings
2. In GitLab CI → Pipelines, find a failed pipeline where the `quality-gate` job blocked the build
3. Click into the job log — show the per-service coverage % and the ❌ FAILED message
4. Show the `build` and `deploy` stages were never reached

### Scene 5 — APM + Traces (3 min)

> "Once code ships, Datadog continues watching. Every payment transaction creates a distributed trace."

1. Navigate to **APM → Traces**
2. Filter by service `novapay-payments`, operation `payment.process`
3. Click into a trace — show span tags: `payment.currency`, `payment.method`, `payment.risk_score`
4. Show the latency distribution (50/95/99 percentiles)

### Wrap-up (1 min)

> "Datadog Quality Engineering gives NovaPay the confidence to ship 40 times a day — with flaky tests quarantined automatically, coverage gaps caught before merge, and quality gates preventing regressions from reaching production."

---

## Troubleshooting

### Services not starting in Kubernetes

```bash
kubectl get pods -n novapay
kubectl describe pod <pod-name> -n novapay
kubectl logs <pod-name> -n novapay
```

**Common causes:**
- Image not found: ensure you ran `eval "$(minikube docker-env)"` before building
- OOMKilled: increase minikube memory (`minikube stop && minikube start --memory=10240`)

### Port forwarding dropped

```bash
pkill -f "kubectl port-forward"
kubectl port-forward svc/novapay-payments 8001:8001 -n novapay &
kubectl port-forward svc/novapay-fraud    8003:8003 -n novapay &
kubectl port-forward svc/novapay-lending  8002:8002 -n novapay &
```

### Datadog Agent not receiving data

```bash
# Check agent status
kubectl exec -it $(kubectl get pod -l app=datadog -n datadog -o jsonpath='{.items[0].metadata.name}') \
    -n datadog -- agent status

# Verify API key
kubectl get secret datadog-secret -n datadog -o jsonpath='{.data.api-key}' | base64 -d
```

### Tests not appearing in Test Optimization

Ensure the following environment variables are set when running pytest:
```bash
export DD_CIVISIBILITY_ENABLED=true
export DD_SERVICE=novapay-payments   # (or fraud / lending)
export DD_ENV=ci
export DD_API_KEY=<your-key>
```

And that `ddtrace` is in requirements.txt and `--ddtrace` is passed to pytest.

### docker-compose alternative (no Kubernetes)

If you don't have minikube available, run the full stack with Docker Compose:

```bash
export DD_API_KEY=<your-key>
docker-compose up --build
```

Services will be available on the same ports. Logs and APM data will flow to Datadog via the `datadog-agent` container.

### Reset everything

```bash
# Delete all NovaPay resources
kubectl delete namespace novapay

# Uninstall Datadog agent
helm uninstall datadog-agent -n datadog

# Stop minikube
minikube stop

# Start fresh
./setup.sh
```

---

## File Structure

```
novapay/
├── services/
│   ├── payments/          # Port 8001 — core payment processing
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py    # FastAPI app + dd-trace
│   │   │   ├── models.py  # Pydantic models
│   │   │   └── database.py
│   │   ├── tests/
│   │   │   ├── conftest.py
│   │   │   └── test_payments.py  # 14 stable + 3 flaky tests
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── fraud/             # Port 8003 — fraud risk analysis
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── models.py
│   │   │   └── engine.py  # Fraud scoring rules
│   │   ├── tests/
│   │   │   ├── conftest.py
│   │   │   └── test_fraud.py     # 12 stable + 2 flaky tests
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── lending/           # Port 8002 — loan applications
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── models.py
│       │   └── database.py
│       ├── tests/
│       │   ├── conftest.py
│       │   └── test_lending.py   # 14 stable + 2 flaky tests
│       ├── requirements.txt
│       └── Dockerfile
├── k8s/
│   ├── namespace.yaml
│   ├── datadog/
│   │   └── datadog-values.yaml   # Helm values for DD agent
│   ├── payments/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── fraud/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   └── lending/
│       ├── deployment.yaml
│       └── service.yaml
├── scripts/
│   └── generate_traffic.py       # Realistic traffic simulator
├── docker-compose.yml             # Local dev (no K8s needed)
├── Jenkinsfile                    # CI/CD pipeline with DD CI Visibility
├── setup.sh                      # One-command environment setup
└── SETUP_GUIDE.md                 # This file
```

---

*Built for Datadog APJ Royal Rumble 2026 — Quality Engineering / Shift-Left track.*
