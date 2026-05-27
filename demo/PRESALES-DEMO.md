# Pelorus DORA Metrics - Presales Demo

## What You'll Show

Pelorus captures the four DORA metrics automatically from your existing tools -
git providers, Kubernetes, issue trackers. No application instrumentation needed.

You'll seed background data for 4 teams, then send live events and watch metrics
appear in Grafana dashboards in real time.

---

## Pre-Demo Setup

**CRC requirements:** 6 CPUs, 16GB RAM, 50GB disk, cluster monitoring enabled.
Fresh CRC install needs ~30 min for operator catalog indexing before `install.sh` works.
 (15-20 minutes before)

### 1. Deploy Pelorus (if not already running)

```bash
./demo/install.sh
```

### 2. Verify pods are running

```bash
oc get pods -n pelorus
```

You should see: `deploytime-exporter`, `committime-exporter`, `webhook-exporter`,
`grafana-*`, `prometheus-*` all Running.

### 3. Port-forward to the webhook exporter

```bash
oc port-forward -n pelorus svc/webhook-exporter 18080:8080 &
```

Test it:

```bash
curl -s http://localhost:18080/metrics | head -3
```

### 4. Seed background data

```bash
./demo/seed-metrics.sh http://localhost:18080
```

This creates metrics for 4 teams with different performance profiles.
Wait ~60 seconds for Prometheus to scrape.

### 5. Open Grafana

```bash
# Get the URL
oc get route grafana-route -n pelorus -o jsonpath='{.spec.host}'
```

Login: **admin** / **$PELORUS_PASSWORD** (printed by install.sh)

Open the **Software Delivery Performance** dashboard. Set time range to **Last 6 months**.

Verify you see data in the panels (Lead Time, Deployment Frequency, etc.).

---

## Demo Flow (15-20 minutes)

### Opening (2 min)

> "Every engineering org wants to ship faster and more reliably, but most can't
> answer a basic question: how fast are we actually delivering, and how stable
> is what we deliver?"
>
> "The DORA research identified four metrics that separate elite performers from
> the rest. Pelorus captures these automatically from your existing tools."

**Show the Software Delivery Performance dashboard.** Point out the four quadrants:

| Metric | What it measures |
|---|---|
| **Lead Time for Change** | Time from code commit to production |
| **Deployment Frequency** | How often you ship |
| **Mean Time to Restore** | How fast you recover from incidents |
| **Change Failure Rate** | What percentage of deploys cause problems |

---

### Part 1: "Where does the data come from?" (3 min)

**Show the pods** in the OpenShift Console or terminal:

```bash
oc get pods -n pelorus -l pelorus.dora-metrics.io/exporter-type
```

Walk through the exporters:

| Exporter | What it measures | Data source |
|---|---|---|
| **deploytime** | When code reaches production | Watches the Kubernetes API |
| **committime** | When code was committed | GitHub, GitLab, Bitbucket, Azure DevOps |
| **failure** | Incidents and resolution | Jira, ServiceNow, PagerDuty, GitHub Issues |
| **webhook** | All of the above via HTTP | Any CI/CD system or custom integration |

> "Nothing to instrument in your applications. Pelorus reads metadata that
> already exists - container image SHAs, git commit timestamps, issue tracker
> state changes."

---

### Part 2: "Watch metrics flow in real time" (5 min)

This is the hero moment. You send live events and the dashboards update.

> "Let me show you what happens when a team deploys code."

**Step 1: A developer commits code**

```bash
IMG_SHA="sha256:$(openssl rand -hex 32)"

curl -s -X POST http://localhost:18080/pelorus/webhook \
  -H "Content-Type: application/json" \
  -H "User-Agent: Pelorus-Webhook/demo" \
  -H "X-Pelorus-Event: committime" \
  -d "{
    \"app\": \"checkout-service\",
    \"commit_hash\": \"$(openssl rand -hex 20)\",
    \"image_sha\": \"${IMG_SHA}\",
    \"namespace\": \"checkout-prod\",
    \"timestamp\": $(date +%s)
  }"
```

> "A developer just committed code. In production, the committime exporter
> picks this up automatically from GitHub or GitLab."

**Step 2: CI/CD deploys to production** (wait ~10 seconds)

```bash
curl -s -X POST http://localhost:18080/pelorus/webhook \
  -H "Content-Type: application/json" \
  -H "User-Agent: Pelorus-Webhook/demo" \
  -H "X-Pelorus-Event: deploytime" \
  -d "{
    \"app\": \"checkout-service\",
    \"image_sha\": \"${IMG_SHA}\",
    \"namespace\": \"checkout-prod\",
    \"timestamp\": $(date +%s)
  }"
```

> "The deploy landed. Pelorus now knows the lead time - the gap between commit
> and production. No CI plugin needed."

**Step 3: Deploy again** (shows deployment frequency increasing)

```bash
IMG_SHA2="sha256:$(openssl rand -hex 32)"

curl -s -X POST http://localhost:18080/pelorus/webhook \
  -H "Content-Type: application/json" \
  -H "User-Agent: Pelorus-Webhook/demo" \
  -H "X-Pelorus-Event: committime" \
  -d "{\"app\":\"checkout-service\",\"commit_hash\":\"$(openssl rand -hex 20)\",\"image_sha\":\"${IMG_SHA2}\",\"namespace\":\"checkout-prod\",\"timestamp\":$(date +%s)}"

sleep 5

curl -s -X POST http://localhost:18080/pelorus/webhook \
  -H "Content-Type: application/json" \
  -H "User-Agent: Pelorus-Webhook/demo" \
  -H "X-Pelorus-Event: deploytime" \
  -d "{\"app\":\"checkout-service\",\"image_sha\":\"${IMG_SHA2}\",\"namespace\":\"checkout-prod\",\"timestamp\":$(date +%s)}"
```

