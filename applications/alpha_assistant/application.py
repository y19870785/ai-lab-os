"""Alpha Assistant —— AI-Lab 首个可运行业务应用。

支持 Mock 和 Real Provider 两种模式。
"""

from applications.models import ApplicationRequest, ApplicationResponse


class AlphaAssistant:
    """Alpha Assistant 应用实现。

    通过 ApplicationRuntime.execute() 调度，不直接访问底层。
    """

    def __init__(self, runtime=None):
        self._runtime = runtime

    async def run(self, request: ApplicationRequest) -> ApplicationResponse:
        if self._runtime:
            return await self._runtime.execute(request)
        raise RuntimeError("AlphaAssistant runtime is not configured")
