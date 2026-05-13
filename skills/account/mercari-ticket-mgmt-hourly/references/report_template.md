# Hourly Report Template

Use this format at the end of every run.

```md
# Mercari Ticket Mgmt Report

- run_at: YYYY-MM-DD HH:mm JST
- batch_window: YYYY-MM-DD HH:mm to YYYY-MM-DD HH:mm JST
- scope_status: 未返信
- processed_count: 0
- greeting_only_count: 0
- historical_greeting_only_matches: 0
- real_ticket_count: 0
- suspicious_count: 0
- tickets_created: 0
- tickets_updated: 0
- replies_drafted: 0
- replies_sent: 0

## Greeting-Only Messages

- none

## Replies Sent

- none

## Notes

- no new messages found
- completed or canceled threads, if any, are reported only as historical matches
```

When there are greeting-only messages, include one bullet per message:

```md
- transaction_id: ...
  message_id: ...
  source_text: ...
  reply_text: ...
```

Keep the report short and factual.
