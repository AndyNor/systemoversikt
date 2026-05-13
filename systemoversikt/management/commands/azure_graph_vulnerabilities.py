# -*- coding: utf-8 -*-
import os
import time
import json
import gzip
import gc
import requests
from functools import reduce
from operator import or_
from datetime import timedelta, datetime
from urllib.parse import urljoin, urlparse

from collections import OrderedDict

from django.db.models import Q

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


class _BoundedLRUDeviceVulnCache:
    """
    Holder (device_id, cve_id) -> AzureDeviceVulnerability med øvre grense.
    Mest nylig brukte nøkler beholdes (LRU via OrderedDict); sjeldnere par kastes
    ut av minnet og hentes igjen fra DB ved behov.
    Nøkler i pinned_keys evikteres ikke (typisk nye rader før bulk_create).
    """

    __slots__ = ("_max", "_pinned", "_od")

    def __init__(self, max_entries, pinned_keys):
        self._max = max_entries
        self._pinned = pinned_keys
        self._od = OrderedDict()

    def __contains__(self, key):
        return key in self._od

    def __len__(self):
        return len(self._od)

    def get(self, key, default=None):
        if key not in self._od:
            return default
        self._od.move_to_end(key)
        return self._od[key]

    def __getitem__(self, key):
        val = self._od[key]
        self._od.move_to_end(key)
        return val

    def __setitem__(self, key, value):
        if key in self._od:
            del self._od[key]
        self._od[key] = value
        self._od.move_to_end(key)
        self._evict_excess()

    def merge_fetch_results(self, queryset_or_iterable):
        for obj in queryset_or_iterable:
            k = (obj.device_id, obj.cve_id)
            if k in self._od:
                del self._od[k]
            self._od[k] = obj
            self._od.move_to_end(k)
        self._evict_excess()

    def _evict_excess(self):
        while len(self._od) > self._max:
            victim = None
            for k in self._od:
                if k not in self._pinned:
                    victim = k
                    break
            if victim is None:
                break
            del self._od[victim]


