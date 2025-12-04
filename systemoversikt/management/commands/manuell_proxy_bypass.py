from django.core.management.base import BaseCommand
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
import requests

class Command(BaseCommand):
	def handle(self, **options):


		# Replace with your values
		CLIENT_ID = ""
		CLIENT_SECRET = ""
		TENANT_ID = ""
		APP_PROXY_URL = "https://kartoteket.oslo.kommune.no/api/vav/akva/"
		# Authority and scope
		AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
		APP_SCOPE = "https://kartoteket.oslo.kommune.no/.default"

		# Create credential
		credential = ClientSecretCredential(
			tenant_id=TENANT_ID,
			client_id=CLIENT_ID,
			client_secret=CLIENT_SECRET
		)

		# Initialize GraphClient
		graph_client = GraphClient(credential=credential)


		# Acquire token for your internal app behind proxy
		token = credential.get_token(APP_SCOPE).token  # Pass a single string here

		# Call the app behind Application Proxy
		headers = {
			"Authorization": f"Bearer {token}",
			"key": f"",
		}
		response = requests.get(APP_PROXY_URL, headers=headers)

		if response.status_code == 200:
			print("Successfully accessed the app:")
			print(response.text)
		else:
			print(f"Failed to access app: {response.status_code} - {response.text}")







