import sys
import socket
import win32net
from datetime import datetime
import pandas as pd
import numpy as np
import json
from django.core.management.base import BaseCommand

class Command(BaseCommand):
	def handle(self, **options):

		dfRaw = pd.read_excel('systemoversikt\\management\\commands\\lokalt\\servere.xlsx', sheet_name='eksport')
		dfRaw = dfRaw.replace(np.nan, '', regex=True)
		targets = dfRaw.to_dict('records')
		timeout = 0.2
		ports = [
				#(25, "SMTP"),
				(3389, "RDP"),
				#(445, "SMB"),
			]
		open_hosts = []
		shares = []
		count_targets = len(targets)

		# Add Banner
		print("-" * 50)
		print("Scanning started at: " + str(datetime.now()))
		print("Scanning ports ", ports)
		print("-" * 50)
		print(f"Hosts: {count_targets}")
		print("\n")

		index = 0
		for target in targets:
			index += 1
			try:
				target_name = target['Maskinnavn'].strip("(søk AD)").strip("\n").strip("\t").strip()
				print(f"{index}/{count_targets}: Scanning {target_name} IP {target['IP']}..")
				for port in ports:
					if target['IP'] != '' and target_name != '':
						if "cxa" in target_name.lower():
							continue
						s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
						s.settimeout(timeout)
						result = s.connect_ex((target['IP'], port[0]))
						s.close()

						if result == 0:
							print(f"*** {target['Business service']} {target_name} {target['IP']} port {port[1]} is open")
							open_hosts.append({
								"server_name": target_name,
								"business_service": target['Business service'],
								"server_ip": target['IP'],
								"open_port": port[1],
								})
				"""
				try:
					shares, _, _ = win32net.NetShareEnum(target_name, 0)
					print(f"+++ {target['Business service']} {target_name} {target['IP']} has shares: {shares}")
					shares.append({
							"server_name": target_name,
							"business_service": target['Business service'],
							"server_ip": target['IP'],
							"shares": shares,
						})
				except:
					pass
				"""
			except KeyboardInterrupt:
				sys.exit()
			except:
				print(f"Error with {target}")

		print("-" * 50)
		print("Scanning stopped at:" + str(datetime.now()))
		print("-" * 50)

		print("Saving to file..")
		with open('systemoversikt\\management\\commands\\lokalt\\scan_result.json', 'w', encoding='utf-8') as f:
			json.dump(open_hosts, f, ensure_ascii=False, indent=4)
		#with open('systemoversikt\\management\\commands\\lokalt\\scan_share_result.json', 'w', encoding='utf-8') as f:
		#	json.dump(shares, f, ensure_ascii=False, indent=4)
		print("Done")

