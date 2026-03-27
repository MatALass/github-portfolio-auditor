# Portfolio Decision Rules

## Principle

Portfolio decisions are not just score buckets.
They combine:

- repository score
- delivery blockers
- repository hygiene
- documentation readiness
- narrative value for public visibility

## FEATURE_NOW

Use when all of the following are true:

- the repository score is already high enough to feature
- no major blockers are present
- the repository is not merely an archive-grade artifact

This is the recommendation for repositories that can safely represent the portfolio today.

## KEEP_AND_IMPROVE

Use when:

- the repository is already credible
- there is real engineering value
- targeted fixes would significantly strengthen presentation
- no severe delivery failure makes public visibility unsafe

This is a visible-but-not-finished state.

## MERGE_OR_REPOSITION

Use when:

- the repository has useful substance
- but is not sufficiently differentiated or complete on its own
- or is better treated as part of a broader project narrative

This is the right bucket for overlap, weak differentiation, or projects that need reframing.

## ARCHIVE_PUBLIC

Use when:

- the repository is below current feature quality
- but it still has documentary or narrative value
- README exists
- no severe hygiene failure is present
- keeping it public is unlikely to damage the portfolio narrative

This is not a featured state.
It is a public archive state.

## MAKE_PRIVATE

Use when:

- the repository is weak enough to hurt overall portfolio quality
- severe hygiene or delivery failures are present
- or there is not enough narrative value to justify public visibility

This is the safest default for repositories that are currently more harmful than helpful.
