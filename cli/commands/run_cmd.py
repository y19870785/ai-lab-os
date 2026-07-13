async def run(args):
    app_name = args[0] if args else "alpha_assistant"
    from api.dependencies import get_runtime
    runtime = get_runtime()
    apps = await runtime.list_applications()
    print(f"Running application: {app_name}")
    print(f"Registered applications: {len(apps)}")
    for a in apps:
        print(f"  - {a.name} v{a.version} [{a.status.value}]")
