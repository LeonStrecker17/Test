# EINFACHE DEPLOYMENT ANLEITUNG
## Ollama + OpenWebUI auf K3s

---

## ✅ WAS DU BEKOMMST

- **12 parallele Ollama Requests** (3 Pods × 4 parallel)
- Jeder Pod nutzt **beide GPUs** (RTX 5000 Ada + A1000)
- **Load Balancing** automatisch
- **OpenWebUI mit HA** (2 Replicas)
- **Zugriff:** `http://<beliebige-node-ip>:30500`

---

## 🚀 DEPLOYMENT (3 Minuten)

```bash
# 1. Deployen
kubectl apply -f ollama-deployment.yaml
kubectl apply -f openwebui-deployment.yaml

# 2. Warten bis alles läuft (2-3 Min)
kubectl get pods -n ai-services -w

# CTRL+C wenn alle "Running" sind
```

**Erwartete Pods:**
- 3x `ollama-xxxxx` (einer pro Node, je 2 GPUs)
- 2x `openwebui-xxxxx` (für HA)

---

## 🌐 ZUGRIFF

OpenWebUI ist **automatisch** erreichbar auf:
- `http://10.52.94.5:30500`
- `http://<node2-ip>:30500`
- `http://<node3-ip>:30500`

Öffne einfach im Browser eine dieser URLs!

---

## 🤖 MODELLE LADEN

```bash
# Verbinde zu Ollama
kubectl exec -it -n ai-services deployment/ollama -- bash

# Lade Modelle
ollama pull llama3.1:8b
ollama pull mistral:7b
ollama pull codellama:13b

# Liste
ollama list

# Exit
exit
```

**Wichtig:** Mit 4 parallel = ~8GB VRAM pro Request. Nutze Models bis 13B Parameter.

---

## 🔍 QUICK CHECKS

### Läuft alles?
```bash
kubectl get pods -n ai-services
# Alle sollten "Running" sein
```

### GPU-Nutzung
```bash
# Auf einem Node:
nvidia-smi

# Sollte beide GPUs zeigen mit Auslastung
```

### Load Balancing testen
```bash
# Logs live ansehen
kubectl logs -n ai-services -l app=ollama -f

# Öffne mehrere Browser-Tabs und chatte
# Du siehst Requests werden auf verschiedene Pods verteilt
```

---

## 🛠️ PROBLEME?

### Pods starten nicht
```bash
kubectl describe pod -n ai-services <pod-name>

# Häufig: Nicht genug GPUs
kubectl get nodes -o json | jq '.items[] | {name: .metadata.name, gpus: .status.capacity."nvidia.com/gpu"}'
```

### OpenWebUI nicht erreichbar
```bash
# Prüfe Service
kubectl get svc -n ai-services openwebui-nodeport

# Prüfe Firewall (falls aktiviert)
sudo ufw allow 30500/tcp
```

### Ollama nutzt nur 1 GPU
```bash
# Prüfe Env Vars
kubectl exec -n ai-services deployment/ollama -- env | grep CUDA

# Sollte zeigen: CUDA_VISIBLE_DEVICES=0,1

# Falls nicht: Neu starten
kubectl rollout restart deployment/ollama -n ai-services
```

---

## 📊 MONITORING

```bash
# Resource Usage
kubectl top pods -n ai-services
kubectl top nodes

# Storage
kubectl get pvc -n ai-services

# Health Check Script
./cluster-health-check.sh
```

---

## ✅ FERTIG!

Dein Setup:
- ✅ OpenWebUI auf `http://<node-ip>:30500`
- ✅ 3 Ollama Pods mit je 2 GPUs
- ✅ 12 parallele Requests möglich
- ✅ Load Balancing & HA

**Viel Spaß beim Chatten! 🎉**
