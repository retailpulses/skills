# Mercari time-sale CSV DOM map

Derived from a successful download and file-selection recording on 2026-06-22. Shop IDs and filenames must always come from runtime input.

## Upload landing page

Route: `/seller/shops/{shopId}/dualprice/upload`

| Purpose | Stable evidence |
|---|---|
| Page heading | `タイムセールを一括設定する` |
| Registration download | Link `未設定の商品データを作成` |
| Existing-sale download | Link `設定済みの商品データを作成` |
| Upload section | Text `②CSVファイルをアップロード` |
| File selection | Button `ファイルを選択` backed by a file input |
| History columns | `ファイル名`, `エラーファイル` |
| History states | `エラー`, `設定完了`, or button `設定を再開する` |
| Error-file action | Button `ダウンロード` scoped to the failed row |

Selecting a file closes the native picker, but that alone is not upload verification. The exact basename must appear in the history table.

## Registration download page

Route: `/seller/shops/{shopId}/dualprice/products/download`

| Purpose | Stable evidence |
|---|---|
| Heading | `タイムセール設定可能な商品データ（CSV）を作成する` |
| Generate | Button `作成` |
| Optional median-price scope | Checkbox containing `過去価格(中央値)のタイムセールを含める` |
| History | Heading `CSVファイル作成履歴` |
| Ready status | `完了` |
| Download | Button `ダウンロード` inside the completed row |

The recorded page states a maximum of 10,000 generated products and that files older than 30 days are removed from history.

## Existing-sale download page

Route: `/seller/shops/{shopId}/dualprice/existing_products/download`

Use the same create-history-download pattern, but treat the output as an update/end CSV rather than a new-registration CSV.

