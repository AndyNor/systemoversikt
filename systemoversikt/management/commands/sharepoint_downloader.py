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


		tenant_url = "https://steria.sharepoint.com"
		folder = "/:x:/r/sites/Sc_kundeportal_ekstern/637269587014341894/Rapporter/CMDB/"

		def download(tenant_url, folder, file):
			file_path = "%s%s" % (folder, file)
			print(file_path)
			ctx_auth = AuthenticationContext(tenant_url)
			ctx_auth.acquire_token_for_user("username", "passord")
			#ctx_auth.acquire_token_for_app("client_id", "client_secret") # client credentials for
			ctx = ClientContext(tenant_url, ctx_auth)
			target = "%s%s%s" % (os.path.dirname(os.path.abspath(__file__)), "/import/", file)
			print(target)
			response = File.open_binary(ctx, file_path)
			with open(target, "wb") as local_file:
				local_file.write(response.content)

		download(tenant_url, folder, files[0])