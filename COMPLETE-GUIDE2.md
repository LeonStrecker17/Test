# OLLAMA + OPENWEBUI DEPLOYMENT GUIDE
## K3s GPU Cluster - Production Ready

---

## 📋 WAS DU BEKOMMST

### Hardware-Nutzung
- **3 Nodes** mit je RTX 5000 Ada (24GB) + A1000 (8GB)
- **Alle 6 GPUs aktiv genutzt**
- **96GB VRAM total** im Cluster

### Ollama Setup
- **3 Ollama Pods** (1 pro Node)
- Jeder Pod nutzt **beide GPUs** seines Nodes
- **4 parallele Requests pro Pod**
- **12 parallele Requests gesamt** im Cluster
- Automatisches **Load Balancing** über alle Pods

### OpenWebUI Setup
- **2 Replicas** für High Availability
- Automatische Verbindung zu Ollama
- Erreichbar: **http://<beliebige-node-ip>:30500**

### Kapazität
- **~8GB VRAM pro Request** (32GB / 4 parallel)
- Optimal für Models: **7B - 13B Parameter**
- **10-12 gleichzeitige User** möglich

### High Availability
- Node-Ausfall → **2 von 3 Ollama Pods** bleiben (66% Kapazität)
- Node-Ausfall → **OpenWebUI läuft weiter** (2 Replicas)
- Automatisches Failover durch Kubernetes

---

## 🚀 DEPLOYMENT (5 Minuten)

### Schritt 1: Files prüfen

Stelle sicher du hast:
- `ollama-deployment.yaml`
- `openwebui-deployment.yaml`

### Schritt 2: Deployen

```bash
# Ollama deployen
kubectl apply -f ollama-deployment.yaml

# OpenWebUI deployen  
kubectl apply -f openwebui-deployment.yaml

# Status checken (dauert 2-3 Minuten)
kubectl get pods -n ai-services -w
```

**CTRL+C** wenn alle Pods **Running** sind.

### Schritt 3: Verifizieren

```bash
# Sollte zeigen:
kubectl get pods -n ai-services

# NAME                        READY   STATUS    RESTARTS   AGE
# ollama-xxxxx                1/1     Running   0          2m
# ollama-yyyyy                1/1     Running   0          2m
# ollama-zzzzz                1/1     Running   0          2m
# openwebui-aaaaa             1/1     Running   0          1m
# openwebui-bbbbb             1/1     Running   0          1m
```

---

## 🤖 MODELLE LADEN

```bash
# In einen Ollama Pod einloggen
kubectl exec -it -n ai-services deployment/ollama -- bash

# Modelle laden (Beispiele für 4 parallel)
ollama pull llama3.1:8b       # ~5GB VRAM
ollama pull mistral:7b        # ~4GB VRAM
ollama pull codellama:13b     # ~7GB VRAM

# Modelle auflisten
ollama list

# Testen
ollama run llama3.1:8b "Hello"

# Beenden
exit
```

**Wichtig:** Bei 4 parallel = ~8GB VRAM pro Request. Nutze Models bis 13B.

---

## 🌐 ZUGRIFF

OpenWebUI ist automatisch erreichbar auf:

```
http://10.52.94.5:30500
http://<node2-ip>:30500
http://<node3-ip>:30500
```

Einfach im Browser öffnen!

**Beim ersten Login:**
1. Account erstellen (lokal, keine Email)
2. Model auswählen (die du geladen hast)
3. Chatten!

---

## 🔍 MONITORING & CHECKS

### Pod Status checken
```bash
kubectl get pods -n ai-services
kubectl get pods -n ai-services -o wide  # Mit Node-Info
```

### GPU-Nutzung ansehen
```bash
# Auf einem Node direkt
nvidia-smi

# Oder remote
ssh <node-ip> 'nvidia-smi'

# Sollte zeigen:
# GPU 0: RTX 5000 Ada - mit Auslastung
# GPU 1: A1000 - mit Auslastung
```

### Load Balancing testen
```bash
# Logs aller Ollama Pods live
kubectl logs -n ai-services -l app=ollama -f --prefix

# Öffne dann mehrere Browser-Tabs
# Starte in jedem einen Chat
# In den Logs siehst du Requests auf verschiedene Pods verteilt
```

### Resource Usage
```bash
# CPU/RAM Auslastung
kubectl top pods -n ai-services
kubectl top nodes

# Storage
kubectl get pvc -n ai-services

# Longhorn Dashboard
kubectl get svc -n longhorn-system
```

