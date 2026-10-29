import sys, time, subprocess
sys.path.insert(0, "/work")
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config
import json
NAME = sys.argv[1]; BASELINE = "--baseline" in sys.argv
cfg = Config(); cfg.max_connection_pool_size = 10; cfg.timeout = 0
pool = ConnectionPool(); assert pool.init([("127.0.0.1", 9669)], cfg)
def sess():
    s = pool.get_session("root", "nebula"); assert s.execute("USE tx").is_succeeded(); return s
S = sess()
def ddl(q):
    for _ in range(40):
        if S.execute(q).is_succeeded(): return True
        time.sleep(2)
    return False
def num(v): return v.as_int() if v.is_int() else (v.as_double() if v.is_double() else None)
def wsp(q):
    try:
        r = sess().execute(q)
    except Exception as e: return ("CRASH?", str(e)[:100])
    if not r.is_succeeded(): return ("ERR", r.error_msg()[:140])
    if r.row_size() == 0: return ("EMPTY",)
    row = r.row_values(0); return ("OK", [n.get_id().as_string() for n in row[0].as_path().nodes()], num(row[1]))
for e in ["ro(w int)", "rm(Weight int)", "rc(w int)"]: assert ddl("CREATE EDGE IF NOT EXISTS " + e), e
for e in ["ro", "rm", "rc"]:
    for _ in range(40):
        if S.execute("DESCRIBE EDGE " + e).is_succeeded(): break
        time.sleep(2)
time.sleep(5)
def vins(vs): assert ddl("INSERT VERTEX person(name, age) VALUES " + ",".join('"%s":("%s",1)' % (v, v) for v in vs))
vins(["oa", "ob", "oc", "m1", "m2", "c1", "c2"])
assert ddl('INSERT EDGE ro(w) VALUES "oa"->"oc"@0:(5), "oa"->"ob"@0:(9000000000000000000), "ob"->"oc"@0:(9000000000000000000)')
assert ddl('INSERT EDGE rm(Weight) VALUES "m1"->"m2"@0:(3)')
out = {"name": NAME, "baseline": BASELINE}; probes = []
def probe(pid, desc, ok, detail): probes.append({"id": pid, "desc": desc, "pass": bool(ok), "detail": str(detail)[:200]}); print("[%s] %s %s" % ("PASS" if ok else "FAIL", pid, desc), "|", str(detail)[:120], flush=True)
# existing behaviour that must survive (also run on the untouched baseline)
r = S.execute('GO FROM "m1" OVER rm YIELD properties(edge).Weight AS w')
probe("K1", "EXISTING: property named Weight (mixed case) still readable via properties(edge).Weight", r.is_succeeded() and r.row_size() == 1, r.error_msg() if not r.is_succeeded() else "")
r = S.execute('FETCH PROP ON rm "m1"->"m2" YIELD properties(edge).Weight AS w')
probe("K2", "EXISTING: FETCH PROP of mixed-case Weight property", r.is_succeeded() and r.row_size() == 1, r.error_msg() if not r.is_succeeded() else "")
if not BASELINE:
    r = wsp('FIND WEIGHTED SHORTEST PATH FROM "m1" TO "m2" OVER rm WEIGHT BY Weight YIELD path AS p, cost AS c')
    probe("K3", "WEIGHT BY with a mixed-case property name (Weight) works", r[0] == "OK" and r[2] == 3, r)
    r = wsp('FIND WEIGHTED SHORTEST PATH FROM "nope" TO "nope" OVER ro WEIGHT BY w YIELD path AS p, cost AS c')
    probe("K4", "src == dst on a NONEXISTENT vertex -> empty (requirement 6)", r[0] == "EMPTY", r)
    r = wsp('FIND WEIGHTED SHORTEST PATH FROM "oa" TO "oa" OVER ro WEIGHT BY w YIELD path AS p, cost AS c')
    out["src_eq_dst_existing"] = str(r)[:160]
    h0 = S.execute("YIELD 1 AS x").is_succeeded()
    r = wsp('FIND WEIGHTED SHORTEST PATH FROM "oa" TO "oc" OVER ro WEIGHT BY w YIELD path AS p, cost AS c')
    alive = False
    try: alive = sess().execute("YIELD 1 AS x").is_succeeded()
    except Exception as e: alive = False
    probe("K5", "int64 overflow on a longer path must not change the answer: expect cost 5 (path oa,oc); graphd must stay up", r[0] == "OK" and r[2] == 5 and alive, "result=%s graphd_alive_after=%s" % (r, alive))
    out["crashed_by_overflow"] = (not alive)
out["probes"] = probes
json.dump(out, open("/review/out2-%s.json" % NAME, "w"), indent=1)
print("DONE", NAME)