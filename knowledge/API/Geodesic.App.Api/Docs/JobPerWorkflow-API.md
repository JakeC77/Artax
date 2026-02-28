# Job-per-workflow API configuration

The API can dispatch workflow runs in two ways:

- **ServiceBus** (default): Sends a message to an Azure Service Bus queue; a long-running worker consumes messages and runs workflows.
- **ContainerAppsJob**: Starts an Azure Container Apps Job per run. The job runs the geodesic-ai image with `python -m app.job_entrypoint` and receives the workflow payload via `PAYLOAD_URL` (or `WORKFLOW_EVENT_JSON` / `PAYLOAD_B64`; see geodesic-ai’s [api-start-job-guide](https://github.com/geodesic-ai/geodesic-ai/blob/main/docs/api-start-job-guide.md)).

Switching mode is configuration-only: set `WorkflowDispatch:Mode` and the corresponding options. No code changes are required for existing deployments until you enable `ContainerAppsJob`. The start request uses the Azure Jobs Start REST API with **api-version=2025-07-01** and a top-level `containers` body as in that guide.

---

## Configuration

### Section: `WorkflowDispatch`

| Key | Description | Default |
|-----|-------------|---------|
| **Mode** | `"ServiceBus"` or `"ContainerAppsJob"` | `"ServiceBus"` |
| **TenantId** | Azure AD tenant ID for the subscription. Set when the subscription is in a different tenant than the default credential (avoids InvalidAuthenticationTokenTenant). | — |
| **SubscriptionId** | Azure subscription ID | — |
| **ResourceGroup** | Resource group containing the Container Apps Job | — |
| **JobName** | Container Apps Job resource name | — |
| **PayloadBlobContainer** | Blob container for workflow payloads (used for PAYLOAD_URL) | — |
| **PayloadSasExpiryMinutes** | SAS URL expiry for the payload blob (minutes) | 60 |
| **ContainerName** | Name of the container in the Job template. Often the same as **JobName** (e.g. `geodesic-workflow-job`); use the job’s template if unsure. | `"main"` |
| **ContainerImage** | Container image for the Start request (e.g. `myacr.azurecr.io/geodesic-ai:latest`). Required by Azure Jobs Start API. | — |

When **Mode** is `ContainerAppsJob`, the following are required: **SubscriptionId**, **ResourceGroup**, **JobName**, **PayloadBlobContainer**, **ContainerImage**. The API uses the same Azure Storage account as the rest of the app (e.g. `AzureStorage:ConnectionString` or `AzureStorage:ServiceUri` with DefaultAzureCredential); only the payload container name is specified under WorkflowDispatch.

Example `appsettings.json`:

```json
{
  "WorkflowDispatch": {
    "Mode": "ContainerAppsJob",
    "TenantId": "<azure-ad-tenant-id-if-subscription-in-different-tenant>",
    "SubscriptionId": "<subscription-id>",
    "ResourceGroup": "my-rg",
    "JobName": "geodesic-workflow-job",
    "PayloadBlobContainer": "workflow-payloads",
    "PayloadSasExpiryMinutes": 60,
    "ContainerName": "main",
    "ContainerImage": "myacr.azurecr.io/geodesic-ai:latest"
  }
}
```

---

## Payload shape

The same payload is used for both Service Bus and Container Apps Job. It matches the geodesic-ai **WorkflowEvent** schema (camelCase; the job also accepts snake_case):

- **Required:** `runId`, `tenantId`, `workspaceId`, `scenarioId` (strings, e.g. GUID)
- **Optional:** `workflowId` (default `"workspace-chat"`), `inputs` (JSON string, default `"{}"`), `prompt`, `relatedChangesetId`, `engine`, `status` (default `"queued"`), `requestedAt` (ISO 8601)

For scenario/engine runs, `workflowId` and `engine` are set from the same value (e.g. the scenario engine). The job receives this payload either in the Service Bus message body or by downloading from `PAYLOAD_URL` (when using ContainerAppsJob). See geodesic-ai’s api-start-job-guide for the full WorkflowEvent reference.

---

## Permissions (ContainerAppsJob)

When **Mode** is `ContainerAppsJob`, the API’s identity (e.g. the app’s managed identity or the credential used at runtime) must be able to:

1. **Start the job**  
   Grant **Microsoft.App/jobs/start/action** on the Container Apps Job (or Contributor on the job or resource group).

2. **Write and create SAS for payloads**  
   The API uploads the workflow payload to the configured **PayloadBlobContainer** and passes a read-only SAS URL to the job. The same storage account as the rest of the app is used; ensure the identity has blob write and SAS create rights on that account/container.

Without these permissions, job start or blob upload will fail and the workflow will not run.

---

## Reference

- **geodesic-ai**: [api-start-job-guide.md](https://github.com/geodesic-ai/geodesic-ai/blob/main/docs/api-start-job-guide.md) (start job endpoint, auth, request body, WorkflowEvent shape).
- **Azure**: [Jobs - Start](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/jobs/start?view=rest-resource-manager-containerapps-2025-07-01) (api-version 2025-07-01).