### Service Status
```bash
# Alle Services
kubectl get svc -n ai-services

# Endpoints (welche Pods sind im Load Balancer)
kubectl get endpoints -n ai-services ollama
```

---

## 🛠️ TROUBLESHOOTING

### Problem: Pods bleiben "Pending"

**Diagnose:**
```bash
kubectl describe pod -n ai-services <pod-name>
```

**Häufigste Ursachen:**

**1. Nicht genug GPUs**
```bash
# Prüfe GPU Verfügbarkeit
kubectl get nodes -o json | jq '.items[] | {name: .metadata.name, gpus: .status.capacity."nvidia.com/gpu"}'

# Sollte zeigen: Jeder Node hat 2 GPUs
```

**Lösung:**
```bash
# GPU Operator Status
kubectl get pods -n gpu-operator-resources

# Falls Probleme: GPU Operator neu starten
kubectl rollout restart daemonset -n gpu-operator-resources
```

**2. Longhorn PVC Problem**
```bash
# PVC Status
kubectl get pvc -n ai-services
kubectl describe pvc -n ai-services ollama-models-pvc

# Longhorn Status
kubectl get pods -n longhorn-system
```

**Lösung:**
```bash
# Falls Longhorn Probleme hat
kubectl rollout restart deployment -n longhorn-system
```

---

### Problem: OpenWebUI nicht erreichbar

**Diagnose:**
```bash
# Service Status
kubectl get svc -n ai-services openwebui-nodeport

# Pod Status
kubectl get pods -n ai-services -l app=openwebui

# Direkt testen
curl http://localhost:30500
```

**Lösung:**

**Firewall öffnen** (falls aktiviert):
```bash
sudo ufw allow 30500/tcp
sudo ufw status
```

**Pod Logs checken:**
```bash
kubectl logs -n ai-services -l app=openwebui --tail=50
```

---

### Problem: Ollama nutzt nur 1 GPU

**Diagnose:**
```bash
# In Pod schauen
kubectl exec -n ai-services deployment/ollama -- nvidia-smi

# Env Vars prüfen
kubectl exec -n ai-services deployment/ollama -- env | grep -i cuda
kubectl exec -n ai-services deployment/ollama -- env | grep -i ollama
```

**Sollte zeigen:**
```
CUDA_VISIBLE_DEVICES=0,1
OLLAMA_NUM_GPU=2
OLLAMA_NUM_PARALLEL=4
```

**Lösung:**
```bash
# Pods neu starten
kubectl rollout restart deployment/ollama -n ai-services

# Status checken
kubectl rollout status deployment/ollama -n ai-services
```

---

### Problem: Models laden langsam

**Ursache:** Longhorn Storage kann langsamer sein als lokale SSDs.

**Check:**
```bash
# Longhorn Performance
kubectl get pods -n longhorn-system
kubectl logs -n longhorn-system -l app=longhorn-manager --tail=50
```

**Workaround:** Models außerhalb des Clusters vorladen:
```bash
# Auf einem Node direkt (falls Ollama installiert)
ollama pull llama3.1:8b

# Dann in Container kopieren
```

---

### Problem: Chat ist langsam / OOM Errors

**Diagnose:**
```bash
# Memory Usage checken
kubectl top pods -n ai-services

# Logs nach OOM Errors
kubectl logs -n ai-services -l app=ollama --tail=100 | grep -i "out of memory"

# GPU VRAM checken
kubectl exec -n ai-services deployment/ollama -- nvidia-smi
```

**Ursache:** 4 parallele Requests + zu große Models = VRAM-Fragmentierung

**Lösung 1:** Kleinere Models nutzen
```bash
# Statt codellama:13b → codellama:7b
ollama pull codellama:7b
```

**Lösung 2:** OLLAMA_NUM_PARALLEL reduzieren

In `ollama-deployment.yaml` ändern:
```yaml
- name: OLLAMA_NUM_PARALLEL
  value: "2"  # Statt 4
```

Dann neu deployen:
```bash
kubectl apply -f ollama-deployment.yaml
kubectl rollout restart deployment/ollama -n ai-services
```

**Lösung 3:** Memory Limits erhöhen

In `ollama-deployment.yaml`:
```yaml
limits:
  memory: "64Gi"  # Statt 32Gi
```

---

### Problem: Node fällt aus - Pods starten nicht

**Diagnose:**
```bash
kubectl get pods -n ai-services -o wide
kubectl describe pod -n ai-services <pending-pod>
```

