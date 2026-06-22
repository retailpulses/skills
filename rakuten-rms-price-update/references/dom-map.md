# Rakuten RMS price-edit DOM map

Derived from a successful RMS price update recorded on 2026-06-20. Identifiers below are structural examples; do not embed the recorded shop, product, or price in automation.

## Routes

- Product list: `https://item.rms.rakuten.co.jp/rms-sku/shops/{shopId}/items`
- Edit page: `https://item.rms.rakuten.co.jp/rms-sku/shops/{shopId}/item/edit/{managementNumber}`
- Price tab fragment: `#tab-1`
- Completion: `/rms-sku/shops/{shopId}/item/edit/{managementNumber}/complete`

## Product list

| Purpose | Stable evidence |
|---|---|
| Search input | Placeholder `キーワード` |
| Search action | Button `検索` |
| Search URL | `type=keywordSearch`, `inventoryOutOfStock=INCLUDED-SKU`, and `keyword={value}` |
| Result identity | Exact listing text plus `商品管理番号`/management number within the same result container |
| Edit action | Link `編集` inside that verified result container |

There may be many `編集` links. Never use the first global match; scope it to the uniquely verified result container.

## Edit form

| Purpose | Stable evidence |
|---|---|
| Page identity | Heading `商品編集` |
| Management number | Text following `商品管理番号（商品URL）` |
| Price section | Link `販売・価格`, URL fragment `#tab-1` |
| Target price | Text `通常購入販売価格`, followed by the associated editable text/number input |
| Tax treatment | Radio buttons `税込` and `税別`; select `税込` by default |
| Save | Button `更新する` |

The target field had no useful accessible name in the recording. Locate it from the `通常購入販売価格` label and its nearest field container, not by a page-wide input index.

## Completion and verification

| Purpose | Stable evidence |
|---|---|
| Completion heading | `商品編集完了` |
| Completion message | `商品情報の編集が完了しました。` |
| Listing identity | `商品管理番号 ：` followed by the expected management number |
| Return to form | Button `商品情報を編集` |
| Optional public links | `商品ページを見る(PC)` and `商品ページを見る(スマートフォン)`; not required for RMS verification |

The recorded workflow reopened the RMS edit form and confirmed the saved field. This read-after-write check is preferred over relying on a potentially cached public product page.
