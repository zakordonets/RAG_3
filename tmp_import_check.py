import importlib, sys
mods = [
    'adapters.telegram.polling',
    'app.routes.chat',
    'app.infrastructure',
    'app.services.infrastructure.orchestrator',
]
for m in mods:
    try:
        importlib.import_module(m)
        print('OK', m)
    except Exception as e:
        print('FAIL', m, type(e).__name__, e)
        sys.exit(1)
print('All imports OK')
