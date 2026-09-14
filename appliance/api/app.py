"""FastAPI application and product surface.

Two complementary experiences over one backend:

  ARCHITECTURE   what the product IS   - breadth, modularity, connectivity
  INTELLIGENCE   what the product DOES - the engineering answer, simply

Every route delegates to ApplianceService. No route implements orchestration, so
the interfaces cannot drift into behaving differently.

Server-rendered HTML with HTMX: no SPA build chain, no npm in the
container, and assets served locally so the appliance renders with no internet.
"""
from __future__ import annotations

import os
import re
import uuid

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import presentation
from .. import surface as surface_model
from ..architecture import DATA_FLOW
from ..core.errors import ApplianceError
from ..service import REVIEW_CONTROL_LABEL, ApplianceService

HERE = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
# Jinja2's template cache key is unhashable under this Python/Jinja2
# combination. Caching buys nothing here and disabling it avoids the
# incompatibility entirely.
templates.env.cache = None

app = FastAPI(title="Engineering Knowledge Intelligence", version="0.1.0",
              description="Evidence-grounded change impact & verification assistant. "
                          "Public demonstrator: synthetic data, session-scoped and "
                          "unauthenticated review.")
# Assets are served locally, never from a CDN: the appliance must render with
# no internet access, which is both an air-gap requirement and the difference
# between a demonstration that works in a meeting room and one that does not.
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
service = ApplianceService()

FLOW = [{"stage": s, "note": n} for s, n in DATA_FLOW]

SESSION_COOKIE = "eia_session"
_SESSION_ID = re.compile(r"[0-9a-f]{32}")


@app.middleware("http")
async def client_session(request: Request, call_next):
    """Give every browser its own analysis session.

    One process and one loaded dataset, but per-client analysis state: two
    people opening the demonstration must not overwrite each other, and one
    pressing Reset must not clear the other's analysis. The cookie is an opaque
    random id and carries no engineering data, so nothing crosses between
    sessions but the identifier itself.
    """
    incoming = request.cookies.get(SESSION_COOKIE)
    session_id = (incoming if incoming and _SESSION_ID.fullmatch(incoming)
                  else uuid.uuid4().hex)
    request.scope["appliance_session"] = session_id
    response = await call_next(request)
    if session_id != incoming:
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True,
                            samesite="lax", path="/", max_age=86400)
    return response


def bind(request: Request) -> None:
    """Bind this request to its client's session before state is touched."""
    service.use(request.scope.get("appliance_session"))


def _ctx(**kwargs) -> dict:
    """Shared template context. Starlette injects `request` itself."""
    return {"health": service.health(), "review_control": REVIEW_CONTROL_LABEL, **kwargs}


def _analysis_ctx() -> dict:
    """Everything the analysis partial renders, for the bound session."""
    outputs = service.full_output_catalogue()
    e = service.executive()
    if e.get("answerable") and e["domain"].get("presentation") == "knowledge":
        outputs = [o for o in outputs if o.get("domain_relevant", True)]
    result = service.session.result or {}
    return _ctx(nav="intelligence", e=e, detail=service.engineering_detail(),
                outputs=outputs, summary=service.output_summary(),
                pipeline=presentation.derivation_pipeline(result, service.session.reviews)
                if result else [],
                reviews=service.reviews())


# ==========================================================================
# DOMAIN SURFACES
#
# A domain pack may ship its own product surface (templates/<surface>/). The
# surface a page uses is chosen per client from the session: the domain the
# client selected, or the domain of the scenario it analysed. Partials that
# render an analysis (explain, review, outputs) always follow the analysis's
# own domain. The engine underneath is the same for every surface.
# ==========================================================================
def _page_surface() -> str | None:
    return service.surface.surface


def _result_surface() -> str | None:
    return service.profile.surface


def _surface_ctx(nav: str, **kwargs) -> dict:
    profile = service.surface
    content = profile.surface_content
    base = dict(nav=nav, p=profile, S=content, labels=profile.labels,
                view=surface_model.analysis_view(service, profile),
                reviews=service.reviews(), review_label=SURFACE_REVIEW_LABEL,
                hero=service.scenario(content.get("hero_scenario", "")),
                scenarios=service.scenarios(profile.domain))
    base.update(kwargs)
    return _ctx(**base)


