# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *
import os, requests, json

class Command(BaseCommand):
	def handle(self, **options):

		client_credential = ClientSecretCredential(
				tenant_id=os.environ['AZURE_TENANT_ID'],
				client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
				client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
		)
		api_version = "v1.0"
		client = GraphClient(credential=client_credential, api_version=api_version)

		users = ['xx', 'xy']

		def create_batch_request(users):
			requests = []
			for i, user in enumerate(users):
				requests.append({
					"id": str(i + 1),
					"method": "GET",
					"url": f"/users/{user}/authentication/methods"
				})
			return {"requests": requests}

		batch_payload = create_batch_request(users)
		response = client.post('/$batch', json=batch_payload)
		response_data = response.json()

		for result in response_data.get('responses', []):
			user_id = result['id']
			status = result['status']
			body = result['body']
			print(f"User ID: {user_id}, Status: {status}, Body: {json.dumps(body, indent=2)}")