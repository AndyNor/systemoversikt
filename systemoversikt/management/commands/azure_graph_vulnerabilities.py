# -*- coding: utf-8 -*-
import os
import time
import json
import gzip
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
    help = "Import of Defender for Endpoint vulnerabilities (streaming, memory-safe)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            choices=["defender", "local"],
            default="defender",
        )
        parser.add_argument(
            "--ignore-schedule",
            action="store_true",
        )

    def handle(self, **options):
        SOURCE = options["source"]
        IGNORE_SCHEDULE = options["ignore_schedule"]

        INTEGRASJON_KODEORD = "azure_vulnerabilities"
        LOG_EVENT_TYPE = "Azure defender vulnerabilities"

        SCRIPT_NAVN = os.path.basename(__file__)
        runtime_t0 = time.time()

        run_ts = timezone.now()

        # ------------------------------------------------------------
        # Integration config
        # ------------------------------------------------------------
        int_config, _ = IntegrasjonKonfigurasjon.objects.get_or_create(
            kodeord=INTEGRASJON_KODEORD,
            defaults={
                "kilde": "Azure Defender",
                "protokoll": "REST",
                "informasjon": "Sårbarheter fra Defender for Endpoint",
                "frekvensangivelse": "Ukentlig",
                "log_event_type": LOG_EVENT_TYPE,
            },
        )

        int_config.script_navn = SCRIPT_NAVN
        int_config.helsestatus = "Forbereder"
        int_config.save()

        print(f"[{timezone.now()}] Starter {SCRIPT_NAVN} (source={SOURCE})")

        try:
            # ------------------------------------------------------------
            # Weekday guard
            # ------------------------------------------------------------
            if (
                SOURCE == "defender"
                and not IGNORE_SCHEDULE
                and timezone.now().weekday() != 4
            ):
                msg = "Skipping run – Defender ingestion only executes on Friday"
                ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=msg)
                int_config.sist_status = msg
                int_config.helsestatus = "Avbrutt"
                int_config.save()
                return

            # ------------------------------------------------------------
            # Preload caches (IDs only, not payload-sized)
            # ------------------------------------------------------------
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
            files_count = 0

            # ------------------------------------------------------------
            # Defender source
            # ------------------------------------------------------------
            if SOURCE == "defender":
                credential = ClientSecretCredential(
                    tenant_id=os.environ["AZURE_TENANT_ID"],
                    client_id=os.environ["AZURE_ENTERPRISEAPP_CLIENT"],
                    client_secret=os.environ["AZURE_ENTERPRISEAPP_SECRET"],
                )

                token = credential.get_token(
                    "https://api.securitycenter.microsoft.com/.default"
                ).token

                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }

                body = {}
                if int_config.dato_sist_oppdatert:
                    body["sinceTime"] = (
                        int_config.dato_sist_oppdatert
                        .astimezone(timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )

                start = requests.get(
                    "https://api.security.microsoft.com/api/machines/SoftwareVulnerabilitiesExport",
                    headers=headers,
                    json=body,
                    timeout=60,
                )

                if start.status_code == 202:
                    poll_url = start.headers["Location"]
                    for _ in range(60):
                        time.sleep(5)
                        poll = requests.get(poll_url, headers=headers, timeout=60)
                        if poll.status_code == 200:
                            manifest = poll.json()
                            files = manifest.get("value", [])
                            break
                    else:
                        raise TimeoutError("Timed out waiting for Defender export")
                elif start.status_code == 200:
                    manifest = start.json()
                    files = manifest.get("exportFiles", [])
                else:
                    raise RuntimeError(start.text)

                files_count = len(files)
                print(f"[{timezone.now()}] Export ready: {files_count} file(s)")

                # --------------------------------------------------------
                # STREAMING download + gzip + NDJSON
                # --------------------------------------------------------
                for idx, sas_url in enumerate(files, start=1):
                    print(
                        f"[{timezone.now()}] Processing file {idx}/{files_count}"
                    )

                    resp = requests.get(
                        sas_url, stream=True, timeout=300
                    )
                    resp.raise_for_status()

                    with gzip.GzipFile(fileobj=resp.raw) as gz:
                        for line in gz:
                            r = json.loads(line.decode("utf-8"))

                            # Skip non-vulnerability / metadata rows
                            device_id = r.get("deviceId")
                            cve_id = r.get("cveId")

                            if not device_id or not cve_id:
                                continue

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

                            # ------------------------------------------------
                            # Flush in batches (memory safety)
                            # ------------------------------------------------
                            if len(dvs_to_create) >= 5000:
                                self.flush(
                                    devices_to_create,
                                    cves_to_create,
                                    dvs_to_create,
                                    dvs_to_update,
                                )

            # ------------------------------------------------------------
            # Final flush
            # ------------------------------------------------------------
            self.flush(
                devices_to_create,
                cves_to_create,
                dvs_to_create,
                dvs_to_update,
            )

            # ------------------------------------------------------------
            # Resolve old vulnerabilities
            # ------------------------------------------------------------
            cutoff = run_ts - timedelta(days=2)
            resolved = AzureDeviceVulnerability.objects.filter(
                status="active",
                last_seen__lt=cutoff,
            ).update(status="resolved")

            runtime = int(time.time() - runtime_t0)

            msg = (
                f"source={SOURCE}, processed={processed}, "
                f"resolved={resolved}, files={files_count}"
            )

            ApplicationLog.objects.create(
                event_type=LOG_EVENT_TYPE,
                message=msg,
            )

            int_config.dato_sist_oppdatert = run_ts
            int_config.sist_status = msg
            int_config.runtime = runtime
            int_config.elementer = processed
            int_config.helsestatus = "Vellykket"
            int_config.save()

            print(msg)

        except Exception as e:
            msg = f"{SCRIPT_NAVN} feilet: {e}"
            ApplicationLog.objects.create(
                event_type=LOG_EVENT_TYPE,
                message=msg,
            )
            int_config.helsestatus = msg
            int_config.save()
            push_pushover(msg)
            raise

    # ------------------------------------------------------------
    # Helper: bulk flush
    # ------------------------------------------------------------
    def flush(self, devices, cves, create, update):
        with transaction.atomic():
            if devices:
                AzureDevice.objects.bulk_create(
                    devices, ignore_conflicts=True, batch_size=1000
                )
                devices.clear()

            if cves:
                CVE.objects.bulk_create(
                    cves, ignore_conflicts=True, batch_size=1000
                )
                cves.clear()

            if create:
                AzureDeviceVulnerability.objects.bulk_create(
                    create, batch_size=2000
                )
                create.clear()

            if update:
                AzureDeviceVulnerability.objects.bulk_update(
                    update,
                    fields=["last_seen", "severity", "status"],
                    batch_size=2000,
                )
                update.clear()