def _surface_page(request: Request, page: str, nav: str, **kwargs):
    return templates.TemplateResponse(
        request, f"{_page_surface()}/{page}", _surface_ctx(nav, **kwargs))


def _targets(raw: str) -> set[str]:
    return {t for t in (raw or "").split(",") if t}


SURFACE_REVIEW_LABEL = "Session scoped · unauthenticated · demonstrator only"


def _by_category(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["category"], []).append(row)
    return grouped


# ==========================================================================
# INTELLIGENCE - what the product does
# ==========================================================================
@app.get("/", response_class=HTMLResponse)
def intelligence(request: Request):
    bind(request)
    if _page_surface():
        profile = service.surface
        records = service.domain_records(profile)
        result = service.session.result if service.session.has_analysis else None
        return _surface_page(
            request, "overview.html", "overview",
            sources=surface_model.knowledge_sources(service, profile, records),
            domains=surface_model.domain_coverage(profile, records, result),
            record_count=len(records))
    return templates.TemplateResponse(request, "intelligence.html", _ctx(
        nav="intelligence", scenarios=service.scenarios(service.surface.domain), flow=FLOW))


@app.get("/domain/{domain}")
def choose_domain(request: Request, domain: str):
    """Switch this client's product surface (and clear any other domain's analysis)."""
    bind(request)
    try:
        service.use_surface(domain)
    except ApplianceError as exc:
        return JSONResponse(exc.as_dict(), status_code=404)
    return RedirectResponse("/", status_code=303)


@app.post("/analyse", response_class=HTMLResponse)
def analyse(request: Request, scenario_id: str = Form(...)):
    bind(request)
    try:
        service.analyse_scenario(scenario_id)
    except ApplianceError as exc:
        return templates.TemplateResponse(request, "partials/error.html",
                                          _ctx(error=exc.as_dict()), status_code=400)
    if _result_surface():
        return templates.TemplateResponse(
            request, f"{_result_surface()}/partials/narrative.html",
            _surface_ctx("analyse"))
    return templates.TemplateResponse(request, "partials/analysis.html", _analysis_ctx())


@app.post("/run/{scenario_id}")
def run_scenario(request: Request, scenario_id: str, next: str = Form("/")):
    """Analyse a scenario, then continue to a page (no-JavaScript entry point)."""
    bind(request)
    try:
        service.analyse_scenario(scenario_id)
    except ApplianceError as exc:
        return JSONResponse(exc.as_dict(), status_code=400)
    target = next if next.startswith("/") and not next.startswith("//") else "/"
    return RedirectResponse(target, status_code=303)


@app.get("/explain/{finding_id}", response_class=HTMLResponse)
def explain(request: Request, finding_id: str):
    bind(request)
    try:
        payload = service.explain(finding_id)
    except ApplianceError as exc:
        return templates.TemplateResponse(request, "partials/error.html",
                                          _ctx(error=exc.as_dict()), status_code=400)
    if _result_surface():
        return templates.TemplateResponse(
            request, f"{_result_surface()}/partials/explain.html",
            _surface_ctx("", e=payload))
    return templates.TemplateResponse(request, "partials/explain.html", _ctx(e=payload))


@app.post("/review/{finding_id}", response_class=HTMLResponse)
def review(request: Request, finding_id: str, decision: str = Form(""),
           reviewer: str = Form(""), note: str = Form(""), targets: str = Form("")):
    """Record a reviewer decision on ONE finding (demonstrator control:
    session scoped, unauthenticated). Returns the refreshed review control and,
    out of band, only the page regions the calling page actually has."""
    bind(request)
    error = None
    shown_output = service.session.last_output if service.session.outputs else None
    try:
        service.review(finding_id, decision, reviewer, note)
    except ApplianceError as exc:
        error = exc.as_dict()
    try:
        payload = service.explain(finding_id)
    except ApplianceError as exc:
        return templates.TemplateResponse(request, "partials/error.html",
                                          _ctx(error=exc.as_dict()), status_code=400)
    present = _targets(targets)
    refreshed = None
    if not error and shown_output and "output" in present:
        # The output on screen was generated before this decision: regenerate it
        # so the reviewer sees the decision applied immediately.
        refreshed = service.generate(shown_output)
    context = dict(e=payload, error=error, targets=present, refreshed=refreshed,
                   draft={"reviewer": reviewer, "note": note if error else ""},
                   reviews=service.reviews(), oob=True,
                   pipeline=presentation.derivation_pipeline(service.session.result,
                                                             service.session.reviews))
    if _result_surface():
        return templates.TemplateResponse(
            request, f"{_result_surface()}/partials/review.html",
            _surface_ctx("", **context), status_code=400 if error else 200)
    return templates.TemplateResponse(request, "partials/review.html", _ctx(**context),
                                      status_code=400 if error else 200)