> "Second deploy. Deployment frequency goes up. Each with its own measured
> lead time."

**Refresh Grafana** (wait ~30s for Prometheus scrape). Switch to
**Software Delivery Performance - By App** dashboard, select `checkout-service`.

> "There it is - checkout-service showing up alongside the other teams."

---

### Part 3: "Comparing team performance" (3 min)

**Stay on the By App dashboard.** Use the Application dropdown to switch between teams.

| Application | Lead Time | Failure Rate | Story |
|---|---|---|---|
| **frontend** | ~35 seconds | ~10% | "Elite performer. Commits reach production in under a minute." |
| **api-gateway** | ~3-4 minutes | ~22% | "Solid. Their test suite adds time but they're reliable." |
| **inventory-service** | ~6 minutes | ~15% | "Improving. They were slower last quarter." |
| **payment-service** | ~13 minutes | ~40% | "This team is struggling. Long lead times, high failure rate." |
| **checkout-service** | ~10 seconds | - | "The service we just deployed. Real data, captured live." |

> "We're not measuring activity - commits, PRs, lines of code. We're measuring
> outcomes. How fast does value reach customers? An engineering VP can look at
> this and know exactly where to invest."

Switch to **Explore** in Grafana, run `sdp:lead_time:by_app`:

> "You can see the stratification clearly - some teams shipping in seconds,
> others taking 15 minutes. This is how you find where the bottlenecks are."

---

### Part 4: "When things go wrong" (3 min)

> "DORA also measures resilience - how fast teams recover from incidents."

**Create an incident:**

```bash
curl -s -X POST http://localhost:18080/pelorus/webhook \
  -H "Content-Type: application/json" \
  -H "User-Agent: Pelorus-Webhook/demo" \
  -H "X-Pelorus-Event: failure" \
  -d "{
    \"app\": \"checkout-service\",
    \"failure_id\": \"INC-1234\",
    \"failure_event\": \"created\",
    \"timestamp\": $(date +%s)
  }"
```

> "An incident just hit checkout-service. The clock is ticking. In production,
> this comes automatically from Jira, ServiceNow, or PagerDuty."

Wait 15-20 seconds (let the tension build), then **resolve it:**

```bash
curl -s -X POST http://localhost:18080/pelorus/webhook \
  -H "Content-Type: application/json" \
  -H "User-Agent: Pelorus-Webhook/demo" \
  -H "X-Pelorus-Event: failure" \
  -d "{
    \"app\": \"checkout-service\",
    \"failure_id\": \"INC-1234\",
    \"failure_event\": \"resolved\",
    \"timestamp\": $(date +%s)
  }"
```

> "Resolved. Pelorus captured the Mean Time to Restore. And the change failure
> rate just went up - that's a signal to investigate."

---

### Part 5: "The business case" (2 min)

**Go back to the global Software Delivery Performance dashboard.**

> "The DORA research shows that elite engineering organizations deploy 973 times
> more frequently than low performers, with 6,570 times shorter lead times.
> And they're not sacrificing stability."
>
> "Pelorus gives you the baseline. You can't improve what you don't measure."
>
> "And this all runs on the same OpenShift platform your teams already use.
> It's not another SaaS tool to procure. It's part of the platform."

---

### Closing (1 min)

> "To recap: Pelorus connects to your existing tools - git providers,
> Kubernetes, issue trackers. It automatically captures the four DORA metrics.
> No application changes, no CI plugins."
>
> "You saw live data flowing from commits and deployments into Grafana
> dashboards. In production, this happens continuously across all your
> services."
>
> "Questions?"

---

## Quick Reference

### Port-forwards needed

```bash
# Webhook exporter (for sending events)
oc port-forward -n pelorus svc/webhook-exporter 18080:8080 &

# Grafana (if not using the route)
oc port-forward -n pelorus svc/grafana-oauth-service 13000:3000 &
```

### Grafana access

- **Route:** `https://grafana-route-pelorus.apps-crc.testing`
- **Port-forward:** `http://localhost:13000`
- **Login:** admin / $PELORUS_PASSWORD
- **Dashboards:** Software Delivery Performance, Software Delivery Performance - By App
- **Time range:** Last 5 minutes (best for demo with seeded data)

### If dashboards show N/A

1. Check webhook is accessible: `curl http://localhost:18080/metrics | grep deploy_timestamp`
2. Check Prometheus has data: `curl http://localhost:19090/api/v1/query?query=count(deploy_timestamp)`
3. Re-seed: `./demo/seed-metrics.sh http://localhost:18080`
4. Wait 60s for Prometheus scrape + recording rules

### Common Questions

**Q: Does this require changes to our applications?**
No. Pelorus reads metadata from Kubernetes, git providers, and issue trackers.

**Q: What git providers are supported?**
GitHub, GitLab, Bitbucket, Gitea, Azure DevOps.

**Q: What issue trackers are supported?**
Jira, GitHub Issues, ServiceNow, PagerDuty, Azure DevOps.

**Q: How is this different from CI/CD pipeline metrics?**
Pipeline metrics tell you how long your build took. DORA metrics tell you the
full path from commit to customer and how stable that delivery is.

**Q: Can we see trends over time?**
Yes. The dashboards show both current values and historical trends.

**Q: Does it work with non-OpenShift Kubernetes?**
The core exporters work on any Kubernetes. The Helm chart includes optional
OpenShift features like OAuth proxy and Routes.

**Q: Is there an operator?**
Yes. The Pelorus Operator manages the full stack via a single custom resource.
