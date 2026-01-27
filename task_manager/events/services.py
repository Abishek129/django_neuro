from task_manager.models import Event


def get_events(metric: str | None = None, severity: str | None = None, limit: int = 50) -> dict:
    try:
        qs = Event.objects.all()
        if metric:
            qs = qs.filter(metric=metric)
        if severity:
            qs = qs.filter(severity=severity)
        qs = qs[:limit]

        events = []
        for e in qs:
            events.append({
                "id": e.id,
                "metric": e.metric,
                "severity": e.severity,
                "message": e.message,
                "value": e.value,
                "threshold": e.threshold,
                "created_at": e.created_at.isoformat(),
            })

        return {"events": events, "count": len(events)}
    except Exception as e:
        return {"error": str(e), "events": [], "count": 0}
