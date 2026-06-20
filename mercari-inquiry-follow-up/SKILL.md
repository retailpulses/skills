---
name: mercari-inquiry-follow-up
description: Review answered Mercari Shops inquiries and send proactive Japanese follow-up messages using the Inquiry Portal and the correct logged-in Mercari shop profile. Use when the user asks to follow up Mercari inquiries, re-contact prospective buyers, check whether a customer still plans to purchase, confirm stock before messaging, or promote a current time sale without making unsupported claims.
---

# Mercari Inquiry Follow-up

Turn previously answered Mercari Shops inquiries into careful, context-aware follow-ups that invite a purchase or clarify the customer's remaining need.

## Requirements

- Use the user's existing logged-in Chrome profiles and tabs.
- Use the Chrome control skill because shop authentication and profile state matter.
- Expect the Inquiry Portal at `https://inquiry-dashboard.pages.dev/` and Mercari Shops seller pages at `https://mercari-shops.com/seller/shops/...`.
- Do not expose customer names, shop IDs, conversation IDs, order IDs, or product codes in reports or reusable files.
- Sending a message is an external action. Draft and verify first; send only when the user's request authorizes sending.

## Workflow

1. Open the Inquiry Portal and select the `Answered` queue.
2. Choose an inquiry that merits a proactive follow-up. Read the full customer question, prior answer, inquiry date, product, shop, quantity, category, and any visible draft/status information.
3. Decide whether a follow-up is appropriate:
   - Follow up when the earlier reply answered a sales, shipping, bulk-purchase, availability, or delivery-timing question and the customer has not clearly declined.
   - Skip if the customer already purchased, the conversation is resolved without a sales opportunity, the message would be repetitive, or key facts cannot be verified.
4. Open the conversation link in the Chrome profile mapped to the inquiry's shop. Verify the Mercari shop and customer conversation match the portal record before composing anything.
5. When the message depends on availability, purchase status, or promotion:
   - Open the shop's `注文` page.
   - Search by product management code, product name, variant name, or order number.
   - Include relevant statuses such as `発送済み` when the default filter would hide completed orders.
   - Confirm the customer has not already purchased and that the exact product or variant remains available.
   - Confirm any time sale or urgency claim from the live listing or portal. Never infer scarcity from an old note.
6. In the Inquiry Portal drafting field, write a short instruction that states the follow-up goal and only verified facts. Use its copywriting action to create natural Japanese.
7. Review the generated Japanese before copying it. The message should:
   - thank the customer for the earlier inquiry;
   - refer naturally to the unresolved question or buying timeline;
   - mention verified stock, direct-purchase availability, delivery context, or a live promotion only when relevant;
   - invite questions without pressuring the customer;
   - end with `ホムブリスカスタマーサポート`.
8. Copy the final draft, return to the matching Mercari conversation, paste into `返信を入力する`, and re-check the recipient, product/variant, quantities, dates, prices, stock, and promotion claims.
9. If sending is authorized, click `送信` once. Verify the new message appears in the conversation and the portal status reflects the completed follow-up where available.
10. Continue with the next eligible inquiry. Keep shop/profile context isolated between cases.

## Message patterns

Use these as structures, not fixed scripts.

### Clarify need or delivery timing

```text
お問い合わせいただき、誠にありがとうございます。

先日ご案内した内容について、ご不明な点はございませんでしょうか。差し支えなければ、商品のご利用予定日をお知らせください。ご希望に沿ってご案内いたします。

何卒よろしくお願いいたします。

ホムブリスカスタマーサポート
```

### Verified stock or promotion follow-up

```text
お世話になっております。この度はお問い合わせいただき、誠にありがとうございます。

先日のお問い合わせについて、購入のご予定はお決まりでしょうか。現在、対象の【商品・種類】は在庫があり、直接ご購入いただけます。【確認済みの場合のみ：ただいまタイムセールを実施中です。】

ご不明な点がございましたら、お気軽にお問い合わせください。

ホムブリスカスタマーサポート
```

## Guardrails

- Do not send a follow-up based only on the card summary; read the conversation.
- Do not claim stock, last-unit status, sale pricing, delivery dates, or availability without a current check.
- Do not promise carrier delivery timing that the shop cannot control.
- Do not reuse text across customers without adapting the product, variant, and prior question.
- Do not message the wrong shop profile. If profile-to-shop mapping is unclear, stop before pasting or sending.
- Avoid manipulative urgency. Mention a sale or limited inventory factually and only while it is live.
- Never include internal drafting notes such as `proactively follow-up` in the customer-facing message.

## Completion report

Report only aggregate operational details: inquiries reviewed, messages sent, cases skipped, and concise skip reasons. Do not include private customer or order details.

## Example triggers

- "Follow up the answered Mercari inquiries."
- "Re-contact customers who asked about delivery but did not buy."
- "Check stock and send a polite Mercari follow-up."
- "Follow up inquiries while the item is on time sale."

