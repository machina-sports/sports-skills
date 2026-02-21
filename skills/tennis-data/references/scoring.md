# Reading Match Scores

Tennis scores are reported as set scores. Example response:
```json
{
  "competitors": [
    {"name": "Carlos Alcaraz", "seed": 1, "set_scores": [6, 3, 7], "winner": true},
    {"name": "Novak Djokovic", "seed": 2, "set_scores": [4, 6, 5], "winner": false}
  ],
  "result": "(1) Carlos Alcaraz (ESP) bt (2) Novak Djokovic (SRB) 6-4 3-6 7-5"
}
```
This means Alcaraz won 6-4, 3-6, 7-5 (won first set, lost second, won third).

# Understanding Tournament Draws

The `draws` array in scoreboard results contains match groupings:
- **Men's Singles** / **Women's Singles**: Individual matches
- **Men's Doubles** / **Women's Doubles**: Pairs matches

Each match has a `round` field: "Qualifying 1st Round", "Round 1", "Round of 16", "Quarterfinal", "Semifinal", "Final".
