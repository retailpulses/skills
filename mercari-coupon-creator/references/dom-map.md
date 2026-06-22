# Mercari Shops coupon DOM map

This map comes from a successful recorded product-coupon creation on 2026-06-20. Use semantic text and roles; element numbers from the recording are intentionally omitted.

## Routes

- Coupon list: `/seller/shops/{shopId}/coupon`
- Create form: `/seller/shops/{shopId}/coupon/create`
- Product chooser: `/seller/shops/{shopId}/coupon/create/products`
- Successful product-coupon list: `/seller/shops/{shopId}/coupon?state=STATE_NOT_STARTED&scope=SCOPE_PRODUCT`

## Create form

| Purpose | Stable evidence |
|---|---|
| Distribution target | Disabled popup `フォロワー` |
| Scope | Popup/select initially `選択してください`; choose `商品単位` |
| Add products | Popup `商品を追加する`, then item/link `商品を選択` |
| Discount type | Popup/select initially `未選択` |
| Fixed amount | Option `割引金額(￥〇〇割引)` |
| Percentage | Option `割引率(〇〇%OFF)` |
| Discount value | Text input placeholder `￥0` after choosing a type |
| Issue count | Text input placeholder `0枚`; observed default `100枚` |
| One use per buyer | Checkbox following text `1人1回制限の設定` |
| Start | First `input[type=date]` / date picker after `クーポン開始日時`, followed by a time select |
| End | Second `input[type=date]` / date picker after `クーポン終了日時`, followed by a time select |
| Review action | Button `クーポンを設定する` |
| Confirmation dialog | Text `クーポンを設定しますか？`; buttons `設定する` and `閉じる` |

## Product chooser

| Purpose | Stable evidence |
|---|---|
| Search | Text input placeholder `商品管理コード（前方一致）、商品名検索` |
| Search submission | Enter key or button named `search`; URL gains `?keyword={code}` |
| Product selection | Result checkboxes; selected counter becomes `( 1/1000 )` for one item |
| Add selection | Button `選択した商品を追加する` |
| Added verification | Create form text `{n}点の商品を追加済み` |

The product search is prefix-based. Exact input can still return ambiguous results, so automation must not blindly select the first checkbox when multiple candidates remain.

## Success evidence

- Toast/text: `クーポンの発行が完了しました`
- URL query: `state=STATE_NOT_STARTED&scope=SCOPE_PRODUCT`
- Coupon card description includes the discount, product, scheduled period, and remaining count such as `残り枚数: 10/10枚`.

