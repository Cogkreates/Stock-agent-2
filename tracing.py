"""neatlogs tracing, with a safe fallback.

Tracing turns on only when the `neatlogs` package is installed AND
NEATLOGS_API_KEY is set. Otherwise every helper here is a no-op, so the demo
still runs anywhere. Works with older and newer versions of the SDK.
"""
import functools
import os
import sys

try:
    import neatlogs
except ImportError:          # package not installed: tracing stays off
    neatlogs = None

ENABLED = False


def init(workflow_name="stock-agent"):
    """Call once at startup, before running the agent."""
    global ENABLED
    key = os.environ.get("NEATLOGS_API_KEY")
    if neatlogs is None or not key:
        return False
    kwargs = {"api_key": key, "workflow_name": workflow_name, "capture_logs": True}
    endpoint = os.environ.get("NEATLOGS_ENDPOINT")   # only needed for EU projects
    if endpoint:
        kwargs["endpoint"] = endpoint
    try:
        neatlogs.init(**kwargs)
    except TypeError:
        # Older SDK without some options: retry with the basics (default endpoint).
        neatlogs.init(api_key=key, workflow_name=workflow_name)
    ENABLED = True
    return True


def traced(kind, name=None, **span_kwargs):
    """Decorator: record the function as a neatlogs span of the given kind.

    Wrapping happens at call time, so it is safe to apply before init().
    If neatlogs rejects the span options, the function just runs untraced.
    """
    def deco(fn):
        state = {}

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not ENABLED:
                return fn(*args, **kwargs)
            if "span_fn" not in state:
                try:
                    state["span_fn"] = neatlogs.span(kind=kind, name=name or fn.__name__, **span_kwargs)(fn)
                except Exception as e:
                    print(f"[tracing] cannot trace {fn.__name__}: {e}", file=sys.stderr)
                    state["span_fn"] = fn
            return state["span_fn"](*args, **kwargs)
        return wrapper
    return deco


def log(template, level="info", **data):
    """Structured log line attached to the active span (dropped outside a span)."""
    if ENABLED and hasattr(neatlogs, "log"):
        try:
            neatlogs.log(template, level=level, **data)
        except Exception:
            pass


def shutdown():
    """Flush and stop the exporter. Call at the end of the script."""
    if ENABLED:
        if hasattr(neatlogs, "flush"):
            neatlogs.flush()
        if hasattr(neatlogs, "shutdown"):
            neatlogs.shutdown()
