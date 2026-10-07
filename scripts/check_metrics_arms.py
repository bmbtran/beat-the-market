"""M8 check 1: reports/metrics.json has every PLAN §12 arm with bootstrap CIs and n_test=200."""
import json
from mf.eval.arms import ALL_ARMS
m = json.load(open("reports/metrics.json", encoding="utf-8"))
missing = [a for a in ALL_ARMS if a not in m["arms"]]
noci = [a for a in ALL_ARMS if "brier_ci" not in m["arms"][a]]
print("arms:", len(m["arms"]), "missing:", missing, "without CI:", noci, "n_test_scored:", m["n_test_scored"])
assert not missing and not noci and m["n_test_scored"] == 200
print("CHECK1 OK")
