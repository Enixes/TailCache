# Original campaign: conditional results and exclusions

These are the original audit’s point ratios and direction classifications. They are not fresh paired ratios, and an unresolved endpoint must not be classified from its point estimate alone. The original unconditional protocol remains NO_GO. Full condition limitations are retained in [the JSON](original-campaign-summary.json).

| Recorder | Payload (B) | Ballast (MiB) | Complete comparison | No conditional quality limitation | p99 Ch/C | p99.9 Ch/C | p99 direction | p99.9 direction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sample | 256 | 0 | True | False | 1.283 | 1.157 | unresolved | unresolved |
| sample | 256 | 96 | True | True | 1.239 | 1.083 | caffeine-lower | unresolved |
| sample | 256 | 208 | True | False | 1.227 | 0.933 | unresolved | unresolved |
| sample | 256 | 288 | True | False | 1.227 | 0.709 | unresolved | unresolved |
| sample | 4096 | 0 | True | True | 1.125 | 1.354 | caffeine-lower | caffeine-lower |
| sample | 4096 | 96 | False | False | missing | missing |  |  |
| sample | 4096 | 208 | True | False | 1.127 | 1.341 | unresolved | unresolved |
| sample | 4096 | 288 | True | False | 1.121 | 1.370 | unresolved | unresolved |
| every-operation | 256 | 0 | True | True | 1.090 | 0.479 | unresolved | chronicle-lower |
| every-operation | 256 | 96 | True | True | 1.179 | 0.495 | caffeine-lower | chronicle-lower |
| every-operation | 256 | 208 | True | True | 1.163 | 0.539 | caffeine-lower | chronicle-lower |
| every-operation | 256 | 288 | True | False | 0.906 | 0.521 | unresolved | unresolved |
| every-operation | 4096 | 0 | True | True | 1.110 | 1.298 | caffeine-lower | caffeine-lower |
| every-operation | 4096 | 96 | True | True | 1.111 | 1.321 | caffeine-lower | caffeine-lower |
| every-operation | 4096 | 208 | True | True | 1.124 | 1.348 | caffeine-lower | caffeine-lower |
| every-operation | 4096 | 288 | True | False | 1.114 | 1.328 | unresolved | unresolved |
