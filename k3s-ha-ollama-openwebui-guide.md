# HA K3s Cluster mit GPU Ollama + OpenWebUI (SQLite + Longhorn)

## Umgebung

### Nodes

  Node    IP
  ------- -------------
  node1   10.52.94.8
  node2   10.52.94.9
  node3   10.52.94.10

### Ziel

-   Hochverfügbarer Kubernetes Cluster (k3s + embedded etcd)
-   GPU Nutzung für Ollama
-   OpenWebUI mit SQLite auf Longhorn
-   Zugriff über feste IP 10.52.94.201

------------------------------------------------------------------------

# 1 Voraussetzungen auf ALLEN Nodes

## System vorbereiten

``` bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git vim
```

## Kernel Settings

``` bash
sudo modprobe overlay
sudo modprobe br_netfilter

cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF

sudo sysctl --system
```

------------------------------------------------------------------------

# 2 NVIDIA Treiber + Container Runtime

## Treiber installieren

``` bash
sudo ubuntu-drivers autoinstall
sudo reboot
```

## Container Toolkit

``` bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit.gpg] https://#g' | \
sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart containerd
```

------------------------------------------------------------------------

# 3 K3s HA Cluster installieren

## NODE 1

``` bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
--cluster-init \
--disable traefik \
--flannel-backend=none" sh -
```

Token anzeigen:

``` bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

------------------------------------------------------------------------

## NODE 2 und 3

``` bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
--server https://10.52.94.8:6443 \
--token <TOKEN> \
--disable traefik \
--flannel-backend=none" sh -
```

------------------------------------------------------------------------

# 4 Cilium installieren

``` bash
curl -L --remote-name https://github.com/cilium/cilium-cli/releases/latest/download/cilium-linux-amd64.tar.gz
tar xzvf cilium-linux-amd64.tar.gz
sudo mv cilium /usr/local/bin/

cilium install
cilium status --wait
```

------------------------------------------------------------------------

# 5 MetalLB installieren

``` bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml
```

IP Pool:

``` yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default
  namespace: metallb-system
spec:
  addresses:
  - 10.52.94.201-10.52.94.210
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
```

Apply:

``` bash
kubectl apply -f metallb.yaml
```

------------------------------------------------------------------------

# 6 Longhorn installieren

``` bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.6.0/deploy/longhorn.yaml
```

------------------------------------------------------------------------

# 7 NVIDIA GPU Operator

``` bash
kubectl create namespace gpu-operator
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/gpu-operator/main/deployments/gpu-operator.yaml
```

------------------------------------------------------------------------

# 8 Ollama DaemonSet

``` yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ollama
  namespace: default
spec:
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
      - name: ollama
        image: ollama/ollama
        ports:
        - containerPort: 11434
        resources:
          limits:
            nvidia.com/gpu: 2
        volumeMounts:
        - mountPath: /root/.ollama
          name: ollama-data
      volumes:
      - name: ollama-data
        hostPath:
          path: /data/ollama
```

------------------------------------------------------------------------

# 9 GPT OSS Modell laden

``` bash
kubectl exec -it <ollama-pod> -- ollama pull gpt-oss:20b
```

------------------------------------------------------------------------

# 10 OpenWebUI Deployment

``` yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openwebui
spec:
  replicas: 1
  selector:
    matchLabels:
      app: openwebui
  template:
    metadata:
      labels:
        app: openwebui
    spec:
      containers:
      - name: openwebui
        image: ghcr.io/open-webui/open-webui:main
        ports:
        - containerPort: 8080
        volumeMounts:
        - mountPath: /app/backend/data
          name: webui-data
      volumes:
      - name: webui-data
        persistentVolumeClaim:
          claimName: webui-pvc
```

------------------------------------------------------------------------

# 11 Longhorn PVC

``` yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: webui-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

------------------------------------------------------------------------

# 12 LoadBalancer Service

``` yaml
apiVersion: v1
kind: Service
metadata:
  name: openwebui
spec:
  type: LoadBalancer
  loadBalancerIP: 10.52.94.201
  selector:
    app: openwebui
  ports:
  - port: 80
    targetPort: 8080
```

------------------------------------------------------------------------

# 13 Test

``` bash
kubectl get nodes
kubectl get pods -A
nvidia-smi
```

Zugriff:

    http://10.52.94.201

------------------------------------------------------------------------

# Fertig
