# InstaKill offline evaluation protocol

**Question.** We replay each eligible user's feed at one historical cut-off and ask how highly each of the four strategies ranks posts that user liked later. The reported measure is NDCG@10 over that user's complete future relevant set.

**Cut-off and snapshot.** Unless `--cutoff` is supplied, `T` is the timestamp at the 80th percentile of the database's likes, with stable timestamp/user/post ordering. We back up SQLite to a temporary file, then remove likes, posts and follows at or after `T`; user rows are retained only when a pre-cutoff like, post or follow proves the account was already known, and their `created_at` is normalized to that earliest evidence. All service reads use that snapshot and the replay clock is fixed at `T`. MovieLens follow rows are inserted by the seeder with the current time rather than historical event times, so these rows are removed and cannot reveal future state.

**Users.** A user is evaluated when they have at least three likes strictly before `T` and at least one later like on any post created before `T`. User groups use the count before `T`: new (<10), casual (10–49), regular (50–199), and power (200+).

**Candidates.** For `chronological`, `for_you` and `learned`, the candidate set and exclusions are exactly those produced by `PostService.get_feed`, which is also the service function called by `GET /feed`; only the database path, replay time and limit are supplied explicitly. `popularity` is computed offline as a global ordering by snapshot like count (then post ID), and is not added to the API.

**Relevance.** A relevant item is every post liked by the user at or after `T` that already existed before `T`, including a post authored by that user; the relevance definition follows the assignment. The service may exclude some such items from its candidates, in which case they cannot appear in the top 10. Multiple future likes contribute to one user's relevance set.

**Metric.** We compute binary NDCG@10: each relevant post at rank `i` contributes `1/log2(i+2)`, and the sum is divided by the ideal DCG for up to ten relevant posts. Every eligible user has at least one relevant post by definition; a relevant post omitted from a strategy's candidate set contributes no gain. Scores range from zero to one.

**Intervals.** Each strategy's mean and the difference `learned − best baseline` use 2,000 bootstrap resamples of users with replacement. The same sampled users are used for both sides of every difference (paired bootstrap), with a fixed seed; interval limits are the 2.5th and 97.5th percentiles. The best baseline is selected by mean within the overall set or slice. `wins`/`loses` require the interval to be wholly above/below zero; otherwise the result is `unclear`.

**Slices.** We report all four lab activity groups, counted strictly before `T`. Users are the resampling unit both overall and within each slice.

**Known limitations.** The learned model was trained on MovieLens ratings through the lab validation cut-off, so some of the replay's future likes may also have been present during training. In the current run, `like_model.npz` stores no training cutoff; therefore the overlap cannot be determined from the artifact, and the learned score may be optimistically biased.

MovieLens consists largely of older films with ratings recorded years later, unlike a social feed dominated by posts from recent days. These slices describe historical MovieLens behavior only; they cannot establish which strategy wins for fresh social posts, and the age/freshness behavior in particular may reverse on that population.

This replay differs from the lab's moment-based test: the lab hides one like among 99 random items at each moment, while this evaluation ranks the complete snapshot candidate set and treats every later like as relevant. The scores are not directly comparable.
