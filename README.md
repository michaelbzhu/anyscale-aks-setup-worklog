# setting up anyscale cloud with aks - worklog

## Table of Contents
- [Terraform](#terraform)
- [Cluster Creds and Nginx](#cluster-creds-and-nginx)
- [Anyscale Cloud Setup](#anyscale-cloud-setup)
- [Trying to Get a Job to Run](#trying-to-get-a-job-to-run)
- [Fixing Missing AZURE_CLIENT_ID](#fixing-missing-azure_client_id)
- [Fixing Authentication Issue](#fixing-authentication-issue)
- [Storage Account CORS Issue](#storage-account-cors-issue)
- [references](#references)

### terraform
First I updated the default value for `variable "aks_cluster_name"` in `terraform/variables.tf`

The storage account name derives from cluster name and needs to be globally unique across azure storage accounts

To deploy the aks cluster with terraform
```
cd terraform
terraform init
terraform plan
terraform apply
```

which gave me the following outputs
```
Apply complete! Resources: 13 added, 0 changed, 10 destroyed.

Outputs:

anyscale_operator_client_id = "803f0854-b930-480f-8756-7d5aa40952f1"
anyscale_registration_command = <<EOT
anyscale cloud register \
	--name <anyscale_cloud_name> \
	--region westus \
	--provider azure \
	--compute-stack k8s \
	--cloud-storage-bucket-name 'azure://michaelz-anyscale-demo-blob' \
	--cloud-storage-bucket-endpoint 'https://michaelzanyscaledemosa.blob.core.windows.net'
EOT
azure_aks_cluster_name = "michaelz-anyscale-demo"
azure_resource_group_name = "michaelz-anyscale-demo-rg"
azure_storage_account_name = "michaelzanyscaledemosa"
helm_upgrade_command = <<EOT
helm upgrade anyscale-operator anyscale/anyscale-operator \
	--set-string cloudDeploymentId=<cloud-deployment-id> \
	--set-string region=westus \
	--set-string cloudProvider=azure \
	--set-string operatorIamIdentity=803f0854-b930-480f-8756-7d5aa40952f1 \
	--set-string workloadServiceAccountName=anyscale-operator \
	--namespace anyscale-operator \
	--create-namespace \
	-i
EOT
```

### cluster creds and nginx
then store the credentials of the cluster to `~/.kube/config`
```
az aks get-credentials --resource-group <azure_resource_group_name> --name <aks_cluster_name> --overwrite-existing
az aks get-credentials --resource-group michaelz-anyscale-demo-rg --name michaelz-anyscale-demo --overwrite-existing
```

then i ran this to setup nginx on the cluster
```
helm repo add nginx https://kubernetes.github.io/ingress-nginx
helm upgrade ingress-nginx nginx/ingress-nginx \
 --version 4.12.1 \
 --namespace ingress-nginx \
 --values sample-values_nginx.yaml \
 --create-namespace \
 --install
```

### anyscale cloud setup
first i used uv to get the anyscale cli

```
uv init
uv add anyscale
source .venv/bin/activate
```

then register the anyscale cloud
```
anyscale cloud register \
  --name <name-for-anyscale-web-ui> \
  --region <region> \
  --provider azure \
  --compute-stack k8s \
  --cloud-storage-bucket-name 'azure://<blog-storage-name>' \
  --cloud-storage-bucket-endpoint 'https://<storage-account>.blob.core.windows.net'

anyscale cloud register \
  --name michaelz-cluster \
  --region westus \
  --provider azure \
  --compute-stack k8s \
  --cloud-storage-bucket-name 'azure://michaelz-anyscale-demo-blob' \
  --cloud-storage-bucket-endpoint 'https://michaelzanyscaledemosa.blob.core.windows.net'
```
the first time i did this it timed out after 10 minutes

which happened twice but on the third time the command succeeded

not sure if it's because i was on a brand new account or some other issue

after command succeeded it gave the following output
```
Output
(anyscale +23.2s) Cloud registration complete! To install the Anyscale operator, run:

helm upgrade <release-name> anyscale/anyscale-operator \
  --set-string global.cloudDeploymentId=cldrsrc_tzte8v44g14txs7vsd39r3xt44 \
  --set-string global.cloudProvider=azure \
  --set-string global.auth.anyscaleCliToken=$ANYSCALE_CLI_TOKEN \
  --set-string workloads.serviceAccount.name=anyscale-operator \
  --namespace <namespace> \
  --create-namespace \
  --wait \
  -i
```

went to anyscale console to get my CLI token and ran thin
```
export ANYSCALE_CLI_TOKEN=...
```

Then I ran
```
helm repo add anyscale https://anyscale.github.io/helm-charts
helm repo update
helm upgrade anyscale-operator anyscale/anyscale-operator \
  --set-string global.cloudDeploymentId=cldrsrc_tzte8v44g14txs7vsd39r3xt44 \
  --set-string global.cloudProvider=azure \
  --set-string global.auth.anyscaleCliToken=$ANYSCALE_CLI_TOKEN \
  --set-string workloads.serviceAccount.name=anyscale-operator \
  --namespace ao-ns \
  --create-namespace \
  --wait \
  -i
```

### trying to get a job to run

I copied over the `main.py` and `job.yaml` from the hello world job from https://github.com/anyscale/examples

I edited the `job.yaml` so that it has the env var `AZURE_STORAGE_ACCOUNT: michaelzanyscaledemosa`

and that it uses my newly setup cloud `cloud: michaelz-cluster`

then i ran this command which failed
```
anyscale job submit -f job.yaml --wait

Output
(anyscale +0.9s) Submitting job with config JobConfig(name='my-first-job', image_uri=None, compute_config=None, env_vars={'EXAMPLE_ENV_VAR': 'EXAMPLE_VAL', 'AZURE_STORAGE_ACCOUNT': 'michaelzanyscaledemosa'}, py_modules=None, py_executable=None, cloud='michaelz-cluster', project=None, ray_version=None, job_queue_config=None, tags=None).
Error: API Exception (400) from GET /cluster_computes/default
Reason: Bad Request
HTTP response body: {"error":{"detail":"No CPU instance types found for this cloud. Add some instance types to the cloud, or specify a custom compute configuration."}}
Trace ID: ['x-trace-id', '701efe7a38e529de740c4a191a4a7e']
```

### fixing missing AZURE_CLIENT_ID
after some debugging i realized the anyscale operator pods were crashing
```
kubectl get pods -n ao-ns

NAME                                 READY   STATUS             RESTARTS        AGE
anyscale-operator-65d77864f4-qs6xk   2/3     CrashLoopBackOff   6 (4m59s ago)   13m
```

from looking at the logs it looks like im missing an AZURE_CLIENT_ID
```
kubectl logs -n ao-ns -l app=anyscale-operator -c operator --tail=50
{"level":"info","ts":1762194415.1621463,"msg":"Starting Anyscale Kubernetes Manager.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b"}
{"level":"info","ts":1762194415.1629694,"msg":"Registering to Anyscale control plane.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b"}
{"level":"info","ts":1762194415.6317222,"msg":"Connecting to Kubernetes Operation Provider at cld-8nplnlihn9dyidul24xr63w7vd.anyscale-cloud.dev:443.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762194415.6324937,"msg":"Verifying that the operator has access to list & generate presigned read/write URL's for the provided storage bucket at path \"/cld_8nplnlihn9dyidul24xr63w7vd/cloud-verify\".","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"error","ts":1762194415.6362724,"msg":"Kubernetes manager failed to run: verify cloud resources: attempt to list storage bucket {bucket=michaelz-anyscale-demo-blob, region=westus, endpoint=https://michaelzanyscaledemosa.blob.core.windows.net}: operation failed: list blobs: DefaultAzureCredential: failed to acquire a token.\nAttempted credentials:\n\tEnvironmentCredential: missing environment variable AZURE_CLIENT_ID\n\tWorkloadIdentityCredential: no client ID specified. Check pod configuration or set ClientID in the options\n\tManagedIdentityCredential: failed to authenticate a system assigned identity. The endpoint responded with The client_id parameter or AZURE_CLIENT_ID environment variable must be set\n\t\t\n\tAzureCLICredential: Azure CLI not found on path\n\tAzureDeveloperCLICredential: Azure Developer CLI not found on path","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
```

with some help from claude i realized our metadata needed a `azure.workload.identity/client-id` which was missing
```
kubectl get serviceaccount anyscale-operator -n ao-ns -o jsonpath='{.metadata.annotations}' | jq

{
  "meta.helm.sh/release-name": "anyscale-operator",
  "meta.helm.sh/release-namespace": "ao-ns"
}
```

so i ran this to find the id
```
az identity list --query "[?contains(name, 'anyscale') || contains(name, 'aks')].{Name:name, ClientId:clientId, ResourceGroup:resourceGroup}" -o table

Name                                         ClientId                              ResourceGroup
-------------------------------------------  ------------------------------------  ----------------------------------------------------------
michaelz-anyscale-demo-anyscale-operator-mi  803f0854-b930-480f-8756-7d5aa40952f1  michaelz-anyscale-demo-rg
michaelz-anyscale-demo-agentpool             6c5cc157-1df3-4d25-981e-899706c08de3  MC_michaelz-anyscale-demo-rg_michaelz-anyscale-demo_westus
```

and then ran this to add to the metadata
```
kubectl annotate serviceaccount anyscale-operator -n ao-ns \
  azure.workload.identity/client-id=803f0854-b930-480f-8756-7d5aa40952f1 \
  --overwrite
```

so now the metadata is correct
```
kubectl get serviceaccount anyscale-operator -n ao-ns -o jsonpath='{.metadata.annotations}' | jq

{
  "azure.workload.identity/client-id": "803f0854-b930-480f-8756-7d5aa40952f1",
  "meta.helm.sh/release-name": "anyscale-operator",
  "meta.helm.sh/release-namespace": "ao-ns"
}
```

we delete the existing pod to force it to restart now that the metadata is fixed
```
kubectl delete pod anyscale-operator-65d77864f4-qs6xk -n ao-ns
```

### fixing authentication issue
but our pods are still crashing. the error logs are different now so we are making progress
```
kubectl logs -n ao-ns -l app=anyscale-operator -c operator --tail=50

{"level":"info","ts":1762195612.623059,"msg":"Starting Anyscale Kubernetes Manager.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b"}
{"level":"info","ts":1762195612.6234903,"msg":"Registering to Anyscale control plane.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b"}
{"level":"info","ts":1762195613.010265,"msg":"Connecting to Kubernetes Operation Provider at cld-8nplnlihn9dyidul24xr63w7vd.anyscale-cloud.dev:443.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762195613.0108657,"msg":"Verifying that the operator has access to list & generate presigned read/write URL's for the provided storage bucket at path \"/cld_8nplnlihn9dyidul24xr63w7vd/cloud-verify\".","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"error","ts":1762195613.5582137,"msg":"Kubernetes manager failed to run: verify cloud resources: attempt to list storage bucket {bucket=michaelz-anyscale-demo-blob, region=westus, endpoint=https://michaelzanyscaledemosa.blob.core.windows.net}: operation failed: list blobs: DefaultAzureCredential: failed to acquire a token.\nAttempted credentials:\n\tEnvironmentCredential: incomplete environment variable configuration. Only AZURE_TENANT_ID and AZURE_CLIENT_ID are set\n\tWorkloadIdentityCredential authentication failed. \n\t\tPOST https://login.microsoftonline.com/7d0e8a87-cdaa-435f-a4ad-ad714b7d183e/oauth2/v2.0/token\n\t\t--------------------------------------------------------------------------------\n\t\tRESPONSE 401: 401 Unauthorized\n\t\t--------------------------------------------------------------------------------\n\t\t{\n\t\t  \"error\": \"invalid_client\",\n\t\t  \"error_description\": \"AADSTS700213: No matching federated identity record found for presented assertion subject 'system:serviceaccount:ao-ns:anyscale-operator'. Check your federated identity credential Subject, Audience and Issuer against the presented assertion. https://learn.microsoft.com/entra/workload-id/workload-identity-federation Trace ID: 5d6ffe6c-5519-4507-b1f6-140ffef40000 Correlation ID: 14224090-c53b-4c62-a1de-b37b45e50ff4 Timestamp: 2025-11-03 18:46:53Z\",\n\t\t  \"error_codes\": [\n\t\t    700213\n\t\t  ],\n\t\t  \"timestamp\": \"2025-11-03 18:46:53Z\",\n\t\t  \"trace_id\": \"5d6ffe6c-5519-4507-b1f6-140ffef40000\",\n\t\t  \"correlation_id\": \"14224090-c53b-4c62-a1de-b37b45e50ff4\",\n\t\t  \"error_uri\": \"https://login.microsoftonline.com/error?code=700213\"\n\t\t}\n\t\t--------------------------------------------------------------------------------\n\t\tTo troubleshoot, visit https://aka.ms/azsdk/go/identity/troubleshoot#workload","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
```

looks like the issue is an authentication error with federated identity credentials.

the fix appears to be that we need to create a federated identity credential for the anyscale operator
```
export AKS_OIDC_ISSUER=$(az aks show --name michaelz-anyscale-demo --resource-group michaelz-anyscale-demo-rg --query "oidcIssuerProfile.issuerUrl" -o tsv)

az identity federated-credential create \
  --name anyscale-operator-federated-credential \
  --identity-name michaelz-anyscale-demo-anyscale-operator-mi \
  --resource-group michaelz-anyscale-demo-rg \
  --issuer "$AKS_OIDC_ISSUER" \
  --subject "system:serviceaccount:ao-ns:anyscale-operator" \
  --audiences "api://AzureADTokenExchange"
```

we kill the pods again to force them to restart
```
kubectl delete pod anyscale-operator-65d77864f4-pc694 -n ao-ns
```

And nice! it's finally not crashing anymore
```
❯ kubectl get pods -n ao-ns
NAME                                 READY   STATUS    RESTARTS   AGE
anyscale-operator-65d77864f4-pvn28   3/3     Running   0          36s
❯ kubectl logs -n ao-ns -l app=anyscale-operator -c operator --tail=50

{"level":"info","ts":1762196396.0468192,"msg":"Starting Anyscale Kubernetes Manager.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b"}
{"level":"info","ts":1762196396.0496607,"msg":"Registering to Anyscale control plane.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b"}
{"level":"info","ts":1762196396.3926904,"msg":"Connecting to Kubernetes Operation Provider at cld-8nplnlihn9dyidul24xr63w7vd.anyscale-cloud.dev:443.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196396.3933928,"msg":"Verifying that the operator has access to list & generate presigned read/write URL's for the provided storage bucket at path \"/cld_8nplnlihn9dyidul24xr63w7vd/cloud-verify\".","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5152757,"msg":"Creating resource anyscale-registry-credentials of type secrets.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5252986,"msg":"Applied 1 resource(s) of type secrets: [anyscale-registry-credentials]","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd","operation_id":"5ebb38e1-ec05-424f-8c1f-f8a4bb58e460"}
{"level":"info","ts":1762196398.5255048,"msg":"Successfully wrote image registry secret.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5255568,"msg":"[Service Config Provider] Initializing provider with configmap \"anyscale-operator-configmap\" in namespace \"ao-ns\".","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5305212,"msg":"[Service Config Provider] Creating empty configmap \"anyscale-operator-configmap\" in namespace \"ao-ns\".","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5404656,"msg":"[Service Config Provider] Successfully merged service configuration, took 9.919866ms.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5405135,"msg":"[Service Config Provider] Provider initialized with initial configuration: ","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5405993,"msg":"[Async Event Producer] Starting to watch for events.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5456212,"msg":"Server listening at 127.0.0.1:3915 . . .","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5459762,"msg":"Leader election is disabled. Starting reconciliation...","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196398.5467062,"msg":"Verifying that the operator has access to list & generate presigned read/write URL's for the provided storage bucket at path \"/cld_8nplnlihn9dyidul24xr63w7vd/cloud-verify\".","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196399.5920959,"msg":"Creating resource anyscale-cldrsrc-tzte8v44g14txs7vsd39r3xt44-certificate of type secrets.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196399.5982945,"msg":"[Service Config Provider] Successfully merged service configuration, took 11.448162ms.","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd"}
{"level":"info","ts":1762196399.6032257,"msg":"Applied 1 resource(s) of type secrets: [anyscale-cldrsrc-tzte8v44g14txs7vsd39r3xt44-certificate]","container_name":"kubernetes_manager","version":"fa65a506820a54d547e64f0ea9205b6b0f4f2d3b","cloud_id":"cld_8nplnlihn9dyidul24xr63w7vd","operation_id":"770341c4-54a4-47c1-a144-06f49153cf0d"}
```

and running the job finally works!!!
```
anyscale job submit -f job.yaml --wait
```

### storage account cors issue
in the anyscale console I ran into an issue where I couldn't access the application logs due to a CORS issue.

to update the cors config of the storage account, I ran the following commands
```
STORAGE_KEY=$(az storage account keys list \
  --account-name michaelzanyscaledemosa \
  --resource-group michaelz-anyscale-demo-rg \
  --query "[0].value" -o tsv)

az storage cors add \
  --services b \
  --methods GET HEAD POST PUT DELETE OPTIONS \
  --origins "*" \
  --allowed-headers "*" \
  --exposed-headers "*" \
  --max-age 3600 \
  --account-name michaelzanyscaledemosa \
  --account-key $STORAGE_KEY
```

wait a bit for the cors config to propagate and the logs should show up in the console.

### references
https://github.com/anyscale/terraform-kubernetes-anyscale-foundation-modules/tree/main/examples/azure/aks-new_cluster
