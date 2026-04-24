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
    help = "Import of Defender for Endpoint vulnerabilities (defender or local source)"

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
        start_ts = timezone.now()
        start_time = time.time()

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
        int_config.helsestatus = "Starter"
        int_config.sist_status = f"Oppstart: source={SOURCE}, ignore_schedule={IGNORE_SCHEDULE}"
        int_config.save()

        print(f"[{start_ts}] Starter {SCRIPT_NAVN}")
        print(f"  Source          : {SOURCE}")
        print(f"  Ignore schedule : {IGNORE_SCHEDULE}")

        try:
            # --------------------------------------------------------
            # Weekday guard
            # --------------------------------------------------------
            if SOURCE == "defender" and not IGNORE_SCHEDULE and start_ts.weekday() != 4:
                msg = "Avbrutt: Defender-kjøring kun tillatt fredag"
                print(msg)

                ApplicationLog.objects.create(
                    event_type=LOG_EVENT_TYPE, message=msg
                )

                int_config.helsestatus = "Avbrutt"
                int_config.sist_status = msg
                int_config.save()
                return

            # --------------------------------------------------------
            # Preload caches
            # --------------------------------------------------------
            print("Laster eksisterende databuffer …")
            int_config.helsestatus = "Laster cache"
            int_config.sist_status = "Laster eksisterende enheter / CVE / sårbarheter"
            int_config.save()

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
            files = []

            # --------------------------------------------------------
            # Source: DEFENDER
            # --------------------------------------------------------
            if SOURCE == "defender":
                print("Starter Defender Export API")
                int_config.helsestatus = "Starter Defender eksport"
                int_config.save()

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
                    print("Eksport er asynkron – venter på ferdigstillelse")
                    for _ in range(60):
                        time.sleep(5)
                        poll = requests.get(poll_url, headers=headers, timeout=60)
                        if poll.status_code == 200:
                            files = poll.json().get("value", [])
                            break
                    else:
                        raise TimeoutError("Tidsavbrudd ved Defender-eksport")
                elif start.status_code == 200:
                    files = start.json().get("exportFiles", [])
                else:
                    raise RuntimeError(start.text)

            # --------------------------------------------------------
            # Source: LOCAL
            # --------------------------------------------------------
            else:
                print("Kjører i LOCAL-modus (kun filsystem)")
                int_config.helsestatus = "Local modus"
                int_config.sist_status = "Leser filer fra disk"
                int_config.save()

                base_dir = os.path.dirname(os.path.dirname(__file__))
                local_dir = os.path.join(base_dir, "import", "defender")

                if not os.path.isdir(local_dir):
                    raise RuntimeError(f"Local import directory mangler: {local_dir}")

                for name in sorted(os.listdir(local_dir)):
                    if name.endswith(".json"):
                        files.append(os.path.join(local_dir, name))

            files_count = len(files)
            print(f"Antall filer å prosessere: {files_count}")

            # --------------------------------------------------------
            # Processing loop
            # --------------------------------------------------------
            for idx, source in enumerate(files, start=1):
                phase = f"Prosesserer fil {idx}/{files_count}"
                print(phase)

                int_config.helsestatus = phase
                int_config.sist_status = os.path.basename(source)
                int_config.save()

                if SOURCE == "defender":
                    resp = requests.get(source, stream=True, timeout=300)
                    resp.raise_for_status()
                    stream = gzip.GzipFile(fileobj=resp.raw)

                    with stream as fh:
                        for line in fh:
                            r = json.loads(line.decode("utf-8"))
                            processed += self._process_record(
                                r, run_ts=start_ts,
                                devices=devices,
                                cves=cves,
                                dvs=dvs,
                                devices_to_create=devices_to_create,
                                cves_to_create=cves_to_create,
                                dvs_to_create=dvs_to_create,
                                dvs_to_update=dvs_to_update,
                            )

                else:
                    with open(source, "r", encoding="utf-8") as fh:
                        payload = json.load(fh)

                    records = payload.get("value", []) if isinstance(payload, dict) else payload

                    for r in records:
                        processed += self._process_record(
                            r, run_ts=start_ts,
                            devices=devices,
                            cves=cves,
                            dvs=dvs,
                            devices_to_create=devices_to_create,
                            cves_to_create=cves_to_create,
                            dvs_to_create=dvs_to_create,
                            dvs_to_update=dvs_to_update,
                        )

                if len(dvs_to_create) >= 5000:
                    self.flush(devices_to_create, cves_to_create, dvs_to_create, dvs_to_update)

            # --------------------------------------------------------
            # Final flush
            # --------------------------------------------------------
            self.flush(devices_to_create, cves_to_create, dvs_to_create, dvs_to_update)

            cutoff = start_ts - timedelta(days=2)
            resolved = AzureDeviceVulnerability.objects.filter(
                status="active",
                last_seen__lt=cutoff,
            ).update(status="resolved")

            runtime = int(time.time() - start_time)

            summary = (
                f"source={SOURCE}, ignore_schedule={IGNORE_SCHEDULE}, "
                f"files={files_count}, processed={processed}, "
                f"resolved={resolved}, runtime={runtime}s"
            )

            ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=summary)

            int_config.dato_sist_oppdatert = start_ts
            int_config.sist_status = summary
            int_config.runtime = runtime
            int_config.elementer = processed
            int_config.helsestatus = "Vellykket"
            int_config.save()

            print(summary)

        except Exception as e:
            msg = f"{SCRIPT_NAVN} feilet: {e}"
            ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=msg)
            int_config.helsestatus = "Feil"
            int_config.sist_status = msg
            int_config.save()
            push_pushover(msg)
            raise

    # ------------------------------------------------------------
    # Record processing helper (no logic change)
    # ------------------------------------------------------------
    def _process_record(
        self, r, run_ts,
        devices, cves, dvs,
        devices_to_create, cves_to_create,
        dvs_to_create, dvs_to_update,
    ):
        device_id = r.get("machineId")
        cve_id = r.get("cveId")

        if not device_id or not cve_id:
            return 0

        device = devices.get(device_id)
        if not device:
            device = AzureDevice(
                device_id=device_id,
                hostname=r.get("machineName", ""),
                os_platform=r.get("osPlatform", ""),
            )
            devices[device_id] = device
            devices_to_create.append(device)

        cve = cves.get(cve_id)
        if not cve:
            cve = CVE(
                cve_id=cve_id,
                severity=r.get("severity", "Unknown"),
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
                    product_name=r.get("productName", ""),
                    product_vendor=r.get("productVendor", ""),
                    product_version=r.get("productVersion", ""),
                    fixing_kb=r.get("fixingKbId"),
                    severity=r.get("severity", "Unknown"),
                    status="active",
                    first_seen=run_ts,
                    last_seen=run_ts,
                )
            )
        else:
            dv.last_seen = run_ts
            dv.severity = r.get("severity", dv.severity)
            dv.status = "active"
            dvs_to_update.append(dv)

        return 1

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