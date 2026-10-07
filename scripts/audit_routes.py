"""Audit all API routes and report which ones have @require_role protection."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.app import app


PUBLIC_ENDPOINTS = {
    "/api/auth/login",
    "/api/time/current",
    "/api/status",
    "/api/scan",
    "/api/sync",
    "/api/static/<path:filename>",
}


def main():
    guarded = []
    unguarded = []
    public = []

    for rule in app.url_map.iter_rules():
        endpoint = rule.endpoint
        if endpoint == "static":
            continue

        func = app.view_functions.get(endpoint)
        if func is None:
            continue

        has_role = False
        try:
            closure = func.__closure__
            if closure:
                for cell in closure:
                    try:
                        if "require_role" in str(cell.cell_contents):
                            has_role = True
                            break
                        if hasattr(cell.cell_contents, "__name__") and "require_role" in cell.cell_contents.__name__:
                            has_role = True
                            break
                    except (ValueError, AttributeError):
                        pass
        except (TypeError, AttributeError):
            pass

        if not has_role:
            wrapped = getattr(func, "__wrapped__", None)
            if wrapped:
                has_role = True

        methods = sorted(rule.methods - {"HEAD", "OPTIONS"})
        route_str = rule.rule

        entry = f"{route_str:50s} methods={str(methods):30s}"

        if route_str in PUBLIC_ENDPOINTS:
            public.append(entry + " PUBLIC")
        elif has_role:
            guarded.append(entry + " GUARDED")
        else:
            unguarded.append(entry + " ⚠ UNGUARDED")

    print("=" * 120)
    print("ROUTE AUDIT REPORT")
    print("=" * 120)

    print(f"\n🔒 GUARDED routes ({len(guarded)}):")
    for e in guarded:
        print(f"  {e}")

    print(f"\n🌐 PUBLIC routes ({len(public)}):")
    for e in public:
        print(f"  {e}")

    print(f"\n⚠️  UNGUARDED routes ({len(unguarded)}):")
    for e in unguarded:
        print(f"  {e}")

    if unguarded:
        print(f"\n❌ {len(unguarded)} routes lack @require_role protection!")
        return 1
    print(f"\n✅ All non-public routes are protected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
