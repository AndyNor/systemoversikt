# -*- coding: utf-8 -*-
# Change log:
# 2026-06-30: Clearer 403 hint – ServiceMessage.Read.All on enterprise app.
# 2026-06-30: Fetch latest service announcement messages from Microsoft Graph.
import os

import requests
from azure.identity import ClientSecretCredential


SERVICE_ANNOUNCEMENT_MESSAGES_URL = (
	"https://graph.microsoft.com/v1.0/admin/serviceAnnouncement/messages"
)

GRAPH_403_HINT = (
	"HTTP 403 fra denne endepunktet betyr vanligvis at enterprise-appen "
	"(AZURE_ENTERPRISEAPP_CLIENT) mangler application permission "
	"ServiceMessage.Read.All med admin consent. Legg til i Entra ID → "
	"App registrations → API permissions → Microsoft Graph → "
	"Application permissions → ServiceMessage.Read.All, og klikk "
	"«Grant admin consent»."
)


def _format_graph_error(response):
	body = response.text[:500]
	if response.status_code == 403:
		return f"Microsoft Graph returnerte HTTP 403: {body}\n\n{GRAPH_403_HINT}"
	return f"Microsoft Graph returnerte HTTP {response.status_code}: {body}"


def fetch_latest_service_announcement_messages(limit=10):
	"""
	Fetch the latest service update messages from Microsoft Graph.

	Returns (messages, error_message). messages is a list of dicts; error_message is
	set when the call fails or credentials are missing.
	"""
	try:
		credential = ClientSecretCredential(
			tenant_id=os.environ['AZURE_TENANT_ID'],
			client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
			client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
		)
	except KeyError as exc:
		return [], f"Mangler Azure-miljøvariabel: {exc.args[0]}"

	token = credential.get_token("https://graph.microsoft.com/.default").token
	headers = {"Authorization": f"Bearer {token}"}
	params = {
		"$top": limit,
		"$orderby": "lastModifiedDateTime desc",
	}

	try:
		response = requests.get(
			SERVICE_ANNOUNCEMENT_MESSAGES_URL,
			headers=headers,
			params=params,
			timeout=60,
		)
	except requests.RequestException as exc:
		return [], f"Microsoft Graph-kall feilet: {exc}"

	if response.status_code != 200:
		return [], _format_graph_error(response)

	messages = response.json().get("value", [])
	messages.sort(key=lambda m: m.get("lastModifiedDateTime", ""), reverse=True)
	return messages[:limit], None
