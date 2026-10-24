import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import Field, BaseModel, ConfigDict, StrictInt, field_validator, model_validator

from .errors import ServiceError
from .models import DataMode, Mandate, SignalInput
from .settings import APP_ROOT, Settings


@dataclass(frozen=True)
class Candidate:
    key: str
    company_name: str
    canonical_domain: str | None
    evidence: list[dict]
    provider: str = "fixture"
    data_mode: DataMode = DataMode.synthetic
    discovery_refs: dict | None = None
    description: str | None = None
    provider_company_id: str | None = None


class DiscoveryProvider(Protocol):
    def ensure_available(self, mandate: Mandate | None = None) -> None: ...
    def discover(self, mandate: Mandate, limit: int, *, task_id=None) -> list[Candidate]: ...


class FixtureCatalog:
    def __init__(self, path: Path):
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.companies = {item["key"]: item for item in self.data["companies"]}

    def replay(self, key: str, signal: SignalInput) -> dict | None:
        for replay in self.companies.get(key, {}).get("signals", []):
            if signal.model_dump(mode="json") == replay["input"]:
                return replay
        return None


class FixtureProvider:
    def __init__(self, catalog: FixtureCatalog):
        self.catalog = catalog

    def ensure_available(self, mandate=None) -> None:
        pass

    def discover(self, mandate: Mandate, limit: int, *, task_id=None) -> list[Candidate]:
        # Catalog is an explicit development scenario, independent of thesis meaning.
        return [Candidate(key=x["key"], company_name=x["company_name"], canonical_domain=x["canonical_domain"], evidence=x["evidence"]) for x in list(self.catalog.companies.values())[:limit]]


class RankedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal["hybrid", "lexical", "semantic"]

    @field_validator("query")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Ranked search query cannot be blank")
        return value


class SearchRequest(BaseModel):
    """Explicit server-side query; no thesis-to-filter inference."""
    model_config = ConfigDict(extra="forbid")
    filters: dict | None = None
    search: RankedRequest | None = None
    fields: list[str]
    limit: StrictInt = Field(ge=1, le=100)

    @model_validator(mode="after")
    def bounded_criteria(self):
        if not self.filters and self.search is None:
            raise ValueError("Supply an explicit search or nonempty filters")
        return self


class SearchConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=300)
    reference_status: str = "example_not_thesis_derived"
    request: SearchRequest


