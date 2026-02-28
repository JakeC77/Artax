Prerequisites: Be sure you have Docker installed and running on your local machine.

## Step 1: Build and Deploy container to Azure Container Registry

In order to push to the container registry you must provide the login server to the build and push script. This is in the "Login Server" field of the container registry overview.

Navigate to the `app` directory and run the build script:

```powershell
.\build-and-push.ps1
```

When prompted, provide:
- **AcrName**: `geodesicworks-avfncfc8ewchexfx.azurecr.io`
- **ImageName**: `geodesicworks-ai-app` (or your desired image name)

## Step 2: Deploying the Azure Container App

Once the build-and-push script has completed, the new image is ready to be used in the Azure Container Registry and tagged with the :latest tag. You can double check the image was update in the ACR Repositories here:

https://portal.azure.com/#@GeodesicWorks.onmicrosoft.com/resource/subscriptions/E20abe73-d17c-4337-a393-fdc79db9a1cc/resourceGroups/rg-sbx-app-westus3-01/providers/Microsoft.ContainerRegistry/registries/geodesicworks/repository

Next you'll need to deploy a new revision of the ContainerApp. Got to the panel in Azure for this application

https://portal.azure.com/#@GeodesicWorks.onmicrosoft.com/resource/subscriptions/E20abe73-d17c-4337-a393-fdc79db9a1cc/resourceGroups/rg-sbx-app-westus3-01/providers/Microsoft.App/containerApps/sbx-wrkr-westus3-01/containerapp

Go to the "Revisions and Replicas" tab and click "Create new revision"

Give it a unique name/suffix and then go down and click the link in the table under the "Container Image" setting. You should not need to adjust anything except the information on the properties tab. In this tab, make sure the Image source is set to Azure Container Registry.

Then select Geodesic-Sandbox as the subscription 
(note: there is a bug for me in Azure UI where the Geodesic-Sandbox selection gets wiped after the first time I select it. If that happens, select it again and it should stick the second time.)

After you select the subscription, you should be able to select from a list of container images. Find the one that matches the name of the container you passed into the build-and-push script, then select the latest as the image tag.

If you need to add a new environment variable to the deployment, you can do so by going to the "Environment Variables" tab and adding the new value. Support for secrets will be coming as soon as I figure out where access for them is getting blocked.

Once you've made those selections, hit save, and then hit create on the Create and Deploy New Revision screen. 

This should trigger the ContainerApp to redeploy with the new image. You can keep an eye on the status of the deployment in the Revisions tab and get links to logs if you need to troubleshoot.


