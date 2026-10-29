import sys, os, json, time, random, threading, re, subprocess
sys.path.insert(0, "/work")
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config
NAME = sys.argv[1]; BASELINE = "--baseline" in sys.argv
cfg = Config(); cfg.max_connection_pool_size = 30; cfg.timeout = 0
pool = ConnectionPool(); assert pool.init([("127.0.0.1", 9669)], cfg)
def sess():
    s = pool.get_session("root", "nebula"); r = s.execute("USE tx"); assert r.is_succeeded(), r.error_msg(); return s
S = sess()
def ddl(q):
    for _ in range(40):
        if S.execute(q).is_succeeded(): return True
        time.sleep(2)
    return False
def timed(fn, secs=60):
    box = {}
    def w():
        try: box["v"] = fn()
        except Exception as e: box["e"] = str(e)[:100]
    t = threading.Thread(target=w, daemon=True); t.start(); t.join(secs)
    if t.is_alive(): return "TIMEOUT"
    return box.get("v", "EXC:" + box.get("e", ""))
for e in ["ra(w int)", "rb(w double)", "rn(w int)", "rs(w string)", "rp(w int)"]: assert ddl("CREATE EDGE IF NOT EXISTS " + e), e
assert ddl("CREATE TAG IF NOT EXISTS weighted(weight int, cost int)")
for e in ["ra", "rb", "rn", "rs", "rp"]:
    for _ in range(40):
        if S.execute("DESCRIBE EDGE " + e).is_succeeded(): break
        time.sleep(2)
time.sleep(5)
random.seed(42)
V = ["v%d" % i for i in range(40)]
def insert_edges(etype, edges, wfmt):
    for i in range(0, len(edges), 40):
        vals = ",".join('"%s"->"%s"@%d:(%s)' % (u, v, r, wfmt(w)) for u, v, r, w in edges[i:i+40])
        assert ddl("INSERT EDGE %s(w) VALUES %s" % (etype, vals)), "insert " + etype
def vins(vs):
    for i in range(0, len(vs), 40):
        assert ddl("INSERT VERTEX person(name, age) VALUES " + ",".join('"%s":("%s",1)' % (v, v) for v in vs[i:i+40]))
vins(V)
def rand_edges(n, wgen):
    seen, out = set(), []
    while len(out) < n:
        u, v = random.choice(V), random.choice(V)
        r = random.choice([0, 0, 0, 1, 2])
        if (u, v, r) in seen: continue
        seen.add((u, v, r)); out.append((u, v, r, wgen()))
    return out
EA = rand_edges(130, lambda: 0 if random.random() < 0.1 else random.randint(1, 20))
EB = rand_edges(80, lambda: random.choice([0.25, 0.5, 0.75, 1.0, 1.5, 2.25, 4.0, 0.1, 0.2, 3.3]))
insert_edges("ra", EA, str); insert_edges("rb", EB, repr)
EDGES = {"ra": EA, "rb": EB}
out = {"name": NAME, "baseline": BASELINE}

def num(v): return v.as_int() if v.is_int() else (v.as_double() if v.is_double() else None)
def run_wsp(q):
    r = sess().execute(q)
    if not r.is_succeeded(): return ("ERR", r.error_msg()[:150])
    if r.row_size() == 0: return ("EMPTY",)
    row = r.row_values(0)
    return ("OK", [n.get_id().as_string() for n in row[0].as_path().nodes()], num(row[1]), r.row_size())
def Q(s, t, over, opt): return 'FIND WEIGHTED SHORTEST PATH FROM "%s" TO "%s" OVER %s WEIGHT BY w %s YIELD path AS p, cost AS c' % (s, t, ",".join(over), opt)
def oracle(over, direction, s, t, k):
    adj = {}
    for ty in over:
        for u, v, r, w in EDGES[ty]:
            if direction in ("fwd", "bi"): adj.setdefault(u, []).append((v, w))
            if direction in ("rev", "bi"): adj.setdefault(v, []).append((u, w))
    best = {s: 0}
    for _ in range(k):
        new = dict(best)
        for u, c in best.items():
            for v, w in adj.get(u, []):
                if c + w < new.get(v, 1e18): new[v] = c + w
        if new == best: break
        best = new
    return best.get(t)
