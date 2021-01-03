from django.core.management.base import BaseCommand
import os

from office365.runtime.auth.authentication_context import AuthenticationContext
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File

class Command(BaseCommand):
	def handle(self, **options):

		files = [
			"OK - CMDB - BS - BSS - DB_Oracle.xlsx",
			"OK - Kartoteket - SQL with BSS.xlsx",
			"OK - Kartoteket Computers with type.xlsx",
			"Oslo Kommune - CMDB - Computer with BS and BSS - Ken Persen NY.xlsx",
			"OK - Kartoteket - Disk Information.xlsx",
			"OK - Kartoketet Business Services.xlsx",
		]

		username = os.environ["AZUREAD_USER"]
		password = os.environ["AZUREAD_PASSWORD"]
		tenant_url = os.environ["2S_PORTAL_URL"]
		folder = os.environ["2S_PORTAL_PATH"]

		def download(tenant_url, folder, file):
			file_path = "%s%s" % (folder, file)
			ctx_auth = AuthenticationContext(tenant_url)
			ctx_auth.acquire_token_for_user(username, password)
			# ctx_auth.with_client_certificate(tenant, client_id, thumbprint, cert_path)
			# ctx_auth.acquire_token_for_app(client_id, client_secret)

			ctx = ClientContext(tenant_url, ctx_auth)
			target = "%s%s%s" % (os.path.dirname(os.path.abspath(__file__)), "/import/", file)
			response = File.open_binary(ctx, file_path)
			with open(target, "wb") as local_file:
				local_file.write(response.content)

		download(tenant_url, folder, files[0])