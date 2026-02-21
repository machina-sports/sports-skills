# NFL Team IDs (ESPN)

| Team | ID | Team | ID |
|------|-----|------|-----|
| Cardinals | 22 | Rams | 14 |
| Falcons | 1 | Ravens | 33 |
| Bills | 2 | Bears | 3 |
| Panthers | 29 | Bengals | 4 |
| Cowboys | 6 | Browns | 5 |
| Broncos | 7 | Lions | 8 |
| Packers | 9 | Texans | 34 |
| Colts | 11 | Jaguars | 30 |
| Chiefs | 12 | Raiders | 13 |
| Chargers | 24 | Dolphins | 15 |
| Vikings | 16 | Patriots | 17 |
| Saints | 18 | Giants | 19 |
| Jets | 20 | Eagles | 21 |
| Steelers | 23 | 49ers | 25 |
| Seahawks | 26 | Buccaneers | 27 |
| Titans | 10 | Commanders | 28 |

**Tip:** Use `get_teams` to get the full, accurate list of team IDs.

## Week Numbering

- **Regular season**: Weeks 1-18
- **Postseason**: Wild Card = 19, Divisional = 20, Conference Championship = 21, Pro Bowl = 22, Super Bowl = 23
- The connector translates these to ESPN's internal `seasontype=3` automatically.
- `get_team_schedule` returns both regular-season and postseason games.
