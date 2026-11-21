# TinyChess V2 depth-3 node-budget experiment

## Decision under test

This experiment changes only engine/.probe/compact_v2_depth3.py. It does not modify approved engine/compact.py, bot/main.py, starter/main.py, or sealed files.

The one source-level change is the base budget selected by lim():

| Opponent | Experimental base |
|---|---:|
| depth-2 | 18,000 |
| depth-3 | 30,000 |
| depth-4 | 18,000 |
| nodes-* | 30,000 |

Ply throttling is unchanged: <=60 is 100%, 61-100 is 75%, and >100 is 50%. Legal move validation, alpha-beta, qsearch, mate handling, root fallback, and all evaluation/search code are unchanged.

Experimental source SHA-256: 1e702620bb6cfadf3856af96373895e94cb41b65cfec2598659c387197b9cb1f.

## Tactical-position validation

The preceding diagnostic harness was run against the experimental module.

| Position | Policy limit now | 18k result | 30k result | Interpretation |
|---|---:|---|---|---|
| T2/G2, depth-3, 53 pre-move plies | 30,000 | a6c4, completed depth 4, 18,000 nodes, depth 5 abort | h8h6, completed depth 5, 30,000 nodes, depth 6 abort | The target improvement is reproduced: extra completed iteration changes the move away from the recorded queen-for-rook line. |
| T2/G6, nodes-500k, 29 pre-move plies | 30,000 | g5g6, depth 4, 18,000, depth 5 abort | g5g6, depth 5, 30,000, depth 6 abort | Unchanged: nodes-* already had 30k. |
| T2/G3, depth-4, 72 pre-move plies | 13,500 | f3g4, depth 4, 9,252 | f3g4, depth 4, 9,252 | Unchanged: depth-4 remains 18k base then 75% throttle; mate is found early. |

T2/G2's selected move at 30k is not proof it wins the game: its completed-depth score remains -480. It is evidence that depth-3's prior 18k budget stopped before the iteration distinguishing it from a6c4. The policy addresses that measured horizon case only; it does not fix the checked-king survival problem in T2/G6 or the already-lost mate in T2/G3.

## Validation results

| Check | Result |
|---|---|
| Phase 1 suite | 48/48 passed (engine/test_engine.py), 51.556 seconds |
| Experimental compact suite | 27/27 passed (engine/.probe/v2_test_runner.py), 53.856 seconds |
| Compact perft cases | All included compact perft positions passed within the 27 tests |
| Policy branches | Passed: depth-2/depth-4/depth-other = 18k; depth-3 = 30k; all nodes-* = 30k; each at plies 60, 61, 100, 101 |
| Determinism | Passed compact test across PYTHONHASHSEED 0, 1, 42, and 12345 |
| Packed HTTP entrypoint | Passed under Python 3.13 -P -s using experimental packed file |
| Root fallback / low-node / qsearch cutoff / TT halfmove | Passed in compact suite |

The runner substitutes only the probe module for compact; its policy expectation is updated only in the runner, leaving engine/test_compact.py preserved.

## Official compression

Official compressor command:

    node cli/makefun.mjs compress engine/.probe/compact_v2_depth3.py --out engine/.probe/v2_depth3_packed.py

| Item | Value |
|---|---|
| Packed size | **3,879 bytes** |
| Target | <=3,900 bytes: passed |
| Hard cap | <=4,096 bytes: passed, 217 bytes headroom |
| Packed SHA-256 | 579112ed0ab1aabea7287aced57d6924473ed201c9d79eb0d3909ea071131ae0 |
| Compressor source size | 12,261 bytes |
| Compressor source SHA-256 | 1e702620bb6cfadf3856af96373895e94cb41b65cfec2598659c387197b9cb1f |

The policy expression costs 6 packed bytes versus the previously reported 3,873-byte approved artifact. No manual minification or truncation was used.

## Runtime estimate

The three extracted depth-3 games provide actual decision counts and response plies. Applying old and new throttled budgets to each TinyChess decision yields:

| Trial depth-3 game | TC decisions | Old scheduled nodes | New scheduled nodes | Additional nodes |
|---|---:|---:|---:|---:|
| T0/G2, 80 total plies | 36 | 603,000 | 1,005,000 | 402,000 |
| T1/G2, 150 total plies | 71 | 963,000 | 1,605,000 | 642,000 |
| T2/G2, 69 total plies | 30 | 522,000 | 870,000 | 348,000 |
| Mean depth-3 game | 45.7 | 696,000 | 1,160,000 | **464,000** |

The local compact test's 50,000-node worst-case search measured 1.92 seconds, about 26,000 nodes/second. Estimates use a conservative 20,000 nodes/second, allowing for slower remote machines and process overhead. The new budget adds 17.4-32.1 seconds per depth-3 game, mean 23.2 seconds.

A six-game practice containing one game per measured opponent tier has estimated added search time of 23 seconds (17-32 seconds from the three observed depth-3 lengths). For an eight-game final, exact opponent mix is unavailable. Scaling the six-game mix proportionally (8/6 depth-3 games) gives 31 seconds added time, range 23-43 seconds. One depth-3 final game uses the six-game estimate; two use mean 46 seconds, range 35-64 seconds.

These are search-time estimates, not wall-clock guarantees: mate can stop early, and HTTP/process overhead is excluded.

## Expected benefit and limitations

Expected benefit is narrow but concrete: depth-3 gets the completed depth-5 iteration that changes T2/G2 from a6c4 to h8h6. It may improve analogous depth-3 horizon decisions without changing depth-2, depth-4, or nodes-* policy.

Limitations:

- It improves no known nodes-* decision, because nodes-* already is 30k.
- It does not solve T2/G6, whose g5g6 remains current search's best non-mating line, or T2/G3, which is mate-lost.
- It does not establish aggregate Elo improvement; only a controlled remote replay can measure that.
- It retains the material/PST-only evaluation and non-capturing-check qsearch limitation.

No production source, bot, starter, sealed competition file, test, staged file, commit, push, or submission was changed. The experiment stops here for review.