@app.post("/output/{workflow_id}", response_class=HTMLResponse)
def output(request: Request, workflow_id: str):
    bind(request)
    try:
        generated = service.generate(workflow_id)
    except ApplianceError as exc:
        return templates.TemplateResponse(request, "partials/error.html",
                                          _ctx(error=exc.as_dict()), status_code=400)
    if _result_surface():
        return templates.TemplateResponse(
            request, f"{_result_surface()}/partials/output.html",
            _surface_ctx("", o=generated))
    return templates.TemplateResponse(request, "partials/output.html", _ctx(o=generated))


@app.post("/reset", response_class=HTMLResponse)
def reset(request: Request):
    bind(request)
    service.reset()
    if _page_surface():
        return templates.TemplateResponse(
            request, f"{_page_surface()}/partials/idle.html", _surface_ctx("analyse"))
    return templates.TemplateResponse(request, "partials/idle.html",
                                      _ctx(nav="intelligence", flow=FLOW))


# ==========================================================================
# DOMAIN SURFACE PAGES (a domain without its own surface returns to "/")
# ==========================================================================
def _surface_only(request: Request, page: str, nav: str, **kwargs):
    bind(request)
    if not _page_surface():
        return RedirectResponse("/", status_code=303)
    return _surface_page(request, page, nav, **kwargs)


@app.get("/analyse-change", response_class=HTMLResponse)
def analyse_change(request: Request):
    return _surface_only(request, "analyse.html", "analyse")


@app.get("/requirements", response_class=HTMLResponse)
def requirements_page(request: Request):
    return _surface_only(request, "requirements.html", "requirements")


@app.get("/reasoning", response_class=HTMLResponse)
def reasoning_page(request: Request):
    return _surface_only(request, "reasoning.html", "reasoning")


@app.get("/review", response_class=HTMLResponse)
def review_page(request: Request):
    return _surface_only(request, "review.html", "review")


@app.get("/verification-plan", response_class=HTMLResponse)
def verification_plan_page(request: Request, output: str = "verification-evidence-plan"):
    bind(request)
    if not _page_surface():
        return RedirectResponse("/", status_code=303)
    profile = service.surface
    generated, error = None, None
    if surface_model.analysis_view(service, profile):
        if output not in profile.workflow_aliases:
            output = "verification-evidence-plan"
        try:
            generated = service.generate(output)
        except ApplianceError as exc:
            error = exc.as_dict()
    return _surface_page(request, "plan.html", "plan", o=generated, error=error,
                         selected=output)


# ==========================================================================
# ARCHITECTURE - what the product is
# ==========================================================================
@app.get("/architecture", response_class=HTMLResponse)
def architecture(request: Request):
    bind(request)
    if _page_surface():
        profile = service.surface
        records = service.domain_records(profile)
        result = service.session.result if service.session.has_analysis else None
        return _surface_page(
            request, "architecture.html", "architecture",
            facts=surface_model.architecture_facts(service, profile, records),
            sources=surface_model.knowledge_sources(service, profile, records),
            domains=surface_model.domain_coverage(profile, records, result))
    catalogue = service.connector_catalogue()
    return templates.TemplateResponse(request, "architecture.html", _ctx(
        nav="architecture",
        arch=service.architecture(),
        connectors_by_category=_by_category(catalogue),
        connector_summary=service.registry.summary(),
        outputs=service.full_output_catalogue()))


