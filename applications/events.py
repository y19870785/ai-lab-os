"""Application Events。"""
class AppEventTypes:
    APP_REGISTERED = "application.registered"
    APP_STARTED = "application.started"
    APP_COMPLETED = "application.completed"
    APP_FAILED = "application.failed"
    APP_STOPPED = "application.stopped"

async def publish_app_event(bus, event_type: str, app_id: str, extra: dict | None = None):
    if not bus: return
    from core.bus.event import Event
    evt = Event(event_type=event_type, source="application.runtime",
                payload={"app_id": app_id, **(extra or {})})
    await bus.publish(event_type, evt)
