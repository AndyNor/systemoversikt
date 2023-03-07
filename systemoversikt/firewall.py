#åpne filen
import pandas as pd
import numpy as np

def parse_groups(data):
	#Laste inn grupper
	return None

excel_file = pd.ExcelFile("firewall_all_ports.xlsx")
print("Fant følgende ark i filen: %s" % excel_file.sheet_names)

all_openings = {}

for sheet in excel_file.sheet_names:
	print("Åpner ark %s" % sheet)

	if sheet == "README":
		continue
	if sheet == "Groups' Content":
		named_network_groups = parse_groups(data=None)
		continue

	df = excel_file.parse(sheet,
				skiprows=2, # de første radene er tomme
				usecols=[2, 3, 4, 7, 9, 10, 14],
				names=['rule_id', 'permit', 'source', 'destination', 'service', 'beskrivelse', 'retning',]
			)
	df['rule_id'].ffill(inplace=True)
	df = df.replace(np.nan, '', regex=True)
	data = df.to_dict('records')
	for line in data:
		try:
			rule_id = int(line["rule_id"])
		except:
			rule_id = "error"

		def lookup_groups(something):
			# det kan være en gruppe. Da returneres alle medlemmer

			# hvis det ikke er noen treff, returnerer vi det vi fant
			return something


		if not rule_id in all_openings:
			all_openings[rule_id] = {
					'firewall': sheet,
					'permit': line["permit"],
					'source': [line["source"]],
					'destination': [line["destination"]],
					'service': [line["service"]],
					'beskrivelse': line["beskrivelse"],
					'retning': line["retning"],
					}
		else:
			if line["source"] != "":
				all_openings[rule_id]["source"].append(line["source"])
			if line["destination"] != "":
				all_openings[rule_id]["destination"].append(line["destination"])



print(len(all_openings))

for opening in all_openings:
	print("Regel %s: %s" % (opening, all_openings[opening]))


#Slå opp tilhørende vlan
# for hver adresse i source eller destination sjekker vi
# først, er det et VLAN eller en enkelt IP.
# hvis IP, identifiser tilhørende vlan
# hvis nettverk, slå det opp.
