# Failures of `ocr_rules`

Each entry: document, whether it was flagged, and the fields that differ (predicted vs label).

- `cord-test-0000` FLAGGED: subtotal: 40000.0 vs 60000.0; items matched 0 of 1 labelled (0 predicted). Checks: Subtotal 40000 with tax 5455, service 0 and discount 0 gives 45455, but the total is 60000.
- `cord-test-0001` FLAGGED: total: None vs 91000.0; items matched 0 of 3 labelled (0 predicted). Checks: No total was found.
- `cord-test-0002` not flagged: total: 20000.0 vs 28000.0; subtotal: None vs 28000.0; items matched 0 of 2 labelled (0 predicted). Checks: no check failed
- `cord-test-0003` FLAGGED: total: None vs 11000.0; items matched 0 of 1 labelled (0 predicted). Checks: No total was found.
- `cord-test-0004` FLAGGED: total: None vs 174600.0; subtotal: None vs 194000.0; items matched 0 of 3 labelled (0 predicted). Checks: No total was found.
- `cord-test-0005` not flagged: subtotal: None vs 28182.0; tax: None vs 2818.0; items matched 0 of 1 labelled (0 predicted). Checks: no check failed
- `cord-test-0006` FLAGGED: total: 0.0 vs 46000.0; items matched 0 of 3 labelled (0 predicted). Checks: The total (0) is not a positive amount.
- `cord-test-0007` FLAGGED: total: None vs 111000.0; subtotal: None vs 100909.0; tax: None vs 10091.0; items matched 0 of 2 labelled (0 predicted). Checks: No total was found.
- `cord-test-0008` FLAGGED: total: None vs 50000.0; subtotal: None vs 45455.0; tax: None vs 4545.0; items matched 0 of 3 labelled (0 predicted). Checks: No total was found.
- `cord-test-0009` FLAGGED: subtotal: None vs 36000.0; items matched 0 of 1 labelled (0 predicted). Checks: No total was found.
- `cord-test-0010` FLAGGED: total: 47000.0 vs 17000.0; subtotal: 0.0 vs 17000.0; items matched 0 of 1 labelled (0 predicted). Checks: Subtotal 0 with tax 0, service 0 and discount 0 gives 0, but the total is 47000.
- `cord-test-0011` FLAGGED: total: None vs 230000.0; items matched 0 of 1 labelled (0 predicted). Checks: No total was found.
