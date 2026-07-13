async def run(args):
    from api.dependencies import get_runtime
    runtime = get_runtime()
    hc = await runtime.health_check()
    print("=" * 50)
    print("AI-Lab v0.30.0 Alpha")
    print("=" * 50)
    print(f"Status:   {hc['status']}")
    print(f"Apps:     {hc['applications']}")
    print(f"Provider: {hc['provider_mode']}")
    print(f"API:      http://localhost:8000 (run 'python -m api.app')")
