# Rollback Procedure

## create-multi Mode (New Listing, No Existing Listings Touched)

**No rollback needed.** The new multi-variant product is a fresh listing. Existing standalone listings for sibling SKUs remain untouched.

If the new product was created in error:
```bash
# Set status to DRAFT (hides it from search without deleting)
ssh -i ~/.ssh/id_ed25519 root@160.251.141.110 \
  "export MERCARI_ACCESS_TOKEN=\$MERCARI_SHOP{N}_TOKEN; \
   curl -4 -sS -X POST 'https://api.mercari-shops.com/v1/graphql' \
   -H 'Authorization: Bearer \$MERCARI_ACCESS_TOKEN' \
   -H 'Content-Type: application/json' \
   -d '{\"query\":\"mutation{updateProduct(input:{id:\\\"PRODUCT_ID\\\",status:DRAFT}){product{id status}}}\"}'"
```

## standalone Mode (Single-SKU Listing)

Same as above — just set the new product to DRAFT status. No other listings affected.

## Future: Delete & Recreate Scenario

If a future update adds support for modifying existing products (e.g., consolidating standalone listings into one multi-variant product by deleting old ones and recreating), the rollback requires:

1. **Full snapshot saved before any deletion** (JSON with all product fields + variant list)
2. **If createProduct fails after delete**: recreate the old product from snapshot using the same `createProduct` mutation
3. **Update Supabase** to point back to the restored product ID

This is NOT currently implemented. Do not attempt without explicit user approval and a verified snapshot.
