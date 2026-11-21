# InstaKill offline evaluation

## Mean NDCG@10 by strategy

| Strategy | Mean | 95% user bootstrap interval | Users |
|---|---:|---:|---:|
| chronological | 0.0000 | [0.0000, 0.0000] | 6 |
| popularity | 0.1208 | [0.0110, 0.2472] | 6 |
| for_you | 0.1208 | [0.0110, 0.2606] | 6 |
| learned | 0.1279 | [0.0110, 0.2580] | 6 |

## learned minus best baseline

| Slice | Best baseline | Mean difference | 95% paired interval | Users | Verdict |
|---|---|---:|---:|---:|---|
| overall | popularity | 0.0071 | [-0.0507, 0.0720] | 6 | unclear |
| new (<10 likes) | popularity | 0.1441 | [0.1441, 0.1441] | 1 | wins |
| casual (10-49) | popularity | -0.0338 | [-0.1014, 0.0000] | 3 | unclear |
| regular (50-199) | popularity | 0.0000 | [0.0000, 0.0000] | 2 | unclear |
| power (200+) | N/A | N/A | N/A | 0 | not estimable |

## Run metadata

- Cut-off (UTC): `2009-07-10T22:03:24Z`
- Bootstrap seed: `42` (2,000 paired user resamples)
- Evaluated users: `6`
- Database SHA-256: `ab4afb1bc1b02c13561493a34c6b8a9c11856dab92c771cd29c7fb3d5e5a41f6`
- Evaluation code commit: `eae815a5c14775a80e78b87f7bcec3c3441a4894`
- Future relevant likes for evaluated users: `32`
- Model training cutoff: `not stored in like_model.npz`
- Source database: `200` users, `2000` posts
- Snapshot posts before T: `1976`