class Command(BaseCommand):
    help = (
        "Import av Defender for Endpoint-sårbarheter. "
        "Med --source defender: først nedlasting av alle eksportfiler til disk, "
        "deretter innlasting av database og parsing (spar RAM under nedlasting). "
        "Med --source local: les fra import/defender uten API-kall (nyttig etter feil). "
        "AzureDeviceVulnerability slås opp i batch mot DB (mer CPU, mindre RAM enn full preload). "
        "Oppslag caches i LRU (mest brukte par i RAM); eldre par hentes igjen fra DB ved behov."
    )

    _DEFENDER_TOKEN_SCOPE = "https://api.securitycenter.microsoft.com/.default"

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

    @staticmethod
    def _defender_url_needs_bearer_only(url):
        """
        Azure Storage-URLer (Blob/DFS) bruker ofte SAS i query-strengen.
        Da skal man ikke sende Authorization: Bearer — Azure svarer da typisk
        HTTP 403 «Server failed to authenticate the request».
        """
        host = (urlparse(url).hostname or "").lower()
        if ".blob.core.windows.net" in host:
            return False
        if ".dfs.core.windows.net" in host:
            return False
        if host.endswith(".blob.storage.azure.net"):
            return False
        return True

    _DV_LOOKUP_BATCH = 2000
    _DV_OR_CHUNK = 300
    _DV_CACHE_MAX_ENTRIES = 50_000

    @classmethod
    def _bulk_fetch_device_vulnerabilities(cls, dvs, keys):
        """
        Last inn eksisterende AzureDeviceVulnerability-rader for oppgitte nøkler.
        Bruker OR-spørringer i mindre biter (CPU/DB) i stedet for å holde hele
        tabellen i RAM.
        """
        if not keys:
            return
        seen = [k for k in dict.fromkeys(keys) if k not in dvs]
        if not seen:
            return
        for i in range(0, len(seen), cls._DV_OR_CHUNK):
            chunk = seen[i : i + cls._DV_OR_CHUNK]
            q = reduce(or_, (Q(device_id=d, cve_id=c) for d, c in chunk))
            qs = AzureDeviceVulnerability.objects.filter(q).only(
                "id",
                "device_id",
                "cve_id",
                "last_seen",
                "severity",
                "status",
            )
            dvs.merge_fetch_results(qs)

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            choices=["defender", "local"],
            default="defender",
            help="defender: API + lagre alle filer lokalt før import. local: kun filer under import/defender.",
        )
        parser.add_argument(
            "--ignore-schedule",
            action="store_true",
        )

    def _say(self, message):
        """Skriv til stdout og tøm buffer med én gang (viktig når stdout ikke er TTY)."""
        self.stdout.write(message)
        self.stdout.flush()

    def _print_run_options(self, script_navn, start_ts, options):
        """Skriv CLI-valg til stdout ved hver kjøring (også ved tidlig avbrudd/feil)."""
        self._say(f"[{start_ts}] Starter {script_navn}")
        self._say("Kjøreparametere:")
        self._say(
            f"  --source={options['source']!r}   "
            f"(defender=hent fra API, local=les fra import/defender på disk; default: defender)"
        )
        self._say(
            f"  --ignore-schedule={options['ignore_schedule']!r}   "
            f"(True=kjør uansett ukedag; False=Defender-kilde følger søndagsregel)"
        )
        if "verbosity" in options:
            self._say(f"  verbosity={options['verbosity']!r}")

    def handle(self, **options):
        SCRIPT_NAVN = os.path.basename(__file__)
        start_ts = timezone.now()
        start_time = time.time()

        self._print_run_options(SCRIPT_NAVN, start_ts, options)

        SOURCE = options["source"]
        IGNORE_SCHEDULE = options["ignore_schedule"]

        INTEGRASJON_KODEORD = "azure_vulnerabilities"
        LOG_EVENT_TYPE = "Azure defender vulnerabilities"

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

        self._say("Integrasjonskonfigurasjon oppdatert. Fortsetter…")

        try:
            if SOURCE == "defender" and not IGNORE_SCHEDULE and start_ts.weekday() != 6:
                msg = "Skippet: Defender-kjøring kun tillatt søndag"
                self._say(msg)
                ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=msg)
                # This is not an error; the job is intentionally only scheduled weekly.
                # Keep health green so admin status doesn't flap on skipped days.
                int_config.helsestatus = "Vellykket"
                int_config.sist_status = msg
                int_config.runtime = 0
                int_config.elementer = 0
                int_config.save()
                return

            file_paths = []

            if SOURCE == "defender":
                self._say("Defender API: henter applikasjonstoken…")
                credential = ClientSecretCredential(
                    tenant_id=os.environ["AZURE_TENANT_ID"],
                    client_id=os.environ["AZURE_ENTERPRISEAPP_CLIENT"],
                    client_secret=os.environ["AZURE_ENTERPRISEAPP_SECRET"],
                )

                token = credential.get_token(self._DEFENDER_TOKEN_SCOPE).token

                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }

                self._say(
                    "Defender API: kaller SoftwareVulnerabilitiesExport "
                    "(første svar kan ta tid)…"
                )
                start = requests.get(
                    "https://api.security.microsoft.com/api/machines/SoftwareVulnerabilitiesExport",
                    headers=headers,
                    params={"sasValidHours": 6},
                    timeout=60,
                )
                self._say(f"Defender API: første svar HTTP {start.status_code}.")

                if start.status_code == 202:
                    poll_url = start.headers.get("Location")
                    if not poll_url:
                        raise RuntimeError("HTTP 202 men mangler Location-header for polling")
                    if poll_url.startswith("/"):
                        poll_url = urljoin(start.url, poll_url)
                    self._say(
                        "Eksport er satt i kø (202). Poller hvert 5. sekund, inntil 60 forsøk (~5 min)…"
                    )
                    for attempt in range(60):
                        self._say(f"  Poller eksport, forsøk {attempt + 1}/60 …")
                        time.sleep(5)
                        if self._defender_url_needs_bearer_only(poll_url):
                            token = credential.get_token(
                                self._DEFENDER_TOKEN_SCOPE
                            ).token
                            poll_headers = {
                                "Authorization": f"Bearer {token}",
                                "Accept": "application/json",
                            }
                        else:
                            poll_headers = None
                        poll = requests.get(
                            poll_url, headers=poll_headers, timeout=60
                        )
                        if poll.status_code == 200:
                            export_urls = self._export_urls_from_api_payload(poll.json())
                            self._say(f"  Eksport klar (HTTP 200) etter {attempt + 1} forsøk.")
                            break
                        if poll.status_code in (401, 403):
                            if self._defender_url_needs_bearer_only(poll_url):
                                hint = (
                                    "Sjekk app-tilgang (Vulnerability.Read.All), utløpt token eller rate limits."
                                )
                            else:
                                hint = (
                                    "Blob-URL med SAS: sjekk utløpt signatur (se), nettverk eller IP-restriksjoner."
                                )
                            raise RuntimeError(
                                "Defender-eksport: HTTP "
                                f"{poll.status_code} under polling. Vert: "
                                f"{(urlparse(poll_url).hostname or '?')!r}. {hint} "
                                f"Svar (utdrag): {poll.text[:800]!r}"
                            )
                    else:
                        raise TimeoutError("Tidsavbrudd ved Defender-eksport")
                elif start.status_code == 200:
                    export_urls = self._export_urls_from_api_payload(start.json())
                    self._say("Eksport klar umiddelbart (HTTP 200).")
                else:
                    raise RuntimeError(start.text)

                local_dir = self._defender_import_dir()
                os.makedirs(local_dir, exist_ok=True)
                self._clear_previous_snapshot_exports(local_dir)

                if not export_urls:
                    raise RuntimeError(
                        "Defender-eksport ga ingen fil-URL-er (exportFiles/value er tom). "
                        "Ingenting å laste ned."
                    )

                self._say(
                    f"Fase 1 — nedlasting: {len(export_urls)} fil(er) til {local_dir} "
                    "(ingen database-cache i RAM ennå)…"
                )
                for idx, url in enumerate(export_urls, start=1):
                    self._say(f"  Nedlasting {idx}/{len(export_urls)} …")
                    resp = requests.get(url, stream=True, timeout=300)
                    try:
                        resp.raise_for_status()
                    except requests.HTTPError as exc:
                        host = (urlparse(url).hostname or "") if url else ""
                        raise RuntimeError(
                            f"Nedlasting feilet for fil {idx}/{len(export_urls)} (HTTP {resp.status_code}). "
                            f"Vert: {host!r}. "
                            "Eksport-URL-er er tidsbegrensede SAS fra Microsoft; ved mange filer eller "
                            "lang total nedlasting kan de utløpe — kjør kommandoen på nytt (sasValidHours=6 "
                            "er satt for å forlenge vinduet). "
                            f"Detalj: {exc}"
                        ) from exc
                    save_name = f"vulnerabilities_{idx:03d}.json.gz"
                    save_path = os.path.join(local_dir, save_name)
                    with open(save_path, "wb") as out:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                out.write(chunk)
                    file_paths.append(save_path)
                    self._say(f"  Lagret: {save_path}")

                if not file_paths:
                    raise RuntimeError(
                        "Defender-eksport inneholdt ingen nedlastbare fil-URL-er "
                        "(sjekk exportFiles/value i API-svaret)."
                    )

            else:
                local_dir = self._defender_import_dir()
                self._say(
                    f"Lokal kilde (--source local): leser katalog {local_dir} "
                    "(ingen API-kall til Microsoft)…"
                )

                if not os.path.isdir(local_dir):
                    raise RuntimeError(f"Local import directory mangler: {local_dir}")

                for name in sorted(os.listdir(local_dir)):
                    lower = name.lower()
                    if lower.endswith(".json.gz") or lower.endswith(".gz"):
                        file_paths.append(os.path.join(local_dir, name))
                    elif name.endswith(".json"):
                        file_paths.append(os.path.join(local_dir, name))

            self._say(
                "Fase 2 — database: henter AzureDevice og CVE. "
                "AzureDeviceVulnerability hentes i batch under import (mer CPU/DB, mindre RAM)."
            )
            devices = {d.device_id: d for d in AzureDevice.objects.all()}
            cves = {c.cve_id: c for c in CVE.objects.defer("description")}
            dv_pin_keys = set()
            dvs = _BoundedLRUDeviceVulnCache(self._DV_CACHE_MAX_ENTRIES, dv_pin_keys)
            self._say(
                f"DB-grunnlag: {len(devices)} enheter, {len(cves)} CVE; "
                f"koblinger i LRU-cache (maks {self._DV_CACHE_MAX_ENTRIES} oppslag i RAM, "
                f"batch-henting ca {self._DV_LOOKUP_BATCH} nøkler)."
            )

            devices_to_create = []
            cves_to_create = []
            dvs_to_create = []
            dvs_to_update = []

            processed = 0
            dv_pending = set()

            self._say(f"Fase 3 — import: {len(file_paths)} fil(er) fra disk…")

            for idx, item in enumerate(file_paths, start=1):
                self._say(
                    f"Prosesserer fil {idx}/{len(file_paths)} — {os.path.basename(item)}"
                )

                use_graph_json = item.lower().endswith(".gz")
                if use_graph_json:
                    self._say(
                        "  Leser gzip (JSONL) — ved OOM («Killed») trengs ofte mer RAM "
                        "eller færre rader i DB-cache."
                    )
                    record_iter = (
                        json.loads(line.decode("utf-8"))
                        for line in gzip.open(item, "rb")
                    )
                else:
                    with open(item, "r", encoding="utf-8") as fh:
                        payload = json.load(fh)
                    record_iter = payload.get("value", [])

                self._say(f"  Prosesserer innhold …")
                lines_seen = 0
                for r in record_iter:
                    lines_seen += 1
                    if lines_seen % 100_000 == 0:
                        self._say(
                            f"  … {lines_seen} JSON-linjer lest i fil {idx}, "
                            f"{processed} poster behandlet så langt i kjøringen "
                            f"(dv-cache {len(dvs)}/{self._DV_CACHE_MAX_ENTRIES}) …"
                        )
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
                    if key not in dvs:
                        dv_pending.add(key)
                    if len(dv_pending) >= self._DV_LOOKUP_BATCH:
                        self._bulk_fetch_device_vulnerabilities(dvs, list(dv_pending))
                        dv_pending.clear()
                    if key not in dvs:
                        self._bulk_fetch_device_vulnerabilities(
                            dvs, list(dv_pending | {key})
                        )
                        dv_pending.clear()
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
                        dv_pin_keys.add(key)
                        dvs[key] = new_dv   # ✅ CRITICAL FIX
                    else:
                        dv.last_seen = last_seen
                        dv.severity = severity
                        dv.status = "active"
                        dvs_to_update.append(dv)

                    processed += 1

                    if (
                        len(dvs_to_create) >= 5000
                        or len(dvs_to_update) >= 5000
                    ):
                        self.flush(
                            devices_to_create,
                            cves_to_create,
                            dvs_to_create,
                            dvs_to_update,
                            dv_pin_keys,
                        )

                if dv_pending:
                    self._bulk_fetch_device_vulnerabilities(dvs, list(dv_pending))
                    dv_pending.clear()

                self._say(
                    f"  Ferdig med fil {idx}/{len(file_paths)}: {lines_seen} linjer, "
                    f"{processed} poster totalt i kjøringen til nå."
                )
                gc.collect()

            if dv_pending:
                self._bulk_fetch_device_vulnerabilities(dvs, list(dv_pending))
                dv_pending.clear()

            self.flush(
                devices_to_create,
                cves_to_create,
                dvs_to_create,
                dvs_to_update,
                dv_pin_keys,
            )

            resolved = AzureDeviceVulnerability.objects.filter(
                status="active",
                last_seen__lt=(start_ts - timedelta(days=2)),
            ).update(status="resolved")

            runtime = int(time.time() - start_time)

            msg = (
                f"source={SOURCE}, ignore_schedule={IGNORE_SCHEDULE}, "
                f"files={len(file_paths)}, processed={processed}, "
                f"resolved={resolved}, runtime={runtime}s"
            )

            ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=msg)

            int_config.helsestatus = "Vellykket"
            int_config.sist_status = msg
            int_config.runtime = runtime
            int_config.elementer = processed
            int_config.dato_sist_oppdatert = start_ts
            int_config.save()

            self._say(msg)

        except Exception as e:
            msg = f"{SCRIPT_NAVN} feilet: {e}"
            ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=msg)
            int_config.helsestatus = "Feil"
            int_config.sist_status = msg
            int_config.save()
            push_pushover(msg)
            self._say(msg)
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

    def flush(self, devices, cves, create, update, dv_pin_keys=None):
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
                to_create = list(create)
                AzureDeviceVulnerability.objects.bulk_create(
                    to_create, batch_size=2000
                )
                if dv_pin_keys is not None:
                    for obj in to_create:
                        dv_pin_keys.discard((obj.device_id, obj.cve_id))
                create.clear()

            if update:
                AzureDeviceVulnerability.objects.bulk_update(
                    update,
                    fields=["last_seen", "severity", "status"],
                    batch_size=2000,
                )
                update.clear()