def path_cost(over, direction, nodes):
    tot = 0
    for a, b in zip(nodes, nodes[1:]):
        c = []
        for ty in over:
            for u, v, r, w in EDGES[ty]:
                if direction in ("fwd", "bi") and u == a and v == b: c.append(w)
                if direction in ("rev", "bi") and u == b and v == a: c.append(w)
        if not c: return None
        tot += min(c)
    return tot

if not BASELINE:
    # ---- 1. oracle differential
    kinds = {"missing": [], "spurious": [], "wrong_cost": [], "bad_path": [], "error": [], "timeout": []}
    total = 0; correct = 0
    combos = [(["ra"]), (["rb"]), (["ra", "rb"])]
    for i in range(150):
        over = random.choice(combos); direction = random.choice(["fwd", "rev", "bi"]); k = random.choice([None, 1, 2, 3, 5])
        s, t = random.sample(V, 2)
        opt = {"fwd": "", "rev": "REVERSELY", "bi": "BIDIRECT"}[direction] + ("" if k is None else " UPTO %d STEPS" % k)
        exp = oracle(over, direction, s, t, k if k else len(V))
        res = timed(lambda: run_wsp(Q(s, t, over, opt)), 60); total += 1
        tag = "%s %s->%s over %s %s" % (direction, s, t, "+".join(over), "" if k is None else "UPTO %d" % k)
        if res == "TIMEOUT": kinds["timeout"].append(tag); continue
        if isinstance(res, str): kinds["error"].append(tag + " " + res); continue
        if res[0] == "ERR": kinds["error"].append(tag + " " + res[1]); continue
        if exp is None:
            (kinds["spurious"].append(tag + " got " + str(res[1:3])) if res[0] == "OK" else None)
            if res[0] == "EMPTY": correct += 1
            continue
        if res[0] == "EMPTY": kinds["missing"].append(tag + " expected cost %s" % exp); continue
        if res[2] is None: kinds["wrong_cost"].append(tag + " NULL cost returned, expected %s" % exp); continue
        if abs(res[2] - exp) > 1e-6: kinds["wrong_cost"].append(tag + " got %s expected %s" % (res[2], exp)); continue
        pc = path_cost(over, direction, res[1])
        if pc is None or abs(pc - exp) > 1e-6 or (k and len(res[1]) - 1 > k) or res[1][0] != s or res[1][-1] != t:
            kinds["bad_path"].append(tag + " path %s cost %s expected %s pathcost %s" % (res[1], res[2], exp, pc)); continue
        correct += 1
    out["oracle"] = {"total": total, "correct": correct, **{k: len(v) for k, v in kinds.items()}, "examples": {k: v[:3] for k, v in kinds.items() if v}}
    # ---- 2. edge-case probes
    probes = []
    def probe(pid, desc, ok, detail=""): probes.append({"id": pid, "desc": desc, "pass": bool(ok), "detail": str(detail)[:200]})
    def add(etype, es, wfmt=str):
        vins(sorted({x for u, v, _, _ in es for x in (u, v)})); insert_edges(etype, es, wfmt); EDGES.setdefault(etype, []).extend(es)
    add("ra", [("z1", "z2", 0, 0), ("z2", "z1", 0, 0), ("z2", "z3", 0, 0), ("z1", "z3", 0, 5)])
    r = run_wsp(Q("z1", "z3", ["ra"], "")); probe("P1", "zero-weight cycle: cost 0 via z1,z2,z3 and terminates", r[0] == "OK" and r[2] == 0, r)
    add("ra", [("q1", "q2", 0, 9), ("q1", "q2", 1, 2), ("q1", "q2", 2, 5)])
    r = run_wsp(Q("q1", "q2", ["ra"], "")); probe("P2", "parallel edges (3 ranks): picks cheapest (2)", r[0] == "OK" and r[2] == 2, r)
    add("ra", [("s1", "s1", 0, 1), ("s1", "s2", 0, 4)])
    r = run_wsp(Q("s1", "s2", ["ra"], "")); probe("P3", "self-loop on the way: cost 4, path s1,s2", r[0] == "OK" and r[2] == 4 and r[1] == ["s1", "s2"], r)
    add("rn", [("n1", "n2", 0, 1), ("n2", "n3", 0, -5), ("n1", "n3", 0, 10)])
    r = run_wsp(Q("n1", "n3", ["rn"], "")); probe("P4", "negative weight on reachable edge -> clear error (not a syntax error)", r[0] == "ERR" and "SyntaxError" not in r[1], r)
    add("rn", [("m1", "m2", 0, 3), ("m8", "m9", 0, -1)])
    r = run_wsp(Q("m1", "m2", ["rn"], "")); probe("P5", "negative edge NOT reachable from source: still answers cost 3 (desirable, not required)", r[0] == "OK" and r[2] == 3, r)
    r = run_wsp(Q("v3", "v3", ["ra"], "")); probe("P6", "src == dst returns something sensible, no crash (record behavior)", r[0] in ("OK", "EMPTY"), r)
    out["src_eq_dst"] = str(r)[:200]
    r = run_wsp(Q("v3", "nonexistent", ["ra"], "")); probe("P7", "unknown destination -> empty, not error", r[0] == "EMPTY", r)
    r = run_wsp(Q("nonexistent", "v3", ["ra"], "")); probe("P8", "unknown source -> empty, not error", r[0] == "EMPTY", r)
    add("ra", [("o1", "o2", 0, 9223372036854775000), ("o2", "o3", 0, 9223372036854775000)])
    r = run_wsp(Q("o1", "o3", ["ra"], "")); probe("P9", "int64 overflow in sum is NOT silently wrong (error, or correct value)", r[0] == "ERR" or (r[0] == "OK" and r[2] is not None and r[2] > 0), r)
    add("rb", [("d1", "d2", 0, 0.1), ("d2", "d3", 0, 0.2)], repr)
    r = run_wsp(Q("d1", "d3", ["rb"], "")); probe("P10", "double sum 0.1+0.2 ~ 0.3", r[0] == "OK" and r[2] is not None and abs(r[2] - 0.3) < 1e-9, r)
    r = run_wsp(Q("v1", "v9", ["ra"], "UPTO 1000 STEPS")); probe("P11", "huge UPTO value is accepted and terminates", r[0] in ("OK", "EMPTY"), r)
    r = run_wsp(Q("v1", "v9", ["ra"], "UPTO 0 STEPS")); probe("P12", "UPTO 0 STEPS: error or empty, no crash (record behavior)", r[0] in ("ERR", "EMPTY"), r)
    r = run_wsp('find weighted shortest path from "z1" to "z3" over ra weight by w yield path as p, cost as c'); probe("P13", "lower-case keywords parse", r[0] == "OK", r)
    r = run_wsp('FIND WEIGHTED SHORTEST PATH FROM "z1" TO "z3" OVER ra WEIGHT BY `w` YIELD path AS p, cost AS c'); probe("P14", "backquoted property name parses", r[0] == "OK", r)
    r = run_wsp(Q("z1", "z3", ["ra"], "").replace("YIELD path AS p, cost AS c", "YIELD path AS p, cost AS c | LIMIT 1")); probe("P15", "pipe into LIMIT works", r[0] in ("OK", "EMPTY"), r)
    add("rs", [("w1", "w2", 0, "x")], lambda w: '"%s"' % w)
    r = run_wsp('FIND WEIGHTED SHORTEST PATH FROM "w1" TO "w2" OVER rs WEIGHT BY w YIELD path AS p, cost AS c'); probe("P16", "string weight -> clear non-syntax error", r[0] == "ERR" and "SyntaxError" not in r[1], r)
    r = run_wsp(Q("v1", "v2", ["ra", "nosuchedge"], "")); probe("P17", "unknown edge type -> error", r[0] == "ERR", r)
    ok1 = S.execute('INSERT VERTEX weighted(weight, cost) VALUES "kw1":(1, 2)').is_succeeded()
    r2 = S.execute('FETCH PROP ON weighted "kw1" YIELD properties(vertex).weight AS cost, properties(vertex).cost AS weighted'); probe("P18", "words WEIGHT/WEIGHTED/COST still usable as tag, property and alias names", ok1 and r2.is_succeeded() and r2.row_size() == 1, r2.error_msg() if not r2.is_succeeded() else "")
    out["probes"] = probes
