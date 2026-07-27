"""The claude-cli backend has no schema enforcement and maths papers are
almost entirely backslashes, so ~20% of extractions returned invalid JSON
until _repair_json existed. Run: .venv/bin/python tests/test_json_repair.py
"""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import try_extract as t, try_assess as a

cases = {
    "latex alpha":      '{"v": "the graph \\alpha here"}',
    "latex braces":     '{"v": "set \\{x\\} and \\$G\\$"}',
    "already-valid \\\\": '{"v": "path C:\\\\valid\\\\dir"}',
    "valid \\n":        '{"v": "line one\\nline two"}',
    "valid \\u":        '{"v": "\\u00e9clair"}',
    "invalid \\umbral": '{"v": "\\umbral calculus"}',
    "quote inside":     '{"v": "he said \\"hi\\" loudly"}',
    "trailing slash":   '{"v": "ends with \\\\"}',
}
ok = True
for name, raw in cases.items():
    try:
        got = t._parse_json(raw)["v"]
        same = a._parse_json(raw)["v"] == got
        print(f"  {'OK ' if same else 'MISMATCH'} {name:20} -> {got!r}")
        ok &= same
    except Exception as e:
        print(f"  FAIL {name:20} -> {type(e).__name__}: {e}")
        ok = False
print("\nall passed" if ok else "\nFAILURES")
sys.exit(0 if ok else 1)
