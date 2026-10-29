#!/usr/bin/env python3
"""Recompute the report's headline claims from the raw evidence. Run in WSL: python3 ~/exp/review/evidence.py"""
import json, glob, re, datetime, subprocess, os
HOME = os.path.expanduser("~"); EXP = HOME + "/exp"
PROJ = glob.glob("/mnt/c/Users/*/.claude/projects")[0]
def ts(s): return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
def session(m):
    for f in glob.glob("%s/--wsl-localhost-Ubuntu-24-04-home-%s-exp-nebula-%s/*.jsonl" % (PROJ, os.path.basename(HOME), m)):
        ev = []
        for l in open(f):
            try: ev.append(json.loads(l))
            except Exception: pass
        if any(e.get("type") == "user" and "WEIGHTED SHORTEST PATH" in json.dumps(e.get("message", "")).upper() for e in ev):
            ev = [e for e in ev if e.get("timestamp")]; ev.sort(key=lambda e: e["timestamp"]); return f, ev
def calls(ev):
    uses, res = {}, {}
    for e in ev:
        c = (e.get("message") or {}).get("content")
        if not isinstance(c, list): continue
        for b in c:
            if not isinstance(b, dict): continue
            if b.get("type") == "tool_use": uses[b["id"]] = (e["timestamp"], b["name"], b.get("input", {}))
            if b.get("type") == "tool_result":
                r = b.get("content"); r = r if isinstance(r, str) else " ".join(x.get("text", "") for x in r if isinstance(x, dict))
                res[b["tool_use_id"]] = (e["timestamp"], r)
    return uses, res
def text(e):
    c = e["message"].get("content")
    return c if isinstance(c, str) else " ".join(b.get("text", "") for b in c if isinstance(b, dict))
