# Gift conversion into Stars (commission 1%)

OwpenGram already implements `payments.convertStarGift`. The store credits `saved.ConvertStars` and atomically marks the redeemed gift as converted. However, the connected GoGram catalog currently reports `convert_stars=0` on sampled catalog entries. A UI change alone cannot make gifts convert into Stars.

## Proposed database fix

Run `gift-conversion-1pct.sql` on the **actual OwpenGram PostgreSQL database**, not on iOS or GitHub Actions.

The script adjusts all revision conversion amounts and unconverted, non-unique gifted item snapshots, keeping gift purchase prices untouched. Fee is `ceil(stars / 100)` because Stars use integer amounts: a 15-Star gift becomes 14 Stars; 100 becomes 99; 250 becomes 247. The effective fee can exceed 1% for small values due to rounding, and costs 1 Star minimum. If exact fractional 1% is required, an integer Stars ledger cannot express it without a different smallest unit.

### Important limitations

- This is a **prepared patch, not yet deployed**. The attached gift-catalog connector supports price/sort changes but does **not** expose `convert_stars` or SSH/SQL access.
- The patch affects **previously received regular gifts** that have not been converted, as well as newly bought gifts. Gifts already converted or upgraded to unique assets are not re-credited.
- Apply only after a PostgreSQL backup and a short maintenance window; this intentionally changes historical catalog revision metadata in place. For permanent production policy, consider adding an audited admin operation that creates a fresh catalog revision for new gifts and a separate entitlement migration.
- This does not transfer real crypto, and does not alter GORAM.
- Correct the previously reported GoGram login-code leak before opening the service to real users.
