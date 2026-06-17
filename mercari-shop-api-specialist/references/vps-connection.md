# VPS Connection Details

## SSH Defaults

- Host: `root@160.251.141.110`
- Key: `~/.ssh/id_ed25519`
- Canonical command:

  ```bash
  ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@160.251.141.110
  ```

- Force IPv4 for all Mercari production requests.

## Egress IP

- Fixed IPv4: `160.251.141.110`
- Verify with:

  ```bash
  curl -4 -fsS https://ifconfig.me
  ```

## API Base URL

```
https://api.mercari-shops.com/v1/graphql
```

## User-Agent

Use `User-Agent: Inhouse_ERP/<VERSION>` for all API requests.
