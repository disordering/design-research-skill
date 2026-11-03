"""Frontend-owned launcher. Prefer Python >=3.11; never edit engine sources."""
import asyncio
import os
import sys
import os
import runpy
from pathlib import Path
from contextlib import asynccontextmanager


def install_timeout_compat():
    if hasattr(asyncio, 'timeout'):
        return False
    from anyio import fail_after
    @asynccontextmanager
    async def timeout(delay):
        with fail_after(delay):
            yield
    asyncio.timeout = timeout
    return True


async def self_test():
    async with asyncio.timeout(1):
        await asyncio.sleep(0)
    try:
        async with asyncio.timeout(0.01):
            await asyncio.sleep(1)
    except TimeoutError:
        pass
    else:
        raise AssertionError('timeout did not interrupt')
    try:
        async with asyncio.timeout(1):
            raise ValueError('original error')
    except ValueError:
        pass
    else:
        raise AssertionError('original error lost')
    async def cancelled():
        async with asyncio.timeout(2):
            await asyncio.sleep(1)
    task = asyncio.create_task(cancelled())
    await asyncio.sleep(0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError('external cancellation lost')


if __name__ == '__main__':
    patched = install_timeout_compat()
    if '--self-test' in sys.argv:
        asyncio.run(self_test())
        print('timeout self-test passed; compatibility=' + str(patched))
    else:
        backend = Path(sys.argv[1]).resolve()
        if not (backend / 'engine' / '__main__.py').is_file():
            raise SystemExit('Backend directory is invalid')
        import json
        selection = backend / 'out/backend-selection.json'
        if selection.is_file():
            selected = json.loads(selection.read_text(encoding='utf-8-sig'))
            if selected.get('enabled'):
                candidate = (backend / selected['path']).resolve()
                if not candidate.is_relative_to(backend / 'out') or not (candidate / 'engine/__main__.py').is_file():
                    raise SystemExit('Invalid temporary backend selection')
                backend = candidate
                print('Temporary B engine copy active: ' + str(backend), flush=True)
        # Explicit local proxy settings must override inherited launcher proxy values.
        envfile = backend / '.env'
        if envfile.exists():
            proxies = {}
            for line in envfile.read_text(encoding='utf-8-sig').splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    key, value = line.split('=', 1)
                    if key.strip() in {'HTTP_PROXY','HTTPS_PROXY','NO_PROXY'}:
                        proxies[key.strip()] = value.strip().strip('"').strip("'")
            for key, value in proxies.items():
                os.environ[key] = value
                os.environ[key.lower()] = value
            if proxies.get('HTTPS_PROXY'):
                os.environ['ALL_PROXY'] = proxies['HTTPS_PROXY']
                os.environ['all_proxy'] = proxies['HTTPS_PROXY']
        sys.path.insert(0, str(backend))
        # Explicit local network configuration must take priority over inherited app proxies.
        env_file = backend / '.env'
        if env_file.is_file():
            for line in env_file.read_text(encoding='utf-8-sig').splitlines():
                key, sep, value = line.strip().partition('=')
                if sep and key in {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY'}:
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
                    os.environ[key.lower()] = value
        # C-owned profile adapter: generic endpoints otherwise ignore thinking settings.
        from engine import session_models
        from engine.config import load_reviewer_config
        original_factory = session_models.build_session_model
        def configured_session_model(request):
            client = original_factory(request)
            profile = load_reviewer_config(required=False).get('providers', {}).get(request.provider, {})
            if request.provider == 'generic' and 'session_enable_thinking' in profile:
                client.session_extra_body = {
                    **getattr(client, 'session_extra_body', {}),
                    'enable_thinking': bool(profile['session_enable_thinking']),
                }
            return client
        session_models.build_session_model = configured_session_model
        if patched:
            print('Python 3.10 timeout compatibility enabled; Python 3.11+ recommended.', flush=True)
        sys.argv = ['engine', 'serve', '--port', '8000']
        runpy.run_module('engine', run_name='__main__')
