async def run(args):
    from api.dependencies import get_runtime
    runtime = get_runtime()
    result = await runtime.health_check()
    print(f"Status: {result['status']}")
    print(f"Applications: {result['applications']}")
    print(f"Provider mode: {result['provider_mode']}")
