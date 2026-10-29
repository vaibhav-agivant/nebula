import sys, time, subprocess
sys.path.insert(0, "/work")
from txnlib import *
S = sess()
def ddl(q):
    for _ in range(40):
        if ok(S, q): return True
        time.sleep(2)
    return False
for e in ["road(cost double)", "ferry(cost double)", "neg(cost double)"]: ddl("CREATE EDGE IF NOT EXISTS " + e)
for e in ["road", "ferry", "neg"]:
    for _ in range(40):
        if ok(S, "DESCRIBE EDGE " + e): break
        time.sleep(2)
time.sleep(4)
E = {"road": [("a","f",50.0),("a","e",10.0),("e","f",10.0),("a","b",1.0),("b","c",1.0),("c","f",1.0),("b","d",7.0),("d","f",1.0)],
     "ferry": [("a","c",1.5)], "neg": [("n1","n2",1.0),("n2","n3",-5.0)]}
for v in sorted({x for es in E.values() for s,d,_ in es for x in (s,d)}): ddl('INSERT VERTEX person(name, age) VALUES "%s":("%s", 1)' % (v, v))
for t, es in E.items():
    for s, d, w in es: ddl('INSERT EDGE %s VALUES "%s"->"%s":(%r)' % (t, s, d, w))
time.sleep(2)
Q = [
 'FIND SHORTEST PATH FROM "a" TO "f" OVER road YIELD path AS p',
 'FIND WEIGHTED SHORTEST PATH FROM "a" TO "f" OVER road WEIGHT BY cost YIELD path AS p, cost AS c',
 'FIND WEIGHTED SHORTEST PATH FROM "a" TO "f" OVER road WEIGHT BY cost UPTO 2 STEPS YIELD path AS p, cost AS c',
 'FIND WEIGHTED SHORTEST PATH FROM "a" TO "f" OVER road, ferry WEIGHT BY cost YIELD path AS p, cost AS c',
 'FIND WEIGHTED SHORTEST PATH FROM "f" TO "a" OVER road WEIGHT BY cost REVERSELY YIELD path AS p, cost AS c',
 'FIND WEIGHTED SHORTEST PATH FROM "c" TO "d" OVER road WEIGHT BY cost BIDIRECT YIELD path AS p, cost AS c',
 'FIND WEIGHTED SHORTEST PATH FROM "a" TO "f" OVER road WEIGHT BY cost YIELD path AS p, cost AS c | YIELD $-.c AS total_cost',
 'FIND WEIGHTED SHORTEST PATH FROM "a" TO "f" OVER road WEIGHT BY nosuch YIELD path AS p, cost AS c',
 'FIND WEIGHTED SHORTEST PATH FROM "n1" TO "n3" OVER neg WEIGHT BY cost YIELD path AS p, cost AS c',
 'EXPLAIN FIND WEIGHTED SHORTEST PATH FROM "a" TO "f" OVER road WEIGHT BY cost YIELD path AS p, cost AS c',
]
C = ["/work/nebula-console", "-addr", "127.0.0.1", "-port", "9669", "-u", "root", "-p", "nebula", "-e"]
for q in Q:
    out = subprocess.run(C + ["USE tx; " + q], capture_output=True, text=True).stdout
    keep = [l for l in out.splitlines() if l.strip() and not l.startswith("Bye") and "CST" not in l and not l.startswith("(root@nebula)") and not l.startswith("Welcome")]
    print("QUERY>>", q); print("\n".join(keep)); print("<<END")