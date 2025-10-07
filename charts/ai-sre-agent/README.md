# AI-SRE-Agent Helm Chart

This Helm chart deploys the AI-SRE-Agent application to a Kubernetes cluster.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- Access to configure RBAC resources (for ClusterRoleBinding)

## Installation

### Basic Installation

```bash
helm install ai-sre-agent ./ai-sre-agent
```

### Installation with Custom Values

```bash
helm install ai-sre-agent ./ai-sre-agent -f my-values.yaml
```

## Configuration

### RBAC Configuration

The chart creates a ServiceAccount and ClusterRoleBinding by default to allow the AI-SRE-Agent to access Kubernetes resources.

```yaml
serviceAccount:
  create: true        # Create a ServiceAccount
  annotations: {}     # Annotations for the ServiceAccount
  name: ""           # Custom name (optional)

rbac:
  create: true              # Create RBAC resources
  clusterRole: view         # ClusterRole to bind (default: view)
```

The default `view` ClusterRole provides read-only access to most Kubernetes resources, which is sufficient for the Kubernetes Expert Agent to:
- Get pod status
- List events
- View deployments

#### Using a Custom ClusterRole

If you need different permissions, you can specify a different ClusterRole:

```yaml
rbac:
  clusterRole: custom-role-name
```

Or disable RBAC creation and manage it externally:

```yaml
rbac:
  create: false
```

### Image Configuration

```yaml
image:
  repository: ghcr.io/k8s-lovers-korea/ai-sre-agent/agent
  tag: 0.0.1
  pullPolicy: IfNotPresent
```

### Resource Limits

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### Environment Variables

Configure the agent behavior through environment variables:

```yaml
env:
  # LLM Provider Settings
  AZURE_OPENAI_ENDPOINT: "https://your-instance.openai.azure.com/"
  AZURE_OPENAI_API_VERSION: "2024-02-15-preview"
  
  # Kubernetes Settings
  MOCK_K8S_API: "false"  # Set to true for testing without real cluster
  
  # Monitoring Integration
  PROMETHEUS_URL: "http://prometheus:9090"
  LOKI_URL: "http://loki:3100"
```

### Secrets

Store sensitive data in Kubernetes secrets:

```yaml
secrets:
  AZURE_OPENAI_API_KEY: "your-api-key"
  GRAFANA_API_KEY: "your-grafana-key"
```

## Security

The chart includes security best practices:

```yaml
securityContext:
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
```

## Ingress

To expose the service externally:

```yaml
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: sre-agent.example.com
      paths:
        - path: /
          pathType: Prefix
```

## Upgrading

```bash
helm upgrade ai-sre-agent ./ai-sre-agent
```

## Uninstalling

```bash
helm uninstall ai-sre-agent
```

## Kubernetes Permissions

The Kubernetes Expert Agent requires the following permissions to function:

| Resource | Verbs | Purpose |
|----------|-------|---------|
| pods | get, list | Check pod status and health |
| events | get, list | Analyze Kubernetes events |
| deployments | get, list | View deployment information |

These permissions are provided by the default `view` ClusterRole.

For deployment restart functionality (when `dry_run=false`), additional permissions would be required:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: ai-sre-agent-admin
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "patch"]
- apiGroups: [""]
  resources: ["pods", "events"]
  verbs: ["get", "list"]
```

## Examples

### Development Setup (Mock Mode)

```yaml
env:
  MOCK_K8S_API: "true"
  DEBUG: "true"

rbac:
  create: false  # No real cluster access needed in mock mode
```

### Production Setup

```yaml
replicaCount: 2

resources:
  requests:
    cpu: 200m
    memory: 256Mi
  limits:
    cpu: 1000m
    memory: 1Gi

serviceAccount:
  create: true

rbac:
  create: true
  clusterRole: view

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: sre-agent.production.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: sre-agent-tls
      hosts:
        - sre-agent.production.com
```

## Troubleshooting

### RBAC Permission Errors

If you see errors like "forbidden: User cannot list pods":

1. Verify the ServiceAccount is created:
   ```bash
   kubectl get serviceaccount -n <namespace>
   ```

2. Verify the ClusterRoleBinding is created:
   ```bash
   kubectl get clusterrolebinding | grep ai-sre-agent
   ```

3. Check if the deployment is using the ServiceAccount:
   ```bash
   kubectl get deployment <deployment-name> -o yaml | grep serviceAccountName
   ```

### Mock Mode Testing

To test without a real cluster:

```yaml
env:
  MOCK_K8S_API: "true"
```

This will use mock data for Kubernetes API calls.

## Support

For issues and questions, please visit:
- GitHub Issues: https://github.com/k8s-lovers-korea/ai-sre-agent/issues
- Documentation: https://github.com/k8s-lovers-korea/ai-sre-agent

## License

See the LICENSE file in the repository root.
