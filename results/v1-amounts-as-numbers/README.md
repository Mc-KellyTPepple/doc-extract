# First run (kept on purpose)

The first benchmark run used a prompt that asked the model for amounts as plain numbers. Receipts in CORD print
Indonesian rupiah with a thousands dot ("60.000"), and the model wrote that as the JSON number 60.0. In the 45 vision
receipts scored, 11 of the 15 wrong documents were this exact error: every field off by a factor of 1000. Because the whole
receipt was scaled together, the arithmetic still added up, so the validator could not flag them.

The prompt now asks for amounts as text exactly as printed, which the parser reads at the right scale. These files are
kept as evidence of the failure and are not the project's results. The current results are in `results/`.
