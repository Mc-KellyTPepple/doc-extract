# Failures of `verified`

Each entry: document, whether it was flagged, and the fields that differ (predicted vs label).

- `cord-test-0012` FLAGGED: items matched 0 of 2 labelled (2 predicted). Checks: '1002-0060 SHOPPING BAG': 1 x 880 is 880, but the line says 0.
- `cord-test-0013` not flagged: subtotal: 46636.0 vs 4663646636.0; items matched 2 of 2 labelled (2 predicted). Checks: no check failed
- `cord-test-0014` FLAGGED: items matched 5 of 6 labelled (6 predicted). Checks: The line items add up to 235000 but the subtotal is 238000.
- `cord-test-0017` not flagged: items matched 6 of 6 labelled (7 predicted). Checks: no check failed
- `cord-test-0026` FLAGGED: items matched 2 of 3 labelled (3 predicted). Checks: 'Teh Tawar': 2 x 4000 is 8000, but the line says 0.; The line items add up to 130000 but the subtotal is 138000.
- `cord-test-0037` not flagged: items matched 1 of 1 labelled (1 predicted). Checks: no check failed
- `cord-test-0039` not flagged: items matched 3 of 3 labelled (3 predicted). Checks: no check failed
- `cord-test-0041` FLAGGED: items matched 6 of 10 labelled (10 predicted). Checks: The line items add up to 333333 but the subtotal is 316017.; Subtotal 316017 with tax 0, service 49982.7 and discount 0 gives 366000, but the total is 365000.
- `cord-test-0042` not flagged: tax: None vs 1500.0; items matched 1 of 1 labelled (1 predicted). Checks: no check failed
- `cord-test-0043` not flagged: items matched 1 of 3 labelled (1 predicted). Checks: no check failed
- `cord-test-0046` not flagged: items matched 2 of 4 labelled (2 predicted). Checks: no check failed
- `cord-test-0048` FLAGGED: tax: None vs 2272.0; items matched 1 of 3 labelled (1 predicted). Checks: Subtotal 22728 with tax 0, service 0 and discount 2272 gives 20456, but the total is 25000.