# ---- 3. existing-query differential (same data in baseline and implementation)
EX = ['FIND SHORTEST PATH FROM "v0" TO "v7" OVER ra YIELD path AS p', 'FIND SHORTEST PATH FROM "v1" TO "v9" OVER ra BIDIRECT YIELD path AS p',
      'FIND SHORTEST PATH FROM "v2" TO "v11" OVER ra REVERSELY UPTO 3 STEPS YIELD path AS p', 'FIND SHORTEST PATH WITH PROP FROM "v0" TO "v7" OVER ra YIELD path AS p',
      'FIND SHORTEST PATH FROM "v0","v1" TO "v7","v9" OVER * YIELD path AS p', 'FIND ALL PATH FROM "v0" TO "v7" OVER ra UPTO 2 STEPS YIELD path AS p',
      'FIND ALL PATH FROM "v3" TO "v5" OVER rb UPTO 3 STEPS YIELD path AS p', 'FIND NOLOOP PATH FROM "v0" TO "v7" OVER ra UPTO 3 STEPS YIELD path AS p',
      'FIND NOLOOP PATH FROM "v4" TO "v8" OVER ra,rb BIDIRECT UPTO 2 STEPS YIELD path AS p',
      'GO FROM "v0" OVER ra YIELD dst(edge) AS id | FIND SHORTEST PATH FROM $-.id TO "v7" OVER ra YIELD path AS p',
      'FIND SHORTEST PATH FROM "v5" TO "v6" OVER ra YIELD path AS p | YIELD count(*) AS n', 'FIND ALL PATH FROM "v1" TO "v2" OVER ra,rb UPTO 2 STEPS WHERE rb.w > 0.2 YIELD path AS p']
