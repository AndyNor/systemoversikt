from django.core.management.base import BaseCommand
import csv
from django.contrib.auth.models import User
import systemoversikt.management.commands.sertifikat_sjekker_config as config

class Command(BaseCommand):
	def handle(self, **options):

		num_certificates = 0
		suspicious_requesters = []
		domain = config.domain
		virksomheter = config.virksomheter
		domain_controller_names = config.domain_controller_names
		admin_account_prefix = config.admin_account_prefix
		server_prefixes = config.server_prefixes
		file_sources = config.file_sources
		file_path = config.file_path

		authorized_admin_accounts = config.authorized_admin_accounts
		authorized_admin_accounts = [x.lower() for x in authorized_admin_accounts]

		security_testing_usernames = config.security_testing_usernames
		security_testing_usernames = [x.lower() for x in security_testing_usernames]


		enterprise_admins = config.enterprise_admins
		enterprise_admins = [x.lower() for x in enterprise_admins]

		domain_admins = config.domain_admins
		domain_admins = [x.lower() for x in domain_admins]


		def default_output(counter, requester_name, raw_SAN, raw_cn, serial_nr, notbefore, template, message=""):
			counter += 1
			suspicious_requesters.append(requester_name)
			try:
				requester_full_name = User.objects.get(username__iexact=requester_name)
			except:
				requester_full_name = requester_name

			if "@" in raw_SAN:
				raw_SAN = raw_SAN.split("@")[0]
			try:
				san_full_name = User.objects.get(username__iexact=raw_SAN)
			except:
				san_full_name = raw_SAN

			try:
				cn_full_name = User.objects.get(username__iexact=raw_cn)
			except:
				cn_full_name = raw_cn

			print(f"{counter} {serial_nr} {notbefore} {message} {template}: Requester is {requester_full_name} for CN {cn_full_name} with SAN {san_full_name}")
			return counter


		def analyze(csv_data):
			counter = 0

			for cert in csv_data:
				raw_requestername = cert["RequestRequesterName"]
				raw_cn = cert["CommonName"]
				raw_SAN = cert["SAN"]
				serial_nr = cert["SerialNumber"]
				notbefore = cert["NotBefore"]
				template = cert["CertificateTemplateOid"]

				# prepare the requester name (remove OSLOFELLES\ and trailing $)
				if f"{domain}\\" in raw_requestername.lower():
					requester_name = raw_requestername.lower().split(f"{domain}\\")[1]
					if requester_name[-1] == "$":
						requester_name = requester_name[0:-1]
				else:
					requester_name = raw_requestername


				#known security testers
				if requester_name.lower() in security_testing_usernames:
					counter = default_output(counter, requester_name, raw_SAN, raw_cn, serial_nr, notbefore, template, message="TESTER")
					continue

				# if SAN or CN is enterprise admin, always output warning
				if raw_SAN.lower() in enterprise_admins or raw_cn.lower() in enterprise_admins:
					counter = default_output(counter, requester_name, raw_SAN, raw_cn, serial_nr, notbefore, template, message="ENTERPRISE ADMIN ***")
					continue

				# if SAN or CN is domain admin, always output warning
				if raw_SAN.lower() in domain_admins or raw_cn.lower() in domain_admins:
					counter = default_output(counter, requester_name, raw_SAN, raw_cn, serial_nr, notbefore, template, message="DOMAIN ADMIN ***")
					continue

				# utstedelse mot driftskontoer (Make note this part runs before we ignore other things authorized admin accounts publish)
				if (admin_account_prefix.lower() in raw_cn.lower() or admin_account_prefix.lower() in raw_SAN.lower()):
					if (requester_name.lower() in raw_cn.lower()) and (requester_name.lower() in raw_SAN.lower()):
						continue # This is expected, nothing suspicious
					counter = default_output(counter, requester_name, raw_SAN, raw_cn, serial_nr, notbefore, template, message="ADMIN ACCOUNT")
					continue

				# cases we want to filter out when requester, CN and SAN are the same
				match = False
				for virksomhet in virksomheter:
					if virksomhet.lower() in raw_SAN.lower() and virksomhet.lower() in requester_name.lower() and virksomhet.lower() in raw_cn.lower():
						match = True
						break
				if match:
					continue

				# cases we want to filter out for when from known accounts.
				if requester_name.lower() in authorized_admin_accounts:
					continue

				# filter out where requester is equal to cn and SAN
				if (requester_name.lower() in raw_cn.lower()) and (requester_name.lower() in raw_SAN.lower()):
					continue # This is expected, nothing suspicious

				if requester_name.lower() in raw_cn.lower():
					try:
						email = User.objects.get(username=requester_name.lower()).email
						if email != "":
							if email.lower() in raw_SAN.lower():
								continue # This is expected, nothing suspicious
					except:
						pass # continue checking

				if requester_name.lower() in raw_SAN.lower() and raw_cn == "":
					continue # This is expected, nothing suspicious

				# when domain controllers require a certificate
				match = False
				for name in domain_controller_names:
					if name.lower() in raw_requestername.lower(): # domain controllers, usually OK
						match = True
						break
				if match:
					continue

				# when servers and clients require a certificate
				match = False
				for prefix in server_prefixes:
					if prefix.lower() in raw_requestername.lower() and prefix.lower() in raw_SAN.lower() and (prefix.lower() in raw_SAN.lower() or raw_SAN == ""):
						match = True
						break
				if match:
					continue

				# Only suspicious certificates left
				counter = default_output(counter, requester_name, raw_SAN, raw_cn, serial_nr, notbefore, template, "SUSPICIOUS")

		# Open files and analyze
		for file in file_sources:
			filename = file[0]
			delimiter = file[1]
			print(f"\nOpening file {file_path}{filename}")
			with open(f"{file_path}{filename}", 'r', encoding='latin-1') as file:
				csv_data = list(csv.DictReader(file, delimiter=delimiter))
			analyze(csv_data)
			num_certificates += len(csv_data)

		# reporting
		print(f"\nAnalyserte {num_certificates} sertifikater")

		suspicious_requesters = set(suspicious_requesters)
		print(f"\nMistenkelige identer:")
		for userid in suspicious_requesters:
			try:
				name = User.objects.get(username=userid)
			except:
				name = userid
			print(f"{name}")
