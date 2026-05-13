"""FastAPI web admin app for VPS deployments."""
import json
import os
import secrets
from pathlib import Path

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

app = FastAPI(title="FrontLines Monitor Suite")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("FRONTLINES_SESSION_SECRET", secrets.token_urlsafe(32)),
    same_site="lax",
    https_only=os.environ.get("FRONTLINES_HTTPS_ONLY", "false").lower() == "true",
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
    results = request.session.pop("hv_search_results", None)
    if results:
        results = json.loads(results)
    return templates.TemplateResponse(
        request,
        "hv.html",
        _context(
            request,
            settings=manager.get_hv_settings(),
            products=manager.get_hv_products(),
            q=q,
            results=results or [],
            results_json=json.dumps(results or []),
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
    results = manager.search_hv_products(keyword.strip())
    request.session["hv_search_results"] = json.dumps(results)
    return RedirectResponse(_url(request, f"/hv?q={keyword}"), status_code=303)


@app.post("/hv/search/add")
async def add_hv_search(
    request: Request,
    csrf: str = Form(...),
    results_json: str = Form(default="[]"),
    selected: list[str] = Form(default=[]),
    ping: str = Form(default=""),
):
    redirect = _require_login(request)
    if redirect:
        return redirect
    _verify_csrf(request, csrf)
    manager.add_hv_search_results(selected, results_json, bool(ping))
    return RedirectResponse(_url(request, "/hv"), status_code=303)


@app.get("/api/status")
async def api_status(request: Request):
    redirect = _require_login(request)
    if redirect:
        raise HTTPException(status_code=401)
    return manager.status()
