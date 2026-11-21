-- GoGram / OwpenGram: gift -> Stars with a 1% commission.
-- RUN ONCE on the actual OwpenGram PostgreSQL database after a backup.
-- Formula (integer Stars): fee = ceil(price / 100); payout = price - fee.
-- Examples: 15 -> 14, 50 -> 49, 100 -> 99, 250 -> 247.
-- The fee is never credited to a user; it remains withheld by the system.
-- This is not a GORAM/GRAM conversion or blockchain action.
-- Changes only regular gift conversion quotations; does not touch Stars balances.
--
-- IMPORTANT: This adjusts current catalog revision values in place, and existing
-- non-converted, non-unique saved gift snapshots. Run only if you accept that
-- the new conversion policy also affects previously received regular gifts.
-- A long-term release should add an admin endpoint that produces new revisions.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

-- Preserve every changed row for auditing / manual rollback.
CREATE TABLE IF NOT EXISTS public.gogram_conversion_fee_backup_catalog_20261121 (
    revision_id bigint PRIMARY KEY,
    old_convert_stars bigint NOT NULL,
    saved_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.gogram_conversion_fee_backup_saved_20261121 (
    saved_id bigint PRIMARY KEY,
    old_convert_stars bigint NOT NULL,
    saved_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.gogram_conversion_fee_backup_catalog_20261121 (revision_id, old_convert_stars)
SELECT id, convert_stars
FROM public.star_gift_catalog_revisions
WHERE convert_stars <> greatest(0::bigint, stars - (stars / 100 + CASE WHEN stars % 100 <> 0 THEN 1 ELSE 0 END))
ON CONFLICT (revision_id) DO NOTHING;

-- Preserve already redeemed gifts (not eligible for conversion).
INSERT INTO public.gogram_conversion_fee_backup_saved_20261121 (saved_id, old_convert_stars)
SELECT p.id, p.convert_stars
FROM public.peer_star_gifts p
JOIN public.star_gift_catalog_revisions r ON r.id = p.catalog_revision_id
WHERE NOT p.converted
  AND COALESCE(p.unique_gift_id, 0) = 0
  AND p.convert_stars <> greatest(0::bigint, r.stars - (r.stars / 100 + CASE WHEN r.stars % 100 <> 0 THEN 1 ELSE 0 END))
ON CONFLICT (saved_id) DO NOTHING;

-- Every catalog revision gets the 1% rule, including gifts from older revisions.
-- Do NOT alter price, animation, gift ID, issuance, or purchased ownership.
UPDATE public.star_gift_catalog_revisions
SET convert_stars = greatest(0::bigint, stars - (stars / 100 + CASE WHEN stars % 100 <> 0 THEN 1 ELSE 0 END))
WHERE convert_stars <> greatest(0::bigint, stars - (stars / 100 + CASE WHEN stars % 100 <> 0 THEN 1 ELSE 0 END));

-- Gift entitlements snapshot the conversion amount when issued.
-- Update unredeemed regular gift snapshots so previous owners can convert too.
UPDATE public.peer_star_gifts p
SET convert_stars = greatest(0::bigint, r.stars - (r.stars / 100 + CASE WHEN r.stars % 100 <> 0 THEN 1 ELSE 0 END))
FROM public.star_gift_catalog_revisions r
WHERE p.catalog_revision_id = r.id
  AND NOT p.converted
  AND COALESCE(p.unique_gift_id, 0) = 0
  AND p.convert_stars <> greatest(0::bigint, r.stars - (r.stars / 100 + CASE WHEN r.stars % 100 <> 0 THEN 1 ELSE 0 END));

-- Trigger the catalog read-model refresh on the root table when catalog revisions change.
UPDATE public.star_gift_catalog SET updated_at=now();

COMMIT;

SELECT c.gift_id, r.stars, r.convert_stars,
       r.stars - r.convert_stars AS commission_stars
FROM public.star_gift_catalog c
JOIN public.star_gift_catalog_revisions r ON r.id=c.active_revision_id
ORDER BY c.sort_order, c.gift_id
LIMIT 20;
