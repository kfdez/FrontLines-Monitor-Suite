"""FastAPI web admin app for VPS deployments."""
import json
import os
import secrets
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from core.logger import setup_logging
from server.auth import authenticate
from server.service_manager import ServiceManager


setup_logging()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
manager = ServiceManager()
HV_SEARCH_CACHE = OrderedDict()
HV_SEARCH_CACHE_TTL = 1800
HV_SEARCH_CACHE_MAX = 50
ROOT_PATH = os.environ.get("FRONTLINES_ROOT_PATH", "").rstrip("/")
SESSION_COOKIE_PATH = ROOT_PATH or "/"

app = FastAPI(title="FrontLines Monitor Suite")
app.add_middleware(
    SessionMiddleware,
    session_cookie=os.environ.get("FRONTLINES_SESSION_COOKIE", "frontlines_session"),
    secret_key=os.environ.get("FRONTLINES_SESSION_SECRET", secrets.token_urlsafe(32)),
    same_site="lax",
    https_only=os.environ.get("FRONTLINES_HTTPS_ONLY", "false").lower() == "true",
    path=SESSION_COOKIE_PATH,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _url(request: Request, path: str) -> str:
    root_path = request.scope.get("root_path", "").rstrip("/")
    if path == "/":
        return f"{root_path}/" if root_path else "/"
    return f"{root_path}{path}"


def _csrf(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def _verify_csrf(request: Request, token: str):
    if not token or token != request.session.get("csrf"):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


def _require_login(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(_url(request, "/login"), status_code=303)
    return None


def _context(request: Request, **kwargs):
    context = {
        "request": request,
        "csrf": _csrf(request),
        "status": manager.status(),
        "message": request.session.pop("message", None),
        "error": request.session.pop("error", None),
        "base_path": request.scope.get("root_path", "").rstrip("/"),
    }
    context.update(kwargs)
    return context


def _flash(request: Request, message: str = None, error: str = None):
    if message:
        request.session["message"] = message
    if error:
        request.session["error"] = error


def _prune_hv_search_cache():
    now = time.time()
    expired_keys = [
        key for key, payload in HV_SEARCH_CACHE.items()
        if now - payload["created_at"] > HV_SEARCH_CACHE_TTL
    ]
    for key in expired_keys:
        HV_SEARCH_CACHE.pop(key, None)
    while len(HV_SEARCH_CACHE) > HV_SEARCH_CACHE_MAX:
        HV_SEARCH_CACHE.popitem(last=False)


def _store_hv_search_results(request: Request, results: list[dict]) -> str:
    request.session.pop("hv_search_results", None)
    cache_id = secrets.token_urlsafe(16)
    HV_SEARCH_CACHE[cache_id] = {"created_at": time.time(), "results": results}
    request.session["hv_search_id"] = cache_id
    _prune_hv_search_cache()
    return cache_id


def _get_hv_search_results(request: Request) -> list[dict]:
    request.session.pop("hv_search_results", None)
    _prune_hv_search_cache()
    cache_id = request.session.get("hv_search_id")
    if not cache_id:
        return []
    payload = HV_SEARCH_CACHE.get(cache_id)
    if not payload:
        request.session.pop("hv_search_id", None)
        return []
    return payload["results"]


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", _context(request))


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), csrf: str = Form(...)):
    _verify_csrf(request, csrf)
    ok, reason = authenticate(username, password)
    if not ok:
        return templates.TemplateResponse(
            request,
            "login.html",
            _context(request, error=reason or "Invalid credentials."),
            status_code=401,
        )
    request.session["authenticated"] = True
    return RedirectResponse(_url(request, "/"), status_code=303)


@app.post("/logout")
async def logout(request: Request, csrf: str = Form(...)):
    _verify_csrf(request, csrf)
    request.session.clear()
    return RedirectResponse(_url(request, "/login"), status_code=303)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "dashboard.html", _context(request, logs=manager.get_logs()))


@app.post("/service/{service}/{action}")
async def service_control(request: Request, service: str, action: str, csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    try:
        manager.control_service(service, action)
        _flash(request, f"{service} {action} requested.")
    except Exception as exc:
        _flash(request, error=str(exc))
    return RedirectResponse(request.headers.get("referer", _url(request, "/")), status_code=303)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "settings.html", _context(request, settings=manager.get_basic_settings()))


