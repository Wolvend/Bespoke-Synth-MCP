import json
import time

import oscoutput

CMD_PORT = 9001
REPLY_OSCOUTPUT_NAME = "oscout"
_seen = {}


def _now_ms():
    return int(time.time() * 1000)


def _parse_message(msg):
    if isinstance(msg, (list, tuple)) and len(msg) >= 1:
        return str(msg[0]), list(msg[1:])
    addr = getattr(msg, "address", None)
    args = getattr(msg, "args", None) or getattr(msg, "params", None)
    if addr is not None:
        return str(addr), list(args) if args is not None else []
    return "", [msg]


def _reply(obj):
    oscoutput.get(REPLY_OSCOUTPUT_NAME).send_string("/mcp/reply", json.dumps(obj))


def on_load():
    me.connect_osc_input(CMD_PORT)
    me.output(f"bspk MCP agent listening on OSC {CMD_PORT}")


def on_osc(message):
    addr, args = _parse_message(message)
    if addr != "/mcp/cmd" or not args:
        return
    try:
        payload = json.loads(args[0])
    except Exception as exc:
        _reply({"ok": False, "error": f"bad_json: {exc}", "ts": _now_ms()})
        return

    idem = payload.get("idempotency_key")
    correlation_id = payload.get("correlation_id") or idem
    if idem and idem in _seen:
        cached = dict(_seen[idem])
        cached["correlation_id"] = correlation_id
        cached["idempotency_key"] = idem
        _reply(cached)
        return

    op = payload.get("op")
    try:
        if op == "set":
            me.set(payload["path"], payload["value"])
            out = {"ok": True, "op": "set", "path": payload["path"]}
        elif op == "get":
            value = me.get(payload["path"])
            out = {"ok": True, "op": "get", "path": payload["path"], "value": value}
        elif op == "batch_set":
            for step in payload["ops"]:
                me.set(step["path"], step["value"])
            out = {"ok": True, "op": "batch_set", "count": len(payload["ops"])}
        elif op == "play_note":
            # Replace with your patch-specific note trigger path if needed.
            me.schedule_call("play_note", 0)
            out = {"ok": True, "op": "play_note"}
        elif op == "schedule_notes":
            out = {"ok": True, "op": "schedule_notes", "count": len(payload["notes"])}
        elif op == "transport_set":
            if payload.get("bpm") is not None:
                me.set("transport~tempo", payload["bpm"])
            out = {"ok": True, "op": "transport_set"}
        elif op == "snapshot_load":
            me.set("snapshots~load", payload["name"])
            out = {"ok": True, "op": "snapshot_load", "name": payload["name"]}
        else:
            out = {"ok": False, "error": "unknown_op", "op": op}
    except Exception as exc:
        out = {"ok": False, "error": str(exc), "op": op}

    out["ts"] = _now_ms()
    out["correlation_id"] = correlation_id
    if idem:
        out["idempotency_key"] = idem
        _seen[idem] = out
    _reply(out)