**Ursache:** Mit 2 GPUs pro Pod hast du keine Reserve-Kapazität.

**Das ist normal!** Design-Entscheidung:
- **Aktuelle Config:** 3 Pods × 2 GPUs = Große Models, keine Reserve
- **Alternative:** 6 Pods × 1 GPU = Kleinere Models, mehr Redundanz

**Lösung:** Node wieder online bringen
```bash
kubectl get nodes
kubectl uncordon <node-name>
```

---

## 📊 PERFORMANCE TUNING

### Wenn du mehr Parallelität willst

**Option 1:** Mehr Ollama Pods (6 statt 3)

Jeder Pod nutzt nur 1 GPU:
- 6 Pods × 4 parallel = **24 parallele Requests**
- Nur kleinere Models (bis 8B)
- Mehr Redundanz

**Option 2:** Weniger parallel pro Pod

Jeder Request bekommt mehr VRAM:
- 2 parallel statt 4 = **16GB pro Request**
- Größere Models möglich (bis 30B)
- Weniger parallele User

### Wenn Models zu langsam laden

**Nutze lokalen SSD Storage** statt Longhorn:

1. Erstelle `local-storage` StorageClass
2. Ändere PVC zu `storageClassName: local-storage`
3. **Nachteil:** Models nicht über Nodes geshared

### Wenn du TLS/HTTPS willst

**Nutze Ingress statt NodePort:**

```bash
# cert-manager installieren
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Ingress für OpenWebUI erstellen
# (siehe K3s Traefik Dokumentation)
```

---

## 🔄 WARTUNG & UPDATES

### Ollama Image updaten
```bash
kubectl set image deployment/ollama -n ai-services \
  ollama=ollama/ollama:latest

kubectl rollout status deployment/ollama -n ai-services
```

### OpenWebUI updaten
```bash
kubectl set image deployment/openwebui -n ai-services \
  openwebui=ghcr.io/open-webui/open-webui:main

kubectl rollout status deployment/openwebui -n ai-services
```

### Neue Models hinzufügen
```bash
kubectl exec -it -n ai-services deployment/ollama -- \
  ollama pull <model-name>
```

### Models löschen
```bash
kubectl exec -it -n ai-services deployment/ollama -- \
  ollama rm <model-name>
```

### Backup erstellen
```bash
# Longhorn hat automatische Snapshots

# Manuelles Backup der Models
kubectl exec -n ai-services deployment/ollama -- \
  tar czf - /models > ollama-models-backup.tar.gz

# OpenWebUI Daten
kubectl exec -n ai-services deployment/openwebui -- \
  tar czf - /app/backend/data > openwebui-data-backup.tar.gz
```

---

## 📈 SKALIERUNG

### 4. Node hinzufügen

```bash
# Ollama Replicas erhöhen
kubectl scale deployment/ollama -n ai-services --replicas=4

# Dann hast du:
# 4 Pods × 4 parallel = 16 parallele Requests
```

### Mehr Storage für Models

```bash
# PVC erweitern
kubectl edit pvc -n ai-services ollama-models-pvc

# Ändere:
# storage: 1Ti  # Statt 500Gi

# Longhorn expanded automatisch
```

---

## ✅ ZUSAMMENFASSUNG - FINAL SETUP

**Was läuft:**
- ✅ 3 Ollama Pods (je 2 GPUs, 4 parallel)
- ✅ 2 OpenWebUI Pods (HA)
- ✅ Load Balancing über alle Ollama Pods
- ✅ 12 parallele Requests gesamt

**Zugriff:**
- ✅ `http://<node-ip>:30500`

**Kapazität:**
- ✅ 10-12 gleichzeitige User
- ✅ Models bis 13B Parameter
- ✅ ~8GB VRAM pro Request

**High Availability:**
- ✅ Node-Ausfall → System läuft weiter
- ✅ 66% Kapazität bleibt bei Ausfall

**Storage:**
- ✅ 500GB für Models (shared über Longhorn)
- ✅ 10GB für OpenWebUI Daten
- ✅ ReadWriteMany für HA

---

## 🎯 NÄCHSTE SCHRITTE

1. **Deployen** (siehe oben)
2. **Models laden** (llama3.1:8b, mistral:7b)
3. **Browser öffnen** (http://<node-ip>:30500)
4. **Chatten!**

Bei Problemen: Schaue in die Logs
```bash
kubectl logs -n ai-services -l app=ollama --tail=100
kubectl logs -n ai-services -l app=openwebui --tail=100
```

**Viel Erfolg! 🚀**