@app.get("/sources", response_class=HTMLResponse)
def sources(request: Request):
    bind(request)
    if _page_surface():
        return RedirectResponse("/architecture#knowledge-sources", status_code=303)
    catalogue = service.connector_catalogue()
    return templates.TemplateResponse(request, "sources.html", _ctx(
        nav="sources", catalogue=catalogue, by_category=_by_category(catalogue),
        summary=service.registry.summary()))


@app.get("/outputs", response_class=HTMLResponse)
def outputs(request: Request):
    bind(request)
    if _page_surface():
        return RedirectResponse("/verification-plan", status_code=303)
    return templates.TemplateResponse(request, "outputs.html", _ctx(
        nav="outputs", outputs=service.full_output_catalogue(),
        summary=service.output_summary(),
        has_analysis=service.session.has_analysis))


@app.get("/evidence", response_class=HTMLResponse)
def evidence(request: Request):
    bind(request)
    if _page_surface():
        profile = service.surface
        view = surface_model.analysis_view(service, profile)
        in_scope = None
        if view:
            in_scope = surface_model.knowledge_sources(
                service, profile, service.domain_records(profile),
                scope=set(view["result"]["closure"]))
        return _surface_page(request, "evidence.html", "evidence", in_scope=in_scope)
    detail = service.engineering_detail()
    connectors = []
    if service.session.has_analysis:
        connectors = list(detail.get("ledger", {}).get("participation", {}).keys())
    return templates.TemplateResponse(request, "evidence.html", _ctx(
        nav="evidence", e=service.executive(), detail=detail, connectors=connectors))


# ==========================================================================
# API
# ==========================================================================
@app.get("/health")
def health():
    return JSONResponse(service.health())


@app.get("/api/architecture")
def api_architecture(request: Request):
    bind(request)
    return JSONResponse(service.architecture())


@app.get("/api/connectors")
def api_connectors():
    return JSONResponse(service.connector_catalogue())


@app.get("/api/outputs")
def api_outputs(request: Request):
    bind(request)
    return JSONResponse({"summary": service.output_summary(),
                         "outputs": service.full_output_catalogue()})


@app.get("/api/executive")
def api_executive(request: Request):
    bind(request)
    return JSONResponse(service.executive())


@app.post("/api/analyse/{scenario_id}")
def api_analyse(request: Request, scenario_id: str):
    bind(request)
    try:
        service.analyse_scenario(scenario_id)
    except ApplianceError as exc:
        return JSONResponse(exc.as_dict(), status_code=400)
    result = service.session.result
    return JSONResponse({
        "scenario_id": scenario_id, "status": result["status"],
        "domain": result["domain"]["domain"], "subject_id": result["subject_id"],
        "executive": {k: v for k, v in service.executive().items() if k != "domain"},
        "findings": [f.model_dump(mode="json") for f in result["findings"]],
        "unknowns": result["unknowns"], "gate": result["gate_report"],
        "activity": result["activity"], "stages": result["stages"],
        "pipeline": presentation.derivation_pipeline(result, service.session.reviews),
        "context_snapshot_id": result["context_snapshot_id"],
        "execution_mode": result["execution_mode"]})


@app.get("/api/explain/{finding_id}")
def api_explain(request: Request, finding_id: str):
    bind(request)
    try:
        payload = service.explain(finding_id)
    except ApplianceError as exc:
        return JSONResponse(exc.as_dict(), status_code=400)
    payload.pop("domain", None)
    return JSONResponse(payload)


@app.post("/api/review/{finding_id}")
async def api_review(request: Request, finding_id: str):
    """JSON body or form: {decision: accept|reject, reviewer, note}."""
    bind(request)
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
    else:
        body = dict(await request.form())
    try:
        record = service.review(finding_id, str(body.get("decision", "")),
                                str(body.get("reviewer", "")), str(body.get("note", "")))
    except ApplianceError as exc:
        return JSONResponse(exc.as_dict(), status_code=400)
    return JSONResponse(record)


@app.get("/api/reviews")
def api_reviews(request: Request):
    bind(request)
    return JSONResponse(service.reviews())


@app.get("/api/output/{workflow_id}")
def api_output(request: Request, workflow_id: str):
    bind(request)
    try:
        generated = service.generate(workflow_id)
    except ApplianceError as exc:
        return JSONResponse(exc.as_dict(), status_code=400)
    return JSONResponse(generated.model_dump(mode="json"))
