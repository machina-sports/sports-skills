$ machina config list < /dev/null
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

$ machina agent list < /dev/null
╭───────────────────── Traceback (most recent call last) ──────────────────────╮
│ /usr/local/lib/python3.11/dist-packages/machina_cli/commands/agent.py:28 in  │
│ list_agents                                                                  │
│                                                                              │
│    25 │   json_output: bool = typer.Option(False, "--json", "-j", help="Outp │
│    26 ):                                                                     │
│    27 │   """List agents in the current project."""                          │
│ ❱  28 │   client = ProjectClient(project_id)                                 │
│    29 │   result = client.post("agent/search", {                             │
│    30 │   │   "filters": {},                                                 │
│    31 │   │   "page": page,                                                  │
│                                                                              │
│ /usr/local/lib/python3.11/dist-packages/machina_cli/project_client.py:113 in │
│ __init__                                                                     │
│                                                                              │
│   110 │   │   │   console.print("[red]No project selected. Run `machina proj │
│   111 │   │   │   raise SystemExit(1)                                        │
│   112 │   │                                                                  │
│ ❱ 113 │   │   session = _get_project_session(self.project_id)                │
│   114 │   │   self.api_url = session["api_url"].rstrip("/")                  │
│   115 │   │   self.project_token = session["token"]                          │
│   116                                                                        │
│                                                                              │
│ /usr/local/lib/python3.11/dist-packages/machina_cli/project_client.py:46 in  │
│ _get_project_session                                                         │
│                                                                              │
│    43 │   │   return _project_cache[project_id]                              │
│    44 │                                                                      │
│    45 │   # Check if we have a stored project token                          │
│ ❱  46 │   stored = get_credential(f"project_token_{project_id}")             │
│    47 │   if stored:                                                         │
│    48 │   │   # Decode JWT to get the api URL (without verification)         │
│    49 │   │   import json                                                    │
│                                                                              │
│ /usr/local/lib/python3.11/dist-packages/machina_cli/config.py:75 in          │
│ get_credential                                                               │
│                                                                              │
│    72                                                                        │
│    73 def get_credential(key: str) -> Optional[str]:                         │
│    74 │   """Retrieve a credential from ~/.machina/credentials.json."""      │
│ ❱  75 │   return _load_creds().get(key)                                      │
│    76                                                                        │
│    77                                                                        │
│    78 def _clear_credential(key: str):                                       │
│                                                                              │
│ /usr/local/lib/python3.11/dist-packages/machina_cli/config.py:55 in          │
│ _load_creds                                                                  │
│                                                                              │
│    52 │   ensure_config_dir()                                                │
│    53 │   if CREDS_FILE.exists():                                            │
│    54 │   │   with open(CREDS_FILE) as f:                                    │
│ ❱  55 │   │   │   return json.load(f)                                        │
│    56 │   return {}                                                          │
│    57                                                                        │
│    58                                                                        │
│                                                                              │
│ /usr/lib/python3.11/json/__init__.py:293 in load                             │
│                                                                              │
│   290 │   To use a custom ``JSONDecoder`` subclass, specify it with the ``cl │
│   291 │   kwarg; otherwise ``JSONDecoder`` is used.                          │
│   292 │   """                                                                │
│ ❱ 293 │   return loads(fp.read(),                                            │
│   294 │   │   cls=cls, object_hook=object_hook,                              │
│   295 │   │   parse_float=parse_float, parse_int=parse_int,                  │
│   296 │   │   parse_constant=parse_constant, object_pairs_hook=object_pairs_ │
│                                                                              │
│ /usr/lib/python3.11/json/__init__.py:346 in loads                            │
│                                                                              │
│   343 │   if (cls is None and object_hook is None and                        │
│   344 │   │   │   parse_int is None and parse_float is None and              │
│   345 │   │   │   parse_constant is None and object_pairs_hook is None and n │
│ ❱ 346 │   │   return _default_decoder.decode(s)                              │
│   347 │   if cls is None:                                                    │
│   348 │   │   cls = JSONDecoder                                              │
│   349 │   if object_hook is not None:                                        │
│                                                                              │
│ /usr/lib/python3.11/json/decoder.py:340 in decode                            │
│                                                                              │
│   337 │   │   obj, end = self.raw_decode(s, idx=_w(s, 0).end())              │
│   338 │   │   end = _w(s, end).end()                                         │
│   339 │   │   if end != len(s):                                              │
│ ❱ 340 │   │   │   raise JSONDecodeError("Extra data", s, end)                │
│   341 │   │   return obj                                                     │
│   342 │                                                                      │
│   343 │   def raw_decode(self, s, idx=0):                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
JSONDecodeError: Extra data: line 4 column 1 (char 106)

$ machina agent run podcast-digest-agent query="Brasileirao futebol" --sync --json < /dev/null
╭───────────────────── Traceback (most recent call last) ──────────────────────╮
│ /usr/local/lib/python3.11/dist-packages/machina_cli/commands/agent.py:181 in │
│ run_agent                                                                    │
│                                                                              │
│   178 │   │   machina agent run my-agent --sync                              │
│   179 │   │   machina agent run my-agent force-competitors=true season_id=sr │
│   180 │   """                                                                │
│ ❱ 181 │   client = ProjectClient(project_id)                                 │
│   182 │                                                                      │
│   183 │   # Fetch agent to get available context-agent inputs                │
│   184 │   try:                                                               │
│                                                                              │
│ /usr/local/lib/python3.11/dist-packages/machina_cli/project_client.py:113 in │
│ __init__                                                                     │
│                                                                              │
│   110 │   │   │   console.print("[red]No project selected. Run `machina proj │
│   111 │   │   │   raise SystemExit(1)                                        │
│   112 │   │                                                                  │
│ ❱ 113 │   │   session = _get_project_session(self.project_id)                │
│   114 │   │   self.api_url = session["api_url"].rstrip("/")                  │
│   115 │   │   self.project_token = session["token"]                          │
│   116                                                                        │
│                                                                              │
│ /usr/local/lib/python3.11/dist-packages/machina_cli/project_client.py:46 in  │
│ _get_project_session                                                         │
│                                                                              │
│    43 │   │   return _project_cache[project_id]                              │
│    44 │                                                                      │
│    45 │   # Check if we have a stored project token                          │
│ ❱  46 │   stored = get_credential(f"project_token_{project_id}")             │
│    47 │   if stored:                                                         │
│    48 │   │   # Decode JWT to get the api URL (without verification)         │
│    49 │   │   import json                                                    │
│                                                                              │
│ /usr/local/lib/python3.11/dist-packages/machina_cli/config.py:75 in          │
│ get_credential                                                               │
│                                                                              │
│    72                                                                        │
│    73 def get_credential(key: str) -> Optional[str]:                         │
│    74 │   """Retrieve a credential from ~/.machina/credentials.json."""      │
│ ❱  75 │   return _load_creds().get(key)                                      │
│    76                                                                        │
│    77                                                                        │
│    78 def _clear_credential(key: str):                                       │
│                                                                              │
│ /usr/local/lib/python3.11/dist-packages/machina_cli/config.py:55 in          │
│ _load_creds                                                                  │
│                                                                              │
│    52 │   ensure_config_dir()                                                │
│    53 │   if CREDS_FILE.exists():                                            │
│    54 │   │   with open(CREDS_FILE) as f:                                    │
│ ❱  55 │   │   │   return json.load(f)                                        │
│    56 │   return {}                                                          │
│    57                                                                        │
│    58                                                                        │
│                                                                              │
│ /usr/lib/python3.11/json/__init__.py:293 in load                             │
│                                                                              │
│   290 │   To use a custom ``JSONDecoder`` subclass, specify it with the ``cl │
│   291 │   kwarg; otherwise ``JSONDecoder`` is used.                          │
│   292 │   """                                                                │
│ ❱ 293 │   return loads(fp.read(),                                            │
│   294 │   │   cls=cls, object_hook=object_hook,                              │
│   295 │   │   parse_float=parse_float, parse_int=parse_int,                  │
│   296 │   │   parse_constant=parse_constant, object_pairs_hook=object_pairs_ │
│                                                                              │
│ /usr/lib/python3.11/json/__init__.py:346 in loads                            │
│                                                                              │
│   343 │   if (cls is None and object_hook is None and                        │
│   344 │   │   │   parse_int is None and parse_float is None and              │
│   345 │   │   │   parse_constant is None and object_pairs_hook is None and n │
│ ❱ 346 │   │   return _default_decoder.decode(s)                              │
│   347 │   if cls is None:                                                    │
│   348 │   │   cls = JSONDecoder                                              │
│   349 │   if object_hook is not None:                                        │
│                                                                              │
│ /usr/lib/python3.11/json/decoder.py:340 in decode                            │
│                                                                              │
│   337 │   │   obj, end = self.raw_decode(s, idx=_w(s, 0).end())              │
│   338 │   │   end = _w(s, end).end()                                         │
│   339 │   │   if end != len(s):                                              │
│ ❱ 340 │   │   │   raise JSONDecodeError("Extra data", s, end)                │
│   341 │   │   return obj                                                     │
│   342 │                                                                      │
│   343 │   def raw_decode(self, s, idx=0):                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
JSONDecodeError: Extra data: line 4 column 1 (char 106)