@app.post("/settings")
async def save_settings(request: Request, csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    form = await request.form()
    manager.update_basic_settings(form)
    _flash(request, "Settings saved.")
    return RedirectResponse(_url(request, "/settings"), status_code=303)


@app.get("/skutto", response_class=HTMLResponse)
async def skutto_page(request: Request, tab: str = "products", q: str = "", status_filter: str = "pending"):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "skutto.html",
        _context(
            request,
            tab=tab,
            q=q,
            status_filter=status_filter,
            products=manager.get_skutto_products(q),
            pending_skus=manager.get_pending_skus(status_filter, q),
            emails=manager.get_emails(q),
            platforms=manager.get_platforms(),
            settings=manager.get_basic_settings(),
            sheets_error=manager.sheets_error,
            products_cache_path=str(manager.skutto_products_cache),
            products_cache_count=len(manager.sku_data),
            logs=manager.get_logs(40),
        ),
    )


@app.post("/skutto/products/reload")
async def reload_skutto_products(request: Request, csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    try:
        manager.load_skutto_products_from_sheets()
        _flash(request, "SKUtto products reloaded from Google Sheets.")
    except Exception as exc:
        _flash(request, error=str(exc))
    return RedirectResponse(_url(request, "/skutto?tab=products"), status_code=303)


@app.post("/skutto/products/save")
async def save_skutto_product(request: Request, csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    try:
        manager.upsert_skutto_product(await request.form())
        _flash(request, "SKUtto product saved.")
    except Exception as exc:
        _flash(request, error=str(exc))
    return RedirectResponse(_url(request, "/skutto?tab=products"), status_code=303)


@app.post("/skutto/pending/{action}")
async def skutto_pending_action(request: Request, action: str, sku_id: int = Form(...), csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    try:
        form = await request.form()
        if action == "update":
            manager.update_pending_sku(sku_id, form)
            _flash(request, "Pending SKU updated.")
        elif action == "approve":
            manager.approve_pending_sku(sku_id)
            _flash(request, "Pending SKU approved.")
        elif action == "reject":
            manager.reject_pending_sku(sku_id)
            _flash(request, "Pending SKU rejected.")
        else:
            raise HTTPException(status_code=404)
    except Exception as exc:
        _flash(request, error=str(exc))
    return RedirectResponse(_url(request, "/skutto?tab=pending"), status_code=303)


@app.post("/skutto/emails/save")
async def save_email(request: Request, csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    try:
        manager.upsert_email(await request.form())
        _flash(request, "Email mapping saved.")
    except Exception as exc:
        _flash(request, error=str(exc))
    return RedirectResponse(_url(request, "/skutto?tab=emails"), status_code=303)


@app.post("/skutto/emails/bulk")
async def bulk_email_import(request: Request, mappings: str = Form(...), csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    try:
        result = manager.bulk_import_emails(mappings)
        message = f"Bulk import complete: {result['added']} added, {result['skipped']} skipped."
        if result["errors"]:
            message += f" {len(result['errors'])} row error(s): " + "; ".join(result["errors"][:5])
        _flash(request, message)
    except Exception as exc:
        _flash(request, error=str(exc))
    return RedirectResponse(_url(request, "/skutto?tab=emails"), status_code=303)


@app.post("/skutto/emails/delete")
async def delete_email(request: Request, email: str = Form(...), discord_id: int = Form(...), csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    manager.delete_email(email, discord_id)
    return RedirectResponse(_url(request, "/skutto?tab=emails"), status_code=303)


@app.post("/skutto/platforms/save")
async def save_platform(request: Request, csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    try:
        manager.upsert_platform(await request.form())
        _flash(request, "Platform mapping saved.")
    except Exception as exc:
        _flash(request, error=str(exc))
    return RedirectResponse(_url(request, "/skutto?tab=platforms"), status_code=303)


@app.post("/skutto/platforms/delete")
async def delete_platform(request: Request, platform_id: int = Form(...), csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    manager.delete_platform(platform_id)
    return RedirectResponse(_url(request, "/skutto?tab=platforms"), status_code=303)


@app.get("/shopify", response_class=HTMLResponse)
async def shopify_page(request: Request, q: str = "", stock: str = "all"):
    redirect = _require_login(request)
    if redirect:
        return redirect
    variants = manager.get_shopify_variants(q, stock)
    return templates.TemplateResponse(
        request,
        "shopify.html",
        _context(
            request,
            settings=manager.get_shopify_settings(),
            variants=variants,
            q=q,
            stock=stock,
            logs=manager.get_logs(40),
        ),
    )


@app.post("/shopify")
async def save_shopify(request: Request, csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    manager.update_shopify_settings(await request.form())
    _flash(request, "Shopify settings saved.")
    return RedirectResponse(_url(request, "/shopify"), status_code=303)


@app.post("/shopify/tracker/{action}")
async def shopify_tracker(request: Request, action: str, csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    if action == "clear":
        manager.clear_shopify_tracker()
    elif action == "reload":
        manager.reload_shopify_tracker()
    else:
        raise HTTPException(status_code=404)
    return RedirectResponse(_url(request, "/shopify"), status_code=303)


@app.post("/shopify/variants/reset")
async def reset_shopify_variants(request: Request, csrf: str = Form(...), selected: list[str] = Form(default=[])):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    manager.reset_shopify_variants(selected)
    return RedirectResponse(_url(request, "/shopify"), status_code=303)


@app.get("/hv", response_class=HTMLResponse)
async def hv_page(request: Request, q: str = ""):
    redirect = _require_login(request)
    if redirect:
        return redirect
    results = _get_hv_search_results(request)
    return templates.TemplateResponse(
        request,
        "hv.html",
        _context(
            request,
            settings=manager.get_hv_settings(),
            products=manager.get_hv_products(),
            q=q,
            results=results,
            logs=manager.get_logs(40),
        ),
    )


@app.post("/hv")
async def save_hv(request: Request, csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    manager.update_hv_settings(await request.form())
    _flash(request, "HV settings saved.")
    return RedirectResponse(_url(request, "/hv"), status_code=303)


@app.post("/hv/add")
async def add_hv(request: Request, product_id: str = Form(...), ping: str = Form(default=""), csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    manager.add_hv_product_by_id(product_id, bool(ping))
    return RedirectResponse(_url(request, "/hv"), status_code=303)


@app.post("/hv/products/{action}")
async def hv_products(request: Request, action: str, csrf: str = Form(...), selected: list[str] = Form(default=[])):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    if action == "remove":
        manager.remove_hv_products(selected)
    elif action == "toggle-ping":
        manager.toggle_hv_product_pings(selected)
    elif action == "reset-stock":
        manager.reset_hv_stock(selected)
    else:
        raise HTTPException(status_code=404)
    return RedirectResponse(_url(request, "/hv"), status_code=303)


@app.post("/hv/search")
async def hv_search(request: Request, keyword: str = Form(...), csrf: str = Form(...)):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    search_term = keyword.strip()
    try:
        results = manager.search_hv_products(search_term)
        _store_hv_search_results(request, results)
        if not results:
            _flash(request, "No HV products found for that search.")
    except Exception as exc:
        _store_hv_search_results(request, [])
        _flash(request, error=f"HV search failed: {exc}")
    return RedirectResponse(_url(request, f"/hv?{urlencode({'q': search_term})}"), status_code=303)


@app.post("/hv/search/add")
async def add_hv_search(
    request: Request,
    csrf: str = Form(...),
    selected: list[str] = Form(default=[]),
    ping: str = Form(default=""),
):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    results = _get_hv_search_results(request)
    manager.add_hv_search_results(selected, json.dumps(results), bool(ping))
    request.session.pop("hv_search_id", None)
    return RedirectResponse(_url(request, "/hv"), status_code=303)


@app.get("/api/status")
async def api_status(request: Request):
    redirect = _require_login(request)
    if redirect:
        raise HTTPException(status_code=401)
    return manager.status()


@app.get("/api/logs")
async def api_logs(request: Request, limit: int = 80):
    redirect = _require_login(request)
    if redirect:
        raise HTTPException(status_code=401)
    return {"logs": manager.get_logs(max(1, min(limit, 200)))}
