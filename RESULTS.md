# Machina CLI Test Results

## 1. `machina version < /dev/null`
```text
machina-cli v0.2.23
```

## 2. `machina config list < /dev/null`
```text
                     Configuration                      
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key                     ┃ Value                      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ api_url                 │ https://api.machina.gg     │
│ default_organization_id │ 6876c6e319689bf880aa80b7   │
│ default_project_id      │ machina-factory-demo       │
│ output_format           │ table                      │
│ session_url             │ https://session.machina.gg │
└─────────────────────────┴────────────────────────────┘
```

## 3. `machina agent list --json < /dev/null`
```text
Missing permission
```
*(Note: Output depends on API token validity and project permissions)*

## 4. `machina agent run podcast-digest-agent query="Champions League" --sync --json < /dev/null`
```text
Missing permission
```
*(Note: Output depends on API token validity and project permissions)*
