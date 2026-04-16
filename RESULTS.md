# Results

## 1. `machina version < /dev/null`
**Stdout:**
```text
machina-cli v0.2.23
```

## 2. `machina config list < /dev/null`
**Stdout:**
```text
                     Configuration                      
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key                     ┃ Value                      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ api_url                 │ https://api.machina.gg     │
│ default_organization_id │ <empty>                    │
│ default_project_id      │ <empty>                    │
│ output_format           │ table                      │
│ session_url             │ https://session.machina.gg │
└─────────────────────────┴────────────────────────────┘
```

## 3. `cat ~/.machina/credentials.json`
*(No output / empty file)*

## 4. `machina agent list < /dev/null`
**Stderr:**
```text
No project selected. Run `machina project use <id>` first.
```

## 5. `machina agent run podcast-digest-agent query="Brasileirao" --sync --json < /dev/null`
**Stderr:**
```text
No project selected. Run `machina project use <id>` first.
```
