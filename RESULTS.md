========================================
1. machina version < /dev/null
========================================
machina-cli v0.2.23

========================================
2. machina config list < /dev/null
========================================
                     Configuration                      
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key                     ┃ Value                      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ api_url                 │ https://api.machina.gg     │
│ default_organization_id │ 6876c6e319689bf880aa80b7   │
│ default_project_id      │ 690d5c76ed71f2d5f9908108   │
│ output_format           │ table                      │
│ session_url             │ https://session.machina.gg │
└─────────────────────────┴────────────────────────────┘

========================================
3. cat ~/.machina/credentials.json
========================================
{
  "api_key": "pzYlGOQX5bRpcLh8OhMoU2hm-YwDKZ0I7exQejnVefOQlZsvTi7lXZLD6BUS7wOEDSDR5r5rVpPNXzLufbpRDQ"
}
========================================
4. machina agent list < /dev/null
========================================
Missing permission

========================================
5. machina agent run podcast-digest-agent query="Brasileirao" --sync --json < /dev/null
========================================
Missing permission
