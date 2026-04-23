# -*- coding: utf-8 -*-
import os
import time
import json
import requests
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from azure.identity import ClientSecretCredential

from systemoversikt.views import push_pushover
from systemoversikt.models import (
	IntegrasjonKonfigurasjon,
	ApplicationLog,
	AzureDevice,
	CVE,
	AzureDeviceVulnerability,
)


class Command(BaseCommand):
	help = "Nightly import of Defender for Endpoint vulnerabilities (Export API or local files)"

	def add_arguments(self, parser):
		parser.add_argument(
			"--source",
			choices=["defender", "local"],
			default="defender",
			help="Run from live Defender Export API or from local JSON files",
		)

	def handle(self, **options):
		SOURCE = options["source"]

		INTEGRASJON_KODEORD = "azure_vulnerabilities"
		LOG_EVENT_TYPE = "Azure defender vulnerabilities"
		KILDE = "Azure Defender"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Sårbarheter fra Defender for Endpoint (Export API)"
		FREKVENS = "Ukentlig mandager"

		SCRIPT_NAVN = os.path.basename(__file__)
		runtime_t0 = time.time()

		BASE_DIR = os.path.dirname(os.path.dirname(__file__))
		IMPORT_BASE = os.path.join(BASE_DIR, "import")
		DEFENDER_DIR = os.path.join(IMPORT_BASE, "defender")

		os.makedirs(DEFENDER_DIR, exist_ok=True)

		try:
			int_config, _ = IntegrasjonKonfigurasjon.objects.get_or_create(
				kodeord=INTEGRASJON_KODEORD,
				defaults={
					"kilde": KILDE,
					"protokoll": PROTOKOLL,
					"informasjon": BESKRIVELSE,
					"frekvensangivelse": FREKVENS,
					"log_event_type": LOG_EVENT_TYPE,
				},
			)

			int_config.script_navn = SCRIPT_NAVN
			int_config.helsestatus = "Forbereder"
			int_config.save()

			print(f"[{timezone.now()}] Starter {SCRIPT_NAVN} (source={SOURCE})")

			# ------------------------------------------------------------
			# Only enforce Wednsday-run for Defender source
			# ------------------------------------------------------------
			if SOURCE == "defender" and timezone.now().weekday() != 2:
				message = "Skipping run – Defender ingestion only executes on Wednsday"
				ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=message,
				)
				int_config.sist_status = message
				int_config.helsestatus = "Avbrutt"
				int_config.save()
				print(message)
				return

			run_ts = timezone.now()
			payloads = []
			files_count = 0

			# ------------------------------------------------------------------
			# SOURCE = DEFENDER (export + save locally)
			# ------------------------------------------------------------------
			if SOURCE == "defender":
				credential = ClientSecretCredential(
					tenant_id=os.environ["AZURE_TENANT_ID"],
					client_id=os.environ["AZURE_ENTERPRISEAPP_CLIENT"],
					client_secret=os.environ["AZURE_ENTERPRISEAPP_SECRET"],
				)

				token = credential.get_token(
					"https://api.security.microsoft.com/.default"
				).token

				headers = {
					"Authorization": f"Bearer {token}",
					"Accept": "application/json",
					"Content-Type": "application/json",
				}

				DEFENDER_API = "https://api.security.microsoft.com"
				EXPORT_ENDPOINT = "/api/machines/SoftwareVulnerabilitiesExport"

				body = {}
				if int_config.dato_sist_oppdatert:
					body["sinceTime"] = (
						int_config.dato_sist_oppdatert
						.astimezone(timezone.utc)
						.isoformat()
						.replace("+00:00", "Z")
					)

				# --------------------------------------------------
				# 1. Start export job (GET — yes, GET)
				# --------------------------------------------------
				response = requests.get(
					DEFENDER_API + EXPORT_ENDPOINT,
					headers=headers,
					json=body,
					timeout=60,
				)

				if response.status_code != 202:
					raise RuntimeError(
						f"Export job start failed: {response.status_code} {response.text}"
					)

				export_location = response.headers.get("Location")
				if not export_location:
					raise RuntimeError("No Location header returned from export API")

				# --------------------------------------------------
				# 2. Poll export job until ready
				# --------------------------------------------------
				manifest = None
				for _ in range(60):  # ~5 minutes max
					time.sleep(5)
					status_resp = requests.get(
						export_location,
						headers=headers,
						timeout=60,
					)

					if status_resp.status_code == 200:
						manifest = status_resp.json()
						break
					elif status_resp.status_code not in (202, 204):
						raise RuntimeError(
							f"Export polling failed: "
							f"{status_resp.status_code} {status_resp.text}"
						)

				if not manifest:
					raise TimeoutError("Timed out waiting for Defender export to complete")

				manifest_path = os.path.join(
					DEFENDER_DIR,
					f"manifest_{run_ts.isoformat()}.json",
				)
				with open(manifest_path, "w", encoding="utf-8") as f:
					json.dump(manifest, f, indent=2)

				files = manifest.get("value", [])
				files_count = len(files)

				# --------------------------------------------------
				# 3. Download payload files
				# --------------------------------------------------
				for idx, entry in enumerate(files, start=1):
					sas_url = entry["sasUri"]
					file_resp = requests.get(sas_url, timeout=300)
					file_resp.raise_for_status()
					payload = file_resp.json()
					payloads.append(payload)

					payload_path = os.path.join(
						DEFENDER_DIR,
						f"payload_{idx:03d}.json",
					)
					with open(payload_path, "w", encoding="utf-8") as f:
						json.dump(payload, f)


			# ------------------------------------------------------------------
			# SOURCE = LOCAL (load payload_*.json)
			# ------------------------------------------------------------------
			else:
				for fname in sorted(os.listdir(DEFENDER_DIR)):
					if fname.startswith("payload_") and fname.endswith(".json"):
						with open(
							os.path.join(DEFENDER_DIR, fname),
							encoding="utf-8",
						) as f:
							payloads.append(json.load(f))

				files_count = len(payloads)

				if not payloads:
					raise RuntimeError("No local Defender payload files found")

			# ------------------------------------------------------------------
			# Preload caches
			# ------------------------------------------------------------------
			devices = {d.device_id: d for d in AzureDevice.objects.all()}
			cves = {c.cve_id: c for c in CVE.objects.all()}
			dvs = {
				(dv.device_id, dv.cve_id): dv
				for dv in AzureDeviceVulnerability.objects.all()
			}

			devices_to_create = []
			cves_to_create = []
			dvs_to_create = []
			dvs_to_update = []

			processed = 0

			# ------------------------------------------------------------------
			# Process records
			# ------------------------------------------------------------------
			for payload in payloads:
				for r in payload.get("value", []):
					device_id = r["deviceId"]
					cve_id = r["cveId"]

					device = devices.get(device_id)
					if not device:
						device = AzureDevice(
							device_id=device_id,
							hostname=r.get("deviceName", ""),
							os_platform=r.get("osPlatform", ""),
						)
						devices[device_id] = device
						devices_to_create.append(device)

					cve = cves.get(cve_id)
					if not cve:
						cve = CVE(
							cve_id=cve_id,
							severity=r["severity"],
						)
						cves[cve_id] = cve
						cves_to_create.append(cve)

					key = (device_id, cve_id)

					dv = dvs.get(key)
					if not dv:
						dvs_to_create.append(
							AzureDeviceVulnerability(
								device=device,
								cve=cve,
								product_name=r["productName"],
								product_vendor=r["productVendor"],
								product_version=r["productVersion"],
								fixing_kb=r.get("fixingKbId"),
								severity=r["severity"],
								status="active",
								first_seen=run_ts,
								last_seen=run_ts,
							)
						)
					else:
						dv.last_seen = run_ts
						dv.severity = r["severity"]
						dv.status = "active"
						dvs_to_update.append(dv)

					processed += 1

			# ------------------------------------------------------------------
			# Bulk DB writes
			# ------------------------------------------------------------------
			with transaction.atomic():
				if devices_to_create:
					AzureDevice.objects.bulk_create(
						devices_to_create,
						batch_size=1000,
						ignore_conflicts=True,
					)
				if cves_to_create:
					CVE.objects.bulk_create(
						cves_to_create,
						batch_size=1000,
						ignore_conflicts=True,
					)
				if dvs_to_create:
					AzureDeviceVulnerability.objects.bulk_create(
						dvs_to_create,
						batch_size=2000,
					)
				if dvs_to_update:
					AzureDeviceVulnerability.objects.bulk_update(
						dvs_to_update,
						fields=["last_seen", "severity", "status"],
						batch_size=2000,
					)

			# ------------------------------------------------------------------
			# Mark resolved
			# ------------------------------------------------------------------
			cutoff = run_ts - timedelta(days=2)
			resolved = AzureDeviceVulnerability.objects.filter(
				status="active",
				last_seen__lt=cutoff,
			).update(status="resolved")

			runtime = int(time.time() - runtime_t0)
			message = (
				f"source={SOURCE}, processed={processed}, "
				f"created={len(dvs_to_create)}, updated={len(dvs_to_update)}, "
				f"resolved={resolved}, files={files_count}"
			)

			ApplicationLog.objects.create(
				event_type=LOG_EVENT_TYPE,
				message=message,
			)

			int_config.dato_sist_oppdatert = run_ts
			int_config.sist_status = message
			int_config.runtime = runtime
			int_config.elementer = processed
			int_config.helsestatus = "Vellykket"
			int_config.save()

			print(message)

		except Exception as e:
			message = f"{SCRIPT_NAVN} feilet: {e}"
			ApplicationLog.objects.create(
				event_type=LOG_EVENT_TYPE,
				message=message,
			)
			int_config.helsestatus = message
			int_config.save()
			push_pushover(message)
			raise