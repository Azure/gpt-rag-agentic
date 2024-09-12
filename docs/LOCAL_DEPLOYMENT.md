## Running locally with VS Code

To contribute, test, or debug, you can run the **orchestrator** locally in VS Code.  
   
Ensure proper provisioning of cloud resources as per instructions in the [Enterprise RAG repo](https://github.com/Azure/GPT-RAG?tab=readme-ov-file#getting-started) before local deployment of the orchestrator.

Once the cloud resources (such as CosmosDB and KeyVault) have been provisioned as per the instructions mentioned earlier, follow these steps:  
   
1. Clone this repository.  
   
2. Ensure that your VS Code has the following extensions installed:  
  
   - [Azure Functions](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions)  
   - [Azurite (blob storage emulator)](https://marketplace.visualstudio.com/items?itemName=Azurite.azurite)  
   
3. Refer to the section below [Roles you have to ...](#roles-you-have-to-assign-to-your-user) to grant your user the necessary permissions to access the cloud resources.  
   
4. Open VS Code in the directory where you cloned the repository.  
   
5. When opening it for the first time, create a virtual environment and point it to [Python version 3.10](https://www.python.org/downloads/release/python-31011/) or higher. <BR>Follow the examples illustrated in the images below.  

![Creating Python Environment 01](../media/06.03.2024_12.15.23_REC.png)

![Creating Python Environment 02](../media/06.03.2024_12.16.15_REC.png)
   
6. Create a copy and then rename the file `local.settings.json.template` to `local.settings.json` and update it with your environment information.  
   
7. Before running the function locally, start the Azurite storage emulator. You can do this by double-clicking [Azurite Blob Service], located in the bottom right corner of the status bar.

8. Done! Now you just need to hit F5 (Start Debugging) to run the orchestrator function at  `http://localhost:7071/api/orc`.

**Note:** you can download this [Postman Collection](../tests/gpt-rag-orchestration.postman_collection.json) to test your orchestrator endpoint.

### Roles you have to assign to your user

Since we're now using managed identities you will have to assign some roles to your user:

1. Azure CosmosDB 'Cosmos DB Built-in Data Contributor' role.

*bash*
```
resourceGroupName='your resource group name'
cosmosDbaccountName='CosmosDB Service name'
roleDefinitionId='00000000-0000-0000-0000-000000000002'
principalId='Object id of your user in Microsoft Entra ID'
az cosmosdb sql role assignment create --account-name $cosmosDbaccountName --resource-group $resourceGroupName --scope "/" --principal-id $principalId --role-definition-id $roleDefinitionId
```

*PowerShell*
```
$resourceGroupName='your resource group name'
$cosmosDbaccountName='CosmosDB Service name'
$roleDefinitionId='00000000-0000-0000-0000-000000000002'
$principalId='Object id of your user in Microsoft Entra ID'
New-AzCosmosDBSqlRoleAssignment -AccountName $cosmosDbaccountName -ResourceGroupName $resourceGroupName -RoleDefinitionId $roleDefinitionId -Scope "/" -PrincipalId $principalId
```

2. Azure OpenAI resource 'Cognitive Services OpenAI User' role.

*bash*
```
subscriptionId='your subscription id'
resourceGroupName='your resource group name'
openAIAccountName='Azure OpenAI service name'
principalId='Object id of your user in Microsoft Entra ID'
az role assignment create --role "Cognitive Services OpenAI User" --assignee $principalId --scope /subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName
```

*PowerShell*
```
$subscriptionId='your subscription id'
$resourceGroupName='your resource group name'
$openAIAccountName='Azure OpenAI service name'
$principalId='Object id of your user in Microsoft Entra ID'
New-AzRoleAssignment -ObjectId $principalId -RoleDefinitionName 'Cognitive Services OpenAI User' -Scope "/subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName"
```