# -*- coding: utf-8 -*-
import os
import time
import json
import gzip
import requests
from datetime import timedelta, datetime

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
    help = "Import of Defender for Endpoint vulnerabilities (defender API or local disk)"

    @staticmethod
    def _defender_import_dir():
        base_dir = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(base_dir, "import", "defender")

    @staticmethod
    def _export_urls_from_api_payload(payload):
        """Microsoft documents exportFiles; some responses use value."""
        if not isinstance(payload, dict):
            return []
        return payload.get("exportFiles") or payload.get("value") or []

    @staticmethod
    def _clear_previous_snapshot_exports(local_dir):
        """Remove prior vulnerabilities_NNN.json.gz so each API run replaces disk snapshot."""
        if not os.path.isdir(local_dir):
            return
        for name in os.listdir(local_dir):
            if name.startswith("vulnerabilities_") and name.endswith(".json.gz"):
                try:
                    os.remove(os.path.join(local_dir, name))
                except OSError:
                    pass

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
        int_config.sist_status = f"source={SOURCE}, ignore_schedule={IGNORE_SCHEDULE}"
        int_config.save()

        print(f"[{start_ts}] Starter {SCRIPT_NAVN}")
        print(f"  Source          : {SOURCE}")
        print(f"  Ignore schedule : {IGNORE_SCHEDULE}")

        try:
            if SOURCE == "defender" and not IGNORE_SCHEDULE and start_ts.weekday() != 2:
                msg = "Avbrutt: Defender-kjøring kun tillatt onsdag"
                print(msg)
                ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=msg)
                int_config.helsestatus = "Avbrutt"
                int_config.sist_status = msg
                int_config.save()
                return

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

                start = requests.get(
                    "https://api.security.microsoft.com/api/machines/SoftwareVulnerabilitiesExport",
                    headers=headers,
                    timeout=60,
                )

                if start.status_code == 202:
                    poll_url = start.headers.get("Location")
                    for _ in range(60):
                        time.sleep(5)
                        poll = requests.get(poll_url, headers=headers, timeout=60)
                        if poll.status_code == 200:
                            files = self._export_urls_from_api_payload(poll.json())
                            break
                    else:
                        raise TimeoutError("Tidsavbrudd ved Defender-eksport")
                elif start.status_code == 200:
                    files = self._export_urls_from_api_payload(start.json())
                else:
                    raise RuntimeError(start.text)

                local_dir = self._defender_import_dir()
                os.makedirs(local_dir, exist_ok=True)
                self._clear_previous_snapshot_exports(local_dir)

            else:
                local_dir = self._defender_import_dir()

                if not os.path.isdir(local_dir):
                    raise RuntimeError(f"Local import directory mangler: {local_dir}")

                for name in sorted(os.listdir(local_dir)):
                    lower = name.lower()
                    if lower.endswith(".json.gz") or lower.endswith(".gz"):
                        files.append(os.path.join(local_dir, name))
                    elif name.endswith(".json"):
                        files.append(os.path.join(local_dir, name))

            print(f"Antall filer å prosessere: {len(files)}")

            for idx, item in enumerate(files, start=1):
                print(f"Prosesserer fil {idx}/{len(files)}")

                if SOURCE == "defender":
                    resp = requests.get(item, stream=True, timeout=300)
                    resp.raise_for_status()
                    save_name = f"vulnerabilities_{idx:03d}.json.gz"
                    save_path = os.path.join(local_dir, save_name)
                    with open(save_path, "wb") as out:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                out.write(chunk)
                    print(f"  Lagret: {save_path}")
                    record_iter = (
                        json.loads(line.decode("utf-8"))
                        for line in gzip.open(save_path, "rb")
                    )
                    use_graph_json = False
                else:
                    use_graph_json = item.lower().endswith(".gz")
                    if use_graph_json:
                        record_iter = (
                            json.loads(line.decode("utf-8"))
                            for line in gzip.open(item, "rb")
                        )
                    else:
                        with open(item, "r", encoding="utf-8") as fh:
                            payload = json.load(fh)
                        record_iter = payload.get("value", [])

                for r in record_iter:
                    if SOURCE == "local" and not use_graph_json:
                        device_id = r.get("DeviceId")
                        hostname = r.get("DeviceName", "")
                        os_platform = r.get("OSPlatform", "")
                        cve_id = r.get("CveId")
                        severity = r.get("VulnerabilitySeverityLevel", "Unknown")
                        cvss_score = r.get("CvssScore")
                        product_vendor = r.get("SoftwareVendor", "")
                        product_name = r.get("SoftwareName", "")
                        product_version = r.get("SoftwareVersion", "")
                        fixing_kb = r.get("RecommendedSecurityUpdateId")
                        first_seen = self._parse_ts(r.get("FirstSeenTimestamp"), start_ts)
                        last_seen = self._parse_ts(r.get("LastSeenTimestamp"), start_ts)
                    else:
                        # Defender export / gzip lines: documented JSON uses deviceId, cveId (see Learn).
                        device_id = (
                            r.get("deviceId")
                            or r.get("DeviceId")
                            or r.get("machineId")
                        )
                        hostname = (
                            r.get("deviceName")
                            or r.get("DeviceName")
                            or r.get("machineName")
                            or ""
                        )
                        os_platform = r.get("osPlatform") or r.get("OSPlatform") or ""
                        cve_id = r.get("cveId") or r.get("CveId")
                        severity = (
                            r.get("vulnerabilitySeverityLevel")
                            or r.get("VulnerabilitySeverityLevel")
                            or r.get("severity")
                            or "Unknown"
                        )
                        cvss_score = r.get("CvssScore") or r.get("cvssScore")
                        product_vendor = (
                            r.get("softwareVendor") or r.get("SoftwareVendor") or ""
                        )
                        product_name = r.get("softwareName") or r.get("SoftwareName") or ""
                        product_version = (
                            r.get("softwareVersion") or r.get("SoftwareVersion") or ""
                        )
                        fixing_kb = (
                            r.get("recommendedSecurityUpdateId")
                            or r.get("RecommendedSecurityUpdateId")
                            or r.get("fixingKbId")
                        )
                        first_seen = self._parse_ts(
                            r.get("firstSeenTimestamp") or r.get("FirstSeenTimestamp"),
                            start_ts,
                        )
                        last_seen = self._parse_ts(
                            r.get("lastSeenTimestamp") or r.get("LastSeenTimestamp"),
                            start_ts,
                        )

                    if not device_id or not cve_id:
                        continue

                    device = devices.get(device_id)
                    if not device:
                        device = AzureDevice(
                            device_id=device_id,
                            hostname=hostname,
                            os_platform=os_platform,
                            first_seen=first_seen,
                            last_seen=last_seen,
                        )
                        devices[device_id] = device
                        devices_to_create.append(device)

                    cve = cves.get(cve_id)
                    if not cve:
                        cve = CVE(
                            cve_id=cve_id,
                            severity=severity,
                            cvss_score=cvss_score,
                        )
                        cves[cve_id] = cve
                        cves_to_create.append(cve)

                    key = (device_id, cve_id)
                    dv = dvs.get(key)

                    if not dv:
                        new_dv = AzureDeviceVulnerability(
                            device=device,
                            cve=cve,
                            product_name=product_name,
                            product_vendor=product_vendor,
                            product_version=product_version,
                            fixing_kb=fixing_kb,
                            severity=severity,
                            status="active",
                            first_seen=first_seen,
                            last_seen=last_seen,
                        )
                        dvs_to_create.append(new_dv)
                        dvs[key] = new_dv   # ✅ CRITICAL FIX
                    else:
                        dv.last_seen = last_seen
                        dv.severity = severity
                        dv.status = "active"
                        dvs_to_update.append(dv)

                    processed += 1

                    if len(dvs_to_create) >= 5000:
                        self.flush(devices_to_create, cves_to_create, dvs_to_create, dvs_to_update)

            self.flush(devices_to_create, cves_to_create, dvs_to_create, dvs_to_update)

            resolved = AzureDeviceVulnerability.objects.filter(
                status="active",
                last_seen__lt=(start_ts - timedelta(days=2)),
            ).update(status="resolved")

            runtime = int(time.time() - start_time)

            msg = (
                f"source={SOURCE}, ignore_schedule={IGNORE_SCHEDULE}, "
                f"files={len(files)}, processed={processed}, "
                f"resolved={resolved}, runtime={runtime}s"
            )

            ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=msg)

            int_config.helsestatus = "Vellykket"
            int_config.sist_status = msg
            int_config.runtime = runtime
            int_config.elementer = processed
            int_config.dato_sist_oppdatert = start_ts
            int_config.save()

            print(msg)

        except Exception as e:
            msg = f"{SCRIPT_NAVN} feilet: {e}"
            ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=msg)
            int_config.helsestatus = "Feil"
            int_config.sist_status = msg
            int_config.save()
            push_pushover(msg)
            raise

    def _parse_ts(self, value, default):
        if not value:
            return default
        if isinstance(value, str) and len(value) >= 19:
            # e.g. "2020-11-03 10:13:34.8476880" -> parse first 19 chars
            value = value[:19]
        try:
            return timezone.make_aware(
                datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            )
        except Exception:
            return default

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