"""neatlogs tracing, with a safe fallback.

Tracing turns on only when the `neatlogs` package is installed AND
NEATLOGS_API_KEY is set. Otherwise every helper here is a no-op, so the demo
still runs anywhere. Span kinds follow the neatlogs Python SDK docs.
"""
import functools
import os

try:
    import neatlogs
except ImportError:          # package not installed: tracing stays off
    neatlogs = None

ENABLED = False


def init(workflow_name="stock-agent"):
    """Call once at startup, before running the agent."""
    global ENABLED
    key = os.environ.get("NEATLOGS_API_KEY")
    if neatlogs is not None and key:
        neatlogs.init(
            api_key=key,
            # Regional ingest base URL (no /v1/traces). EU projects use https://eu.ingest.neatlogs.com
            endpoint=os.environ.get("NEATLOGS_ENDPOINT", "https://ingest.neatlogs.com"),
            workflow_name=workflow_name,
            capture_logs=True,
        )
        ENABLED = True
    return ENABLED


def traced(kind, name=None, **span_kwargs):
    """Decorator: record the function as a neatlogs span of the given kind.

    Wrapping happens at call time, so it is safe to apply before init().
    Examples: traced("TOOL", tool_name="place_order"), traced("AGENT", role=..., goal=...)
    """
    def deco(fn):
        state = {}

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not ENABLED:
                return fn(*args, **kwargs)
            if "span_fn" not in state:
                state["span_fn"] = neatlogs.span(kind=kind, name=name or fn.__name__, **span_kwargs)(fn)
            return state["span_fn"](*args, **kwargs)
        return wrapper
    return deco


def log(template, level="info", **data):
    """Structured log line attached to the active span (dropped outside a span)."""
    if ENABLED:
        neatlogs.log(template, level=level, **data)


def shutdown():
    """Flush and stop the exporter. Call at the end of the script."""
    if ENABLED:
        neatlogs.flush()
        neatlogs.shutdown()