def git(repo, *a): return subprocess.run(["git", "-C", repo] + list(a), capture_output=True, text=True).stdout
# E11 rule (section 5.4): Read/Grep/Glob, or a shell command using one of these readers, unless it runs git or the build/test scripts
LOOK = re.compile(r"""(^|[\s;|&("'])(cat|grep|rg|find|head|tail|ls|sed -n|awk)\b""")
RUNS = re.compile(r"""\bgit\b|(^|[;&|("']\s*)\S*(build|test)\.sh\b""")
prompts = {}
for m, label in [("claude", "Plain Claude Code"), ("speckit", "Spec Kit")]:
    f, ev = session(m); t0 = ts(ev[0]["timestamp"]); uses, res = calls(ev)
    mins = lambda t: (ts(t) - t0).total_seconds() / 60
    passt = min(t for t, r in res.values() if "RESULT WEIGHTED: 17 passed" in r)
    print("==== %s  (session file %s)" % (label, os.path.basename(f)))
    print("E1  session start %s UTC; first ALL PASS +%.1f min" % (ev[0]["timestamp"][11:19], mins(passt)))
    usage, ntool = {}, 0
    for e in ev:
        if e["timestamp"] > passt: continue
        mg = e.get("message") or {}
        if e.get("type") == "assistant" and mg.get("usage"): usage[mg.get("id")] = mg["usage"]
    for t, n, i in uses.values():
        if t <= passt: ntool += 1
    tk = sum(sum((u.get(k) or 0) for k in ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]) for u in usage.values())
    print("E2  timed run: tokens %s, output tokens %s, tool calls %d" % (format(tk, ","), format(sum(u.get("output_tokens", 0) for u in usage.values()), ","), ntool))
    runs = [(mins(t), re.search(r"RESULT WEIGHTED: (\d+) passed", r).group(1)) for t, r in sorted(res.values()) if t <= passt and re.search(r"RESULT WEIGHTED: (\d+) passed", r)]
    seen = []; [seen.append(x) for x in runs if not seen or abs(seen[-1][0] - x[0]) > 0.2 or seen[-1][1] != x[1]]
    print("E3  acceptance results up to and including the first pass: %s" % ", ".join("%s/17 at +%.1f" % (s, t) for t, s in seen))
    errs = sorted({round(mins(t), 1) for t, r in res.values() if t <= passt and re.search(r"\.(cpp|h|yy):\d+:\d+: (fatal )?error", r)})
    print("E4  tool results showing a C++ compile error before the pass, at minutes: %s" % (errs or "none"))
    rd = [(mins(t), n) for t, n, i in uses.values() if re.search(r"weighted_tests\.py", json.dumps(i)) and re.search(r"\b(cat|less|head|Read)\b|^Read$", json.dumps(i) + n)]
    print("E5  opened the acceptance test source weighted_tests.py: %s" % (("yes, at +%.1f min" % min(rd)[0]) if rd else "no"))
    for e in ev:
        if e.get("type") == "user" and "Build with" in text(e):
            s = text(e); s = re.split(r"</pasted_content[^>]*>|</command-args>", s[s.find("In the NebulaGraph"):])[0].strip()
            prompts[label] = s; i = s.find("Build with")
            print("E6  delivered prompt: %d characters; build line: %s" % (len(s), s[i:s.find("\n", i)])); break
    first = None
    for u, (t, n, i) in sorted(uses.items(), key=lambda x: x[1][0]):
        r = res.get(u, ("", ""))[1]; c = i.get("command", "")
        if n in ("Edit", "Write", "MultiEdit") and "src" in i.get("file_path", "") and "error" not in r.lower()[:200]: first = t; break
        if n in ("Bash", "PowerShell") and "/src" in c and re.search(r"\.write\(|sed -i", c) and not re.search(r"not found|Traceback|rror", r): first = t; break
    nl = [(mins(t), n) for t, n, i in uses.values() if t < first and (n in ("Read", "Grep", "Glob") or (n in ("Bash", "PowerShell") and LOOK.search(i.get("command", "")) and not RUNS.search(i.get("command", ""))))]
    print("E11 look-ups before the first successful source change (at +%.1f min): %d" % (mins(first), len(nl)))
    repo = "%s/nebula-%s" % (EXP, m)
    rows = [l.split("\t") for l in git(repo, "diff", "--numstat", "baseline", "HEAD", "--", "src").splitlines()]
    prod = [(int(a), int(d)) for a, d, p in rows if "/test/" not in p]; test = [int(a) for a, d, p in rows if "/test/" in p]
    print("E7  src lines added vs baseline: production +%d/-%d in %d files; tests +%d in %d files" % (sum(a for a, d in prod), sum(d for a, d in prod), len(prod), sum(test), len(test)))
    o = json.load(open("%s/review/out-nebula-%s.json" % (EXP, m))); o2 = json.load(open("%s/review/out2-nebula-%s.json" % (EXP, m)))
    pr = o["probes"] + [p for p in o2["probes"]]
    print("E8  hidden suite: randomised %d/%d correct; probes passed %d/%d; failed probes: %s" % (o["oracle"]["correct"], o["oracle"]["total"], sum(p["pass"] for p in pr), len(pr), ", ".join(p["id"] for p in pr if not p["pass"])))
    b = json.load(open("%s/review/out-base.json" % EXP))["existing"]
    print("E9  existing path queries identical to the untouched build: %d/%d" % (sum(b[q] == o["existing"].get(q) for q in b), len(b)))
print("==== Both runs\nE6  delivered prompts identical in both runs: %s" % ("yes" if len(prompts) == 2 and len(set(prompts.values())) == 1 else "NO"))
spec = git(EXP + "/nebula-speckit", "diff", "--numstat", "baseline", "HEAD", "--", "specs")
print("==== Spec Kit documents\nE10 specs/ lines: %d in %d files" % (sum(int(l.split("\t")[0]) for l in spec.splitlines()), len(spec.splitlines())))
print("==== Unit tests (Spec Kit's tests run against the plain build): see %s/review/plain-unit-test-run.txt" % EXP)
