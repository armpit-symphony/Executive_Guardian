#!/usr/bin/env python3
import sys, json, traceback

def out(obj, code=0):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    raise SystemExit(code)

def load_guardian():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import guardian as g
    return g

def serialize_result(res):
    try:
        if hasattr(res, "returncode") and hasattr(res, "stdout") and hasattr(res, "stderr"):
            return {
                "args": getattr(res, "args", None),
                "returncode": getattr(res, "returncode", None),
                "stdout": getattr(res, "stdout", None),
                "stderr": getattr(res, "stderr", None),
            }
        json.dumps(res)
        return res
    except Exception:
        return {"_type": type(res).__name__, "repr": repr(res)}

def main():
    raw = sys.stdin.read()
    if not raw or not raw.strip():
        out({"ok": False, "error": "empty_input"}, 2)

    try:
        msg = json.loads(raw)
    except Exception as e:
        out({"ok": False, "error": "invalid_json", "detail": str(e), "raw": raw[:500]}, 2)

    msg_type = msg.get("type")
    if not msg_type:
        out({"ok": False, "error": "missing_type"}, 2)

    g = load_guardian()

    try:
        if msg_type == "ping":
            out({"ok": True, "type": "ping", "status": g.get_status()})

        elif msg_type == "command_exec":
            task_id = msg.get("task_id", "unknown")
            lane = msg.get("lane", "main")
            command = msg.get("command")
            if not command:
                out({"ok": False, "type": msg_type, "error": "missing_command"}, 2)

            res = g.wrap_command_exec(task_id=task_id, lane=lane, command=command)
            out({"ok": True, "type": msg_type, "task_id": task_id, "lane": lane, "result": serialize_result(res)})

        elif msg_type == "file_write":
            # expects: task_id, lane, path, content (string or bytes via base64 later; keep string now)
            from pathlib import Path
            task_id = msg.get("task_id", "unknown")
            lane = msg.get("lane", "main")
            path = msg.get("path")
            content = msg.get("content", "")
            if not path:
                out({"ok": False, "type": msg_type, "error": "missing_path"}, 2)

            def perform():
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                # content is string
                p.write_text(content, encoding="utf-8")
                return {"written": True, "path": str(p), "bytes": len(content.encode("utf-8"))}

            def validate(res):
                p = Path(path)
                ok = p.exists() and p.stat().st_size > 0
                tier = "success" if ok else "fail"
                meta = {"exists": p.exists(), "size": (p.stat().st_size if p.exists() else 0), "path": str(p)}
                return (tier, meta)

            # Use the guardian membrane directly so it journals + validates
            result = g.exec_with_guard(
                task_id=task_id,
                lane=lane,
                action_type="file_write",
                expected_outcome=f"file_write {path}",
                confidence_pre=0.75,
                perform_fn=perform,
                validate_fn=validate,
                metadata={"path": path, "content_len": len(content)},
            )
            out({"ok": True, "type": msg_type, "task_id": task_id, "lane": lane, "result": serialize_result(result)})

        elif msg_type == "http_request":
            task_id = msg.get("task_id", "unknown")
            lane = msg.get("lane", "main")
            expected_statuses = msg.get("expected_statuses", (200, 201, 202, 204))
            req = msg.get("request") or {}
            method = (req.get("method") or "GET").upper()
            url = req.get("url")
            if not url:
                out({"ok": False, "type": msg_type, "error": "missing_url"}, 2)

            import urllib.request
            data = None
            if req.get("body") is not None:
                b = req["body"]
                data = b.encode("utf-8") if isinstance(b, str) else b

            headers = req.get("headers") or {}

            def _do():
                r = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(r, timeout=30) as resp:
                    body = resp.read()
                    body_txt = body.decode("utf-8", errors="replace")
                    return {"status": resp.status, "headers": dict(resp.headers), "body": body_txt}

            res = g.wrap_http_request(
                task_id=task_id,
                lane=lane,
                request_fn=_do,
                expected_statuses=tuple(expected_statuses),
            )
            out({"ok": True, "type": msg_type, "task_id": task_id, "lane": lane, "result": serialize_result(res)})

        else:
            out({"ok": False, "error": "unknown_type", "type": msg_type}, 2)

    except SystemExit:
        raise
    except Exception as e:
        out({"ok": False, "type": msg_type, "error": "exception", "detail": str(e), "trace": traceback.format_exc()}, 1)

if __name__ == "__main__":
    main()