class CrustdataSearchProvider:
    """One bounded documented search request; no pagination, retries or enrichment.

    Mapping: https://crustdata.com/company-data-api, checked 2026-10-24.
    Account access separately proven by control's handoffs/crustdata-smoke.json.
    The in-app adapter is tested with HTTPX mock transport without spending credits.
    """
    endpoint = "https://api.crustdata.com/company/search"
    api_version = "2025-11-01"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None, response_sink=None):
        self.settings, self.transport, self.response_sink = settings, transport, response_sink
        self.last_diagnostic = None

    def configuration(self) -> SearchConfiguration:
        path = self.settings.crustdata_search_config
        if path is None:
            raise ServiceError("provider_not_configured", "Set CRUSTDATA_SEARCH_CONFIG to an explicit server-side search JSON file before running live discovery. No paid request was made.", 503)
        path = path if path.is_absolute() else APP_ROOT / path
        try:
            config = SearchConfiguration.model_validate_json(path.read_text(encoding="utf-8-sig"))
            required = {"basic_info.name", "basic_info.primary_domain"}
            if not required.issubset(config.request.fields):
                raise ValueError("Missing required projection fields")
            return config
        except (OSError, ValueError):
            raise ServiceError("provider_not_configured", "Crustdata transport configuration is unreadable or invalid. Required identity fields: basic_info.name, basic_info.primary_domain. No paid request was made.", 503) from None

    def ensure_available(self, mandate=None) -> None:
        if not self.settings.crustdata_api_key.strip():
            raise ServiceError("provider_not_configured", "Live discovery requires server-side CRUSTDATA_API_KEY. No fixture fallback was used.", 503)
        self.configuration()

    def discover(self, mandate: Mandate, limit: int, *, task_id=None) -> list[Candidate]:
        self.ensure_available()
        config = self.configuration()
        body = config.request.model_dump(exclude_none=True)
        body["limit"] = min(body["limit"], limit)
        return self.execute_request(body)

    def execute_request(self, body: dict) -> list[Candidate]:
        """Low-level transport, called by approved execution or explicit mock tests."""
        body = SearchRequest.model_validate(body).model_dump(exclude_none=True)
        headers = {"Authorization": f"Bearer {self.settings.crustdata_api_key.strip()}", "x-api-version": self.api_version}
        try:
            with httpx.Client(transport=self.transport, timeout=httpx.Timeout(20, connect=5), follow_redirects=False, trust_env=False) as client:
                response = client.post(self.endpoint, headers=headers, json=body)
        except httpx.HTTPError:
            raise ServiceError("provider_unavailable", "Crustdata search could not be completed. No automatic retry or fixture fallback was made.", 502, True) from None
        self.last_diagnostic = {'http_status': response.status_code, 'request_id': response.headers.get('x-request-id'), 'credits_used': response.headers.get('x-credits-used')}
        if self.response_sink is not None:
            self.response_sink({'request': body, 'diagnostic': self.last_diagnostic, 'response_text': response.text})
        if response.status_code != 200:
            if response.status_code in {401, 403}:
                raise ServiceError("provider_not_configured", "Crustdata rejected authentication or endpoint access. Check server credentials and permissions.", 503)
            raise ServiceError("provider_unavailable", f"Crustdata search returned HTTP {response.status_code}. Provider body omitted; no retry or fixture fallback was made.", 502, response.status_code == 429 or response.status_code >= 500)
        try:
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("companies"), list):
                raise ValueError("Invalid response envelope")
            if len(payload["companies"]) > body["limit"]:
                raise ValueError("Response exceeds bounded result limit")
            stamp = getattr(self, 'retrieval_timestamp_override', None) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            candidates = []
            for record in payload["companies"]:
                basic = record["basic_info"]
                name = basic["name"]
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Invalid company name")
                # Provider uses an empty string for an unknown optional domain.
                domain = basic.get("primary_domain")
                if domain == "":
                    domain = None
                if domain is not None:
                    if not isinstance(domain, str) or not domain or any(c.isspace() for c in domain) or "/" in domain or ":" in domain:
                        raise ValueError("Invalid primary domain")
                    domain = domain.lower().rstrip(".")
                    parsed_domain = urlsplit("https://" + domain)
                    if parsed_domain.hostname != domain or parsed_domain.username or parsed_domain.password or parsed_domain.query or parsed_domain.fragment:
                        raise ValueError("Primary domain must be a hostname, not a URL or credentials")
                identity = record.get("crustdata_company_id") or domain
                if not identity or isinstance(identity, (dict, list, bool)):
                    raise ValueError("Missing stable company identity")
                headcount = (record.get("headcount") or {}).get("total")
                description = basic.get("description")
                if description is not None and not isinstance(description, str):
                    raise ValueError("Invalid optional description")
                if headcount is not None and (type(headcount) is not int or headcount < 0):
                    raise ValueError("Invalid headcount")
                # Evidence claims only what returned fields establish. Endpoint is
                # provenance, not an invented public company/source URL.
                facts = [("company_profile", f"Crustdata search returned company name {name!r}" + (f" with primary domain {domain}." if domain else "."))]
                if "headcount.total" in body.get("fields", []):
                    facts.append(("headcount_total", f"Crustdata reported headcount.total={headcount}. Observation date and thesis relevance are unknown." if headcount is not None else "Crustdata did not return headcount.total; value remains unknown."))
                if description is not None:
                    facts.append(("provider_company_description", "Crustdata indexed description (provider claim, not inspected proof): " + description))
                observation = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:16]
                evidence = [{"claim_type": claim, "summary": summary, "source_url": self.endpoint, "source_key": f"crustdata:{identity}:search:{stamp}:{observation}:{claim}", "retrieved_at": stamp, "data_mode": "live"} for claim, summary in facts]
                candidates.append(Candidate(key=str(identity), company_name=name, canonical_domain=domain, evidence=evidence, provider="crustdata", data_mode=DataMode.live, description=description, provider_company_id=str(record["crustdata_company_id"]) if record.get("crustdata_company_id") is not None else None))
            return candidates
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            reason = str(exc)[:160]
            self.last_diagnostic['normalization_error'] = reason
            raise ServiceError("provider_unavailable", "Crustdata HTTP 200 normalization failed: " + reason + ". Saved response can be replayed locally without another paid call.", 502) from None


def build_provider(settings: Settings, catalog: FixtureCatalog, state=None) -> DiscoveryProvider:
    if settings.provider_mode == "fixture":
        return FixtureProvider(catalog)
    from .discovery import ApprovedCompanySearchProvider
    if state is None:
        raise ValueError("Live sourcing requires backend discovery approval/reservation state")
    return ApprovedCompanySearchProvider(settings, state)
