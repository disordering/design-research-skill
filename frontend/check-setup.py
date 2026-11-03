"""Read-only local preflight. Never prints keys or calls paid model APIs."""
import sys
import importlib.util
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
errors = []
print('Python 3.11+:', 'OK' if sys.version_info >= (3,11) else 'MISSING: current ' + sys.version.split()[0])
if sys.version_info < (3,11): errors.append('Use Python 3.11 or 3.12 and recreate repository .venv')
for name in ['fastapi','uvicorn','httpx','pydantic','PIL','anyio','playwright','mcp','bs4','pypdf']:
    ok = importlib.util.find_spec(name) is not None
    print(name + ': ' + ('OK' if ok else 'MISSING'))
    if not ok: errors.append('Install requirements-session.txt: ' + name)
print('Node.js:', 'OK' if shutil.which('node') else 'MISSING (required for frontend)')
if not shutil.which('node'): errors.append('Install Node.js LTS')
config = root / 'config/reviewer.toml'
print('reviewer.toml:', 'present' if config.is_file() else 'MISSING')
if not config.is_file(): errors.append('Copy config/reviewer.example.toml to config/reviewer.toml')
values = {}
if (root / '.env').is_file():
    for line in (root / '.env').read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=',1)
            values[key.strip()] = value.strip().strip('"').strip("'")
provider = values.get('REVIEW_PROVIDER','')
if provider == 'generic':
    from urllib.parse import urlsplit
    for key in ['REVIEW_BASE_URL','REVIEW_MODEL','REVIEW_API_KEY']:
        ok = bool(values.get(key,''))
        print(key + ': ' + ('set (value hidden)' if ok else 'MISSING'))
        if not ok: errors.append('Fill local .env: ' + key)
    u = urlsplit(values.get('REVIEW_BASE_URL',''))
    if u.scheme not in ['http','https'] or not u.hostname or u.hostname.endswith('.example') or u.username or u.password:
        errors.append('Replace example model endpoint with a valid HTTP(S) base URL without credentials')
    try:
        import tomllib
        d=tomllib.loads(config.read_text(encoding='utf-8-sig')) if config.is_file() else {}
        if d.get('screen_review',{}).get('provider') != 'generic':
            errors.append('Set screen_review.provider=generic if using only generic service')
    except ImportError:
        pass
    except Exception:
        errors.append('reviewer.toml syntax is invalid')
else:
    print('Model config: generic template not selected; verify your provider locally before model use')
    errors.append('This preflight expects the generic handoff template; configure .env or validate another provider separately')
if errors:
    print('NOT READY:')
    for error in errors: print('- ' + error)
else:
    print('Preflight passed. This does not verify credentials, network, browser binary or model quality.')
raise SystemExit(1 if errors else 0)
