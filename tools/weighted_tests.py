import sys, time; sys.path.insert(0, "/work")
from txnlib import *
S = sess()
def ddl(q):
    for _ in range(40):
        if ok(S, q): return True
        time.sleep(2)
    return False
for e in ["road(cost double)", "ferry(cost double)", "toll(w int)", "neg(cost double)", "label(name string)"]:
    ddl("CREATE EDGE IF NOT EXISTS " + e)
for e in ["road", "ferry", "toll", "neg", "label"]:
    for _ in range(40):
        if ok(S, "DESCRIBE EDGE " + e): break
        time.sleep(2)
time.sleep(4)
E = {"road": [("a","f",50.0),("a","e",10.0),("e","f",10.0),("a","b",1.0),("b","c",1.0),("c","f",1.0),("b","d",7.0),("d","f",1.0),
              ("t1","t2",1.0),("t2","t4",1.0),("t1","t3",1.0),("t3","t4",1.0)],
     "ferry": [("a","c",1.5)], "toll": [("p","q",2),("q","r",3),("p","r",10)], "neg": [("n1","n2",-1.0)], "label": [("l1","l2","x")]}
vids = sorted({v for es in E.values() for s, d, _ in es for v in (s, d)})
for v in vids: assert ddl('INSERT VERTEX person(name, age) VALUES "%s":("%s", 1)' % (v, v)), "seed vertex " + v
for t, es in E.items():
    for s, d, w in es:
        wv = ('"%s"' % w) if isinstance(w, str) else repr(w)
        assert ddl('INSERT EDGE %s VALUES "%s"->"%s":(%s)' % (t, s, d, wv)), "seed edge"
time.sleep(2)

def num(v): return v.as_int() if v.is_int() else v.as_double()
def wsp(q):
    """returns None on error, [] if empty, else (vids, cost)"""
    r = sess().execute(q)
    if not r.is_succeeded(): return None
    if r.row_size() == 0: return []
    row = r.row_values(0)
    return ([n.get_id().as_string() for n in row[0].as_path().nodes()], num(row[1]))
def near(x, y): return x is not None and abs(x - y) < 1e-9
def is_(res, vids, cost): return res not in (None, []) and res[0] == vids and near(res[1], cost)
Q = "FIND WEIGHTED SHORTEST PATH FROM \"%s\" TO \"%s\" OVER %s WEIGHT BY %s %s YIELD path AS p, cost AS c"
def q(s, d, over="road", w="cost", opt=""): return Q % (s, d, over, w, opt)
def err(query):
    r = sess().execute(query); return (not r.is_succeeded()) and len(r.error_msg()) > 0 and "SyntaxError" not in r.error_msg()
def tie():
    r = wsp(q("t1", "t4")); return r not in (None, []) and near(r[1], 2.0) and len(r[0]) == 3 and r[0][0] == "t1" and r[0][-1] == "t4"
def pipe():
    r = sess().execute(q("a", "f") + " | YIELD $-.c AS cost")
    return r.is_succeeded() and r.row_size() == 1 and near(num(r.row_values(0)[0]), 3.0)
def old_sp():
    r = sess().execute('FIND SHORTEST PATH FROM "a" TO "f" OVER road YIELD path AS p')
    return r.is_succeeded() and r.row_size() == 1 and [n.get_id().as_string() for n in r.row_values(0)[0].as_path().nodes()] == ["a","f"]
def old_all():
    r = sess().execute('FIND ALL PATH FROM "a" TO "f" OVER road UPTO 3 STEPS YIELD path AS p')
    return r.is_succeeded() and r.row_size() == 4
run([("1 core","W1","cheapest path beats fewest hops: a->f = a,b,c,f cost 3.0", lambda: is_(wsp(q("a","f")), ["a","b","c","f"], 3.0)),
     ("1 core","W2","UPTO 2 STEPS excludes the 3-hop path: a,e,f cost 20.0", lambda: is_(wsp(q("a","f",opt="UPTO 2 STEPS")), ["a","e","f"], 20.0)),
     ("1 core","W3","UPTO 1 STEPS: direct a,f cost 50.0", lambda: is_(wsp(q("a","f",opt="UPTO 1 STEPS")), ["a","f"], 50.0)),
     ("1 core","W4","unreachable (f -> a, forward) returns empty, no error", lambda: wsp(q("f","a")) == []),
     ("1 core","W5","tie on cost: correct cost 2.0 and valid 2-edge path", tie),
     ("2 directions","W6","REVERSELY f -> a = f,c,b,a cost 3.0", lambda: is_(wsp(q("f","a",opt="REVERSELY")), ["f","c","b","a"], 3.0)),
     ("2 directions","W7","forward-only c -> d is empty", lambda: wsp(q("c","d")) == []),
     ("2 directions","W8","BIDIRECT c -> d = c,f,d cost 2.0", lambda: is_(wsp(q("c","d",opt="BIDIRECT")), ["c","f","d"], 2.0)),
     ("3 edge/weight types","W9","two edge types (road, ferry): a,c,f cost 2.5", lambda: is_(wsp(q("a","f",over="road, ferry")), ["a","c","f"], 2.5)),
     ("3 edge/weight types","W10","integer weight: p,q,r cost 5", lambda: is_(wsp(q("p","r",over="toll",w="w")), ["p","q","r"], 5)),
     ("4 integration","W11","works in a pipe: | YIELD $-.c -> 3.0", pipe),
     ("4 integration","R1","existing FIND SHORTEST PATH unchanged (a,f)", old_sp),
     ("4 integration","R2","existing FIND ALL PATH unchanged (4 paths)", old_all),
     ("4 integration","R3","nonexistent vertex returns empty, no error", lambda: wsp(q("zzz","a")) == []),
     ("5 errors","E1","negative weight -> clear error", lambda: err(q("n1","n2",over="neg"))),
     ("5 errors","E2","unknown weight property -> clear error", lambda: err(q("a","f",w="nosuch"))),
     ("5 errors","E3","non-numeric weight property -> clear error", lambda: err(q("l1","l2",over="label",w="name")))], "WEIGHTED")