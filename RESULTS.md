# Machina CLI End-to-End Test Results

## 1. `machina version < /dev/null`
```text
machina-cli v0.2.23
```

## 2. `machina config list < /dev/null`
```text
                                 Configuration                                  
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key                     ┃ Value                                              ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ api_url                 │ https://api.machina.gg                             │
│ client_api_url          │ https://machina-podcasts-machina-sports-podcast.o… │
│ default_organization_id │ 6876c6e319689bf880aa80b7                           │
│ default_project_id      │ 690d5c76ed71f2d5f9908108                           │
│ output_format           │ table                                              │
│ session_url             │ https://session.machina.gg                         │
└─────────────────────────┴────────────────────────────────────────────────────┘
```

## 3. `machina agent list < /dev/null`
```text
                                     Agents                                     
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃             ┃             ┃          ┃           ┃ Last        ┃             ┃
┃ Name        ┃ Title       ┃ Status   ┃ Scheduled ┃ Execution   ┃ ID          ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ adapters-d… │ Adapters -  │ inactive │    no     │             │ 69e02c71d9… │
│             │ Dataset     │          │           │             │             │
│             │ Pipeline    │          │           │             │             │
│ agent-test… │ Agent Test  │ inactive │    no     │             │ 69e02c71d9… │
│             │ Engine      │          │           │             │             │
│ assistant-… │ Assistant - │ inactive │    no     │             │ 69e0d89d6d… │
│             │ Chat        │          │           │             │             │
│             │ Executor    │          │           │             │             │
│ machina-as… │ Machina     │ inactive │    no     │             │ 69e0d8933d… │
│             │ Assistant - │          │           │             │             │
│             │ Chat        │          │           │             │             │
│             │ Executor    │          │           │             │             │
│ meme-agent  │ Meme Agent  │ active   │    no     │             │ 69e02de00e… │
│ personaliz… │ Personaliz… │ inactive │    no     │ Mon, 09 Feb │ 690d617a13… │
│             │ Podcast     │          │           │ 2026 19     │             │
│             │ Agent       │          │           │             │             │
│ podcast-di… │ Podcast     │ active   │    no     │ Thu, 16 Apr │ 69e0c2a865… │
│             │ Digest      │          │           │ 2026 15     │             │
│             │ Agent       │          │           │             │             │
│ social-med… │ Social      │ active   │    yes    │ Tue, 14 Apr │ 694b4fe21a… │
│             │ Media       │          │           │ 2026 09     │             │
│             │ Content     │          │           │             │             │
│             │ Generator   │          │           │             │             │
└─────────────┴─────────────┴──────────┴───────────┴─────────────┴─────────────┘
```

## 4. `machina agent run podcast-digest-agent query="Brasileirao futebol" --sync --json < /dev/null`
```text

  Running agent: podcast-digest-agent
  query=Brasileirao futebol

{
  "agent_run_id": "69e102daec1f7952e7867b36",
  "digest": "",
  "query": "Brasileirao futebol",
  "workflow-status": "failed"
}
```
