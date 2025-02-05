import os
import logging
import re
from azure.identity.aio import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential
from azure.keyvault.secrets.aio import SecretClient as AsyncSecretClient
from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError

##########################################################
# KEY VAULT 
##########################################################

async def get_secret(secretName):
    try:
        keyVaultName = os.environ["AZURE_KEY_VAULT_NAME"]
        KVUri = f"https://{keyVaultName}.vault.azure.net"
        async with ChainedTokenCredential(
                ManagedIdentityCredential(),
                AzureCliCredential()
            ) as credential:
            async with AsyncSecretClient(vault_url=KVUri, credential=credential) as client:
                retrieved_secret = await client.get_secret(secretName)
                value = retrieved_secret.value
        return value    
    except KeyError:
        logging.info("Environment variable AZURE_KEY_VAULT_NAME not found.")
        return None
    except ClientAuthenticationError:
        logging.info("Authentication failed. Please check your credentials.")
        return None
    except ResourceNotFoundError:
        logging.info(f"Secret '{secretName}' not found in the Key Vault.")
        return None
    except Exception as e:
        logging.info(f"An unexpected error occurred: {e}")
        return None

def generate_valid_secret_name(base_name: str) -> str:
    """
    Generate a valid secret name that contains only alphanumeric characters and dashes.
    
    Args:
        base_name (str): The base name to convert into a valid secret name.
    
    Returns:
        str: A sanitized secret name with only valid characters.
    """
    # Replace any non-alphanumeric characters with dashes
    sanitized_name = re.sub(r'[^a-zA-Z0-9-]', '-', base_name)
    # Ensure it does not start or end with a dash and limit its length
    sanitized_name = sanitized_name.strip('-')[:63]  # Max length for Azure Key Vault secret names is 63
    return sanitized_name or "default-secret"
