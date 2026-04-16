# Machina CLI Test Results

## 1. `machina version`
```
machina-cli v0.2.23
```

## 2. `machina config list`
```
                     Configuration                      
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key                     ┃ Value                      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ api_url                 │ https://api.machina.gg     │
│ default_organization_id │ 6876c6e319689bf880aa80b7   │
│ default_project_id      │ <empty>                    │
│ output_format           │ table                      │
│ session_url             │ https://session.machina.gg │
└─────────────────────────┴────────────────────────────┘
```

## 3. `machina agent list --json`
```
No project selected. Run `machina project use <id>` first.
```

## 4. `machina workflow run podcast-digest-workflow query="Champions League" --sync --json`
```
No project selected. Run `machina project use <id>` first.
```
