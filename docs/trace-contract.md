# Witnessed identifier equivalence

TwinProof compares complete ordered observations while allowing explicitly
declared fresh IDs to differ. It uses no model, network connection or automatic
timestamp/UUID masks. Clock values and ordinary text stay exact.

```sh
python3 -m pip install .
twinproof trace examples/trace/reference.json examples/trace/candidate.json examples/trace/contract.json
# PASS, exit 0
twinproof trace examples/trace/reference.json examples/trace/corrupt.json examples/trace/contract.json
# FAIL, exit 1: a later reference no longer points to the created object
```

Both traces contain an `initial` JSON value and an ordered `steps` array. A step
can contain `result`, `state`, request arguments and other observable information.
Everything included is compared. The initial observation is always exact.

The caller supplies a separate trusted contract:

```json
{
  "namespaces": {
    "item": {
      "values": ["/result/id", "/state/items/*/id", "/state/selected"],
      "keys": ["/state/items"]
    }
  },
  "bindings": [
    {"step": 0, "namespace": "item", "expected": "ref-1",
     "observed": "cand-1", "path": "/result/id"}
  ]
}
```

`values` marks identifier-valued locations; `keys` marks dictionaries keyed by
identifiers. Patterns use JSON Pointer escaping (`~1` for `/`, `~0` for `~`), with
`*` matching exactly one path segment. Role patterns may not overlap within a
role kind. Literal `*` segments cannot be distinguished from wildcards in role
patterns. Bindings use exact paths, without wildcard expansion.

At the declared creation step, both result paths must contain the declared
string IDs. Each ID must be fresh in its namespace: it cannot appear in the
initial ID roles, a preceding step, or an earlier binding. Subsequent references
and dictionary keys must respect the same one-to-one correspondence. A wrong
unbound ID cannot pass merely because its text equals the reference's ID.

The contract is an assumption, not evidence of user intent. A result ID could
actually be an existing external object unknown to this trace. Trusted adapters
must declare only real creation events and all relevant identifier roles; do not
accept contracts from the candidate being evaluated. There is no automatic
creation inference, active probing, general graph matching or concurrency model.

PASS certifies only equality of the recorded observations under that contract.
It does not establish unobserved behavior, a correct reference implementation,
the truth of the contract or semantic equivalence of entire programs. FAIL
identifies an observed difference. UNKNOWN rejects malformed/contradictory
contracts or unsupported JSON. Difference paths address the normalized trace;
bound IDs are represented by namespaced tokens in those diagnostics.

For exact comparison without identifier alignment, use
`twinproof compare expected.json observed.json`. Both commands preserve decimal
tokens exactly, distinguish bool/number and missing/null, preserve array order,
and reject duplicate JSON keys and nonfinite values.