ex = {}
for q in EX:
    r = sess().execute(q)
    ex[q] = ("ERR " + r.error_msg()[:60]) if not r.is_succeeded() else sorted(str(r.row_values(i)[0]) for i in range(r.row_size()))
out["existing"] = ex
# ---- 4. scale probe (latency)
PV = ["p%d" % i for i in range(3000)]
vins(PV)
pe = []; seen = set()
while len(pe) < 15000:
    u, v = random.choice(PV), random.choice(PV)
    if (u, v) in seen: continue
    seen.add((u, v)); pe.append((u, v, 0, random.randint(1, 100)))
for i in range(0, len(pe), 150):
    vals = ",".join('"%s"->"%s"@0:(%d)' % (e[0], e[1], e[3]) for e in pe[i:i+150])
    assert ddl("INSERT EDGE rp(w) VALUES " + vals)
time.sleep(2)
perf = []
for i in range(5):
    s, t = random.sample(PV, 2)
    for label, q in [("old FIND SHORTEST PATH", 'FIND SHORTEST PATH FROM "%s" TO "%s" OVER rp YIELD path AS p' % (s, t))] + ([] if BASELINE else [("weighted unbounded", Q(s, t, ["rp"], "").replace("WEIGHT BY w", "WEIGHT BY w")), ("weighted UPTO 4", Q(s, t, ["rp"], "UPTO 4 STEPS"))]):
        t0 = time.time(); res = timed(lambda: (lambda r: (r.is_succeeded(), r.row_size()))(sess().execute(q)), 120); dt = time.time() - t0
        perf.append({"q": label, "ms": round(dt * 1000), "res": str(res)})
out["perf"] = perf
# ---- 5. health
h = S.execute("YIELD 1 AS x").is_succeeded()
logs = subprocess.run("grep -l -E 'Check failed|SIGSEGV|Segmentation|terminate called|Aborted' /work/run/graph/logs/* 2>/dev/null | head -3; pgrep -f nebula-graphd | wc -l", shell=True, capture_output=True, text=True).stdout.split()
out["health"] = {"graphd_answers": h, "graphd_processes": logs[-1] if logs else "?", "crash_logs": [l for l in logs[:-1]]}
json.dump(out, open("/review/out-%s.json" % NAME, "w"), indent=1, default=str)
print("DONE", NAME)