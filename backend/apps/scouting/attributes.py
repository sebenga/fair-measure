"""The scouting attribute catalogue, as data: areas, attributes, physical tests and
match stats per sport.

Every sport rates the same five areas on a 1 to 10 scale. Universal attributes
apply to every sport; each sport adds its own (optionally only for some
positions), its physical tests and the match stats the engine can calculate.

A match stat either reads the engine (`source`: a score type key recorded by
the sport's presets, or one of ENGINE_SOURCES) or is a `formula` over the sport's
other stats and the BUILTINS. Nothing in the scouting code branches on a sport.
"""

from __future__ import annotations

SCALE = {"min": 1, "max": 10}

AREAS: list[dict] = [
    {
        "key": "physical",
        "label": "Physical",
        "description": "What the body can do: speed, power, stamina and movement.",
        "anchors": {
            "2": "Clearly behind others in the age group; it limits what they can do in a game.",
            "5": "Typical for the age group and level; neither a strength nor a weakness.",
            "8": "Stands out at this level; regularly wins physical contests.",
            "10": "Exceptional; would stand out a level or two higher.",
        },
    },
    {
        "key": "technical",
        "label": "Technical",
        "description": "Sport-specific skills and how cleanly they are performed under pressure.",
        "anchors": {
            "2": "The skill often breaks down, even without pressure.",
            "5": "Reliable when there is time and space; less so under pressure.",
            "8": "Clean and repeatable under pressure; a clear strength.",
            "10": "Elite execution; does things others at this level cannot.",
        },
    },
    {
        "key": "tactical",
        "label": "Tactical",
        "description": "Understanding the game: choices, positions and reading what happens next.",
        "anchors": {
            "2": "Often in the wrong place or makes the wrong choice.",
            "5": "Understands the basics and follows the game plan.",
            "8": "Reads play early and makes good choices quickly.",
            "10": "Sees things before anyone else and shapes the game around them.",
        },
    },
    {
        "key": "mental",
        "label": "Mental",
        "description": "Attitude, resilience and how they behave with teammates and coaches.",
        "anchors": {
            "2": "Drops off when things go wrong; hard to coach.",
            "5": "Steady most of the time; occasional lapses.",
            "8": "Consistent, driven and responds well to setbacks and feedback.",
            "10": "Lifts everyone around them; thrives under the most pressure.",
        },
    },
    {
        "key": "context",
        "label": "Context",
        "description": "Where they play and how much, so the ratings can be read fairly.",
        "anchors": {
            "2": "Little evidence: low level, few minutes or a falling trend.",
            "5": "A fair sample at a typical level for the age group.",
            "8": "Plenty of minutes at a strong level, improving steadily.",
            "10": "Regular minutes at the top level for the age, improving fast.",
        },
    },
]

AREA_KEYS = {area["key"] for area in AREAS}


def attr(
    key: str, label: str, area: str, description: str, positions: list[str] | None = None
) -> dict:
    row = {"key": key, "label": label, "area": area, "description": description, "scale": SCALE}
    if positions:
        row["applies_to_positions"] = positions
    return row


def test(key: str, label: str, unit: str, better: str, description: str) -> dict:
    return {"key": key, "label": label, "unit": unit, "better": better, "description": description}


def stat(
    key: str, label: str, per: str, *, source: str = "", formula: str = "", unit: str = ""
) -> dict:
    row = {"key": key, "label": label, "per": per}
    if formula:
        row["formula"] = formula
    else:
        row["source"] = source
    if unit:
        row["unit"] = unit
    return row


UNIVERSAL_ATTRIBUTES: list[dict] = [
    attr("speed", "Speed", "physical", "Top speed over the distances the sport needs."),
    attr(
        "acceleration",
        "Acceleration",
        "physical",
        "How quickly they reach top speed from a standing or slow start.",
    ),
    attr(
        "endurance",
        "Endurance",
        "physical",
        "Keeps working at a high level to the end of the game or race.",
    ),
    attr("strength", "Strength", "physical", "Holds their own in contact and generates force."),
    attr("agility", "Agility", "physical", "Changes direction quickly and under control."),
    attr(
        "balance",
        "Balance and coordination",
        "physical",
        "Stays balanced and moves smoothly when off balance or in contact.",
    ),
    attr(
        "decision_making",
        "Decision making",
        "tactical",
        "Picks the right option, at the right time.",
    ),
    attr(
        "positioning",
        "Positioning",
        "tactical",
        "Is in the right place, with and without the ball or play.",
    ),
    attr(
        "game_reading",
        "Game reading",
        "tactical",
        "Anticipates what will happen next and reacts early.",
    ),
    attr("versatility", "Versatility", "tactical", "Plays well in more than one role or system."),
    attr(
        "composure",
        "Composure under pressure",
        "mental",
        "Stays calm and performs in the big moments.",
    ),
    attr(
        "work_rate",
        "Work rate",
        "mental",
        "Keeps working for the team without the ball or when tired.",
    ),
    attr(
        "coachability",
        "Coachability",
        "mental",
        "Listens, applies feedback and improves between sessions.",
    ),
    attr(
        "leadership",
        "Leadership",
        "mental",
        "Organises, encourages and sets the standard for others.",
    ),
    attr("consistency", "Consistency", "mental", "Performs to the same level week after week."),
    attr(
        "competitiveness",
        "Competitiveness",
        "mental",
        "Wants to win every contest and hates losing them.",
    ),
    attr(
        "level_of_competition",
        "Level of competition",
        "context",
        "How strong the league or events they play in are.",
    ),
    attr(
        "minutes_played",
        "Minutes played",
        "context",
        "How much they actually play, so the sample is fair.",
    ),
    attr(
        "development_trend",
        "Development trend",
        "context",
        "Improving, flat or declining over the last seasons.",
    ),
]

# Engine values that are not a single score type: outcomes, scoring points, result
# sheets and profile measurements. Phase 3 calculates them per player.
ENGINE_SOURCES: dict[str, str] = {
    "points": "Scoring points from the player's own events",
    "outcome.played": "Fixtures played",
    "outcome.wins": "Fixtures won",
    "outcome.losses": "Fixtures lost",
    "outcome.draws": "Fixtures drawn",
    "outcome.played_vs_higher": "Fixtures against a higher-ranked opponent",
    "outcome.wins_vs_higher": "Wins against a higher-ranked opponent",
    "outcome.opponent_rank": "Average table position of the opponents",
    "result.best": "Best mark on a result sheet (personal best)",
    "result.season_best": "Best mark this season",
    "result.latest": "Most recent mark",
    "result.progress": "Change in best mark from last season to this one (%)",
    "result.wind_legal": "Share of marks with a legal wind (%)",
    "result.age_graded": "Best mark as a percentage of the age-group standard",
    "result.splits": "Split times from the latest race",
    "participant.handicap": "Playing handicap, from the competition",
    "profile.reach": "Standing reach from the profile",
    "profile.weight": "Body mass from the profile",
}

# Names a formula may use besides the sport's own stat keys.
BUILTINS: dict[str, str] = {
    "matches": "Matches, games or events played",
    "minutes": "Minutes played",
    "rounds": "Rounds or races completed",
}


def _soccer() -> dict:
    keeper = ["goalkeeper"]
    return {
        "attributes": [
            attr(
                "first_touch",
                "First touch",
                "technical",
                "Controls the ball cleanly and sets up the next action.",
            ),
            attr(
                "passing_short",
                "Short passing",
                "technical",
                "Accurate, well-weighted passes over short range.",
            ),
            attr(
                "passing_long",
                "Long passing",
                "technical",
                "Switches play and finds runners over distance.",
            ),
            attr(
                "dribbling",
                "Dribbling",
                "technical",
                "Carries the ball past opponents under control.",
            ),
            attr(
                "finishing",
                "Finishing",
                "technical",
                "Turns chances into goals with either foot and the head.",
            ),
            attr("heading", "Heading", "technical", "Wins headers and directs them with purpose."),
            attr("crossing", "Crossing", "technical", "Delivers dangerous balls into the box."),
            attr("tackling", "Tackling", "technical", "Wins the ball cleanly without fouling."),
            attr(
                "interceptions",
                "Interceptions",
                "tactical",
                "Reads passes and steps in to win the ball.",
            ),
            attr(
                "weaker_foot",
                "Weaker foot",
                "technical",
                "How usable the weaker foot is for passing and shooting.",
            ),
            attr(
                "gk_handling",
                "Handling",
                "technical",
                "Catches and holds shots and crosses cleanly.",
                keeper,
            ),
            attr(
                "gk_distribution",
                "Distribution",
                "technical",
                "Starts attacks with accurate throws, kicks and passes.",
                keeper,
            ),
            attr(
                "gk_shot_stopping",
                "Shot-stopping",
                "technical",
                "Reflexes, positioning and reach to save shots.",
                keeper,
            ),
            attr(
                "gk_command",
                "Command of area",
                "tactical",
                "Claims crosses and organises the defence.",
                keeper,
            ),
        ],
        "physical_tests": [
            test(
                "sprint_10m",
                "10 m sprint",
                "s",
                "lower",
                "Acceleration from a standing start, timed gates.",
            ),
            test("sprint_30m", "30 m sprint", "s", "lower", "Speed over a typical match sprint."),
            test("sprint_40m", "40 m sprint", "s", "lower", "Top speed over 40 m."),
            test(
                "yo_yo_ir1",
                "Yo-Yo IR1",
                "m",
                "higher",
                "Intermittent recovery test, level 1: distance covered.",
            ),
            test("vertical_jump", "Vertical jump", "cm", "higher", "Countermovement jump height."),
        ],
        "match_stats": [
            stat("goals", "Goals", "match", source="goal"),
            stat("assists", "Assists", "match", source="assist"),
            stat("shots", "Shots", "match", source="shot"),
            stat("shots_on_target", "Shots on target", "match", source="shot-on-target"),
            stat("goals_per_90", "Goals per 90", "90min", formula="goals * 90 / minutes"),
            stat("assists_per_90", "Assists per 90", "90min", formula="assists * 90 / minutes"),
            stat(
                "shots_on_target_per_90",
                "Shots on target per 90",
                "90min",
                formula="shots_on_target * 90 / minutes",
            ),
            stat(
                "conversion_rate",
                "Conversion rate",
                "match",
                formula="goals / shots * 100",
                unit="%",
            ),
            stat("tackles", "Tackles won", "match", source="tackle"),
            stat("interceptions", "Interceptions", "match", source="interception"),
            stat("saves", "Saves", "match", source="save"),
        ],
    }


SPORT_ATTRIBUTES: dict[str, dict] = {
    "soccer": _soccer(),
    "rugby_union": {
        "attributes": [
            attr(
                "tackling", "Tackling", "technical", "Safe, dominant tackles that stop the carrier."
            ),
            attr(
                "carrying",
                "Carrying",
                "technical",
                "Breaks the line or gets over the gain line in contact.",
            ),
            attr(
                "breakdown",
                "Breakdown / jackal",
                "technical",
                "Wins or slows the ball at the ruck legally.",
            ),
            attr("passing", "Passing", "technical", "Accurate passes off both hands, at pace."),
            attr(
                "kicking_tactical",
                "Tactical kicking",
                "technical",
                "Kicks for territory and regains with accuracy.",
                ["scrum-half", "fly-half", "centre", "fullback", "wing"],
            ),
            attr(
                "kicking_goal",
                "Goal kicking",
                "technical",
                "Converts penalties and conversions under pressure.",
                ["fly-half", "fullback", "centre"],
            ),
            attr(
                "lineout_throw",
                "Lineout throwing",
                "technical",
                "Hits the jumper accurately.",
                ["hooker"],
            ),
            attr(
                "lineout_jump",
                "Lineout jumping",
                "technical",
                "Wins own ball and contests theirs.",
                ["lock", "flanker", "number-8"],
            ),
            attr(
                "scrummaging",
                "Scrummaging",
                "technical",
                "Holds and drives in the scrum safely.",
                ["loosehead-prop", "hooker", "tighthead-prop", "lock"],
            ),
            attr(
                "line_speed",
                "Defensive line speed",
                "tactical",
                "Gets off the line quickly and in shape with the defence.",
            ),
        ],
        "physical_tests": [
            test("sprint_40m", "40 m sprint", "s", "lower", "Top speed over 40 m."),
            test(
                "bronco",
                "Bronco",
                "s",
                "lower",
                "Repeated 20 / 40 / 60 m shuttles, 1,200 m in total.",
            ),
            test(
                "bench_press_1rm",
                "Bench press 1RM",
                "kg",
                "higher",
                "Heaviest single repetition, coached technique.",
            ),
            test(
                "body_mass", "Body mass", "kg", "higher", "Weighed in the morning before training."
            ),
        ],
        "match_stats": [
            stat("tackles_made", "Tackles made", "match", source="tackle"),
            stat("tackles_missed", "Tackles missed", "match", source="missed-tackle"),
            stat(
                "tackle_success",
                "Tackle success",
                "match",
                formula="tackles_made / (tackles_made + tackles_missed) * 100",
                unit="%",
            ),
            stat("carries", "Carries", "match", source="carry"),
            stat("metres_gained", "Metres gained", "match", source="metres-gained", unit="m"),
            stat("line_breaks", "Line breaks", "match", source="line-break"),
            stat("turnovers", "Turnovers won", "match", source="turnover-won"),
            stat("tries", "Tries", "match", source="try"),
            stat("points", "Points", "match", source="points"),
        ],
    },
    "cricket": {
        "attributes": [
            attr(
                "batting_pace",
                "Batting against pace",
                "technical",
                "Technique and judgement against fast bowling.",
                ["batter", "all-rounder", "wicket-keeper"],
            ),
            attr(
                "batting_spin",
                "Batting against spin",
                "technical",
                "Footwork and shot choice against spin.",
                ["batter", "all-rounder", "wicket-keeper"],
            ),
            attr("shot_range", "Shot range", "technical", "Can score all around the ground."),
            attr(
                "running",
                "Running between wickets",
                "tactical",
                "Quick, safe calls and turns for extra runs.",
            ),
            attr(
                "bowling_pace",
                "Bowling pace",
                "technical",
                "Speed through the air.",
                ["fast-bowler", "all-rounder"],
            ),
            attr(
                "bowling_accuracy",
                "Bowling accuracy",
                "technical",
                "Hits a line and length consistently.",
                ["fast-bowler", "spin-bowler", "all-rounder"],
            ),
            attr(
                "bowling_variation",
                "Bowling variation",
                "technical",
                "Changes of pace, length and movement.",
                ["fast-bowler", "spin-bowler", "all-rounder"],
            ),
            attr(
                "spin",
                "Spin",
                "technical",
                "Turn, drift and control of the spinning ball.",
                ["spin-bowler"],
            ),
            attr("fielding", "Fielding", "technical", "Stops, picks up and throws accurately."),
            attr("catching", "Catching", "technical", "Holds catches close in and in the deep."),
            attr(
                "keeping",
                "Wicket-keeping",
                "technical",
                "Takes the ball cleanly, stumpings and run-outs.",
                ["wicket-keeper"],
            ),
        ],
        "physical_tests": [
            test(
                "bowling_speed",
                "Bowling speed",
                "km/h",
                "higher",
                "Fastest of six deliveries on a speed gun.",
            ),
            test("run_2km", "2 km run", "s", "lower", "Time for 2 km on a flat track."),
            test(
                "run_a_three",
                "Run-a-three",
                "s",
                "lower",
                "Three runs between the creases with a bat.",
            ),
        ],
        "match_stats": [
            stat("runs", "Runs", "match", source="run"),
            stat("dismissals", "Times out", "match", source="dismissed"),
            stat("balls_faced", "Balls faced", "match", source="ball-faced"),
            stat("batting_average", "Batting average", "match", formula="runs / dismissals"),
            stat("strike_rate", "Strike rate", "match", formula="runs / balls_faced * 100"),
            stat("wickets", "Wickets", "match", source="wicket"),
            stat("runs_conceded", "Runs conceded", "match", source="run-conceded"),
            stat("balls_bowled", "Balls bowled", "match", source="ball"),
            stat("bowling_average", "Bowling average", "match", formula="runs_conceded / wickets"),
            stat("economy", "Economy rate", "match", formula="runs_conceded / balls_bowled * 6"),
            stat("catches", "Catches", "match", source="catch"),
        ],
    },
    "netball": {
        "attributes": [
            attr(
                "shooting",
                "Shooting accuracy",
                "technical",
                "Scores from all areas of the circle.",
                ["gs", "ga"],
            ),
            attr(
                "feeding",
                "Feeding",
                "technical",
                "Delivers the ball into the circle accurately.",
                ["ga", "wa", "c"],
            ),
            attr(
                "interceptions",
                "Interceptions",
                "technical",
                "Reads and takes the opponent's pass.",
            ),
            attr("footwork", "Footwork", "technical", "Lands, pivots and moves without stepping."),
            attr(
                "court_vision", "Court vision", "tactical", "Sees space and the right pass early."
            ),
            attr(
                "defending",
                "Defending",
                "technical",
                "Marks closely and pressures the ball legally.",
                ["wd", "gd", "gk", "c"],
            ),
            attr(
                "elevation",
                "Elevation",
                "physical",
                "Gets off the ground to catch, intercept or rebound.",
            ),
        ],
        "physical_tests": [
            test("sprint_20m", "20 m sprint", "s", "lower", "Acceleration over a court length."),
            test("vertical_jump", "Vertical jump", "cm", "higher", "Countermovement jump height."),
            test(
                "beep_test",
                "Beep test",
                "level",
                "higher",
                "Multi-stage 20 m shuttle run level reached.",
            ),
        ],
        "match_stats": [
            stat("goals", "Goals", "match", source="goal"),
            stat("missed_shots", "Missed shots", "match", source="missed-shot"),
            stat("attempts", "Goal attempts", "match", formula="goals + missed_shots"),
            stat(
                "shooting_percentage",
                "Shooting %",
                "match",
                formula="goals / (goals + missed_shots) * 100",
                unit="%",
            ),
            stat(
                "centre_pass_receives",
                "Centre-pass receives",
                "match",
                source="centre-pass-receive",
            ),
            stat("gains", "Gains", "match", source="gain"),
            stat("intercepts", "Intercepts", "match", source="intercept"),
        ],
    },
    "basketball": {
        "attributes": [
            attr(
                "catch_and_shoot", "Catch-and-shoot", "technical", "Shoots accurately off the pass."
            ),
            attr(
                "off_the_dribble",
                "Shooting off the dribble",
                "technical",
                "Creates and makes shots on the move.",
            ),
            attr(
                "free_throw",
                "Free throws",
                "technical",
                "Repeatable free-throw routine and accuracy.",
            ),
            attr(
                "ball_handling",
                "Ball handling",
                "technical",
                "Keeps the dribble alive under pressure, both hands.",
            ),
            attr("passing", "Passing", "technical", "Finds the open player on time and on target."),
            attr("rebounding", "Rebounding", "technical", "Boxes out and secures the ball."),
            attr(
                "perimeter_defence",
                "Perimeter defence",
                "technical",
                "Stays in front of guards and contests shots.",
                ["point-guard", "shooting-guard", "small-forward"],
            ),
            attr(
                "post_defence",
                "Post defence",
                "technical",
                "Holds position and defends close to the basket.",
                ["power-forward", "centre"],
            ),
            attr(
                "finishing",
                "Finishing at the rim",
                "technical",
                "Scores through contact near the basket.",
            ),
        ],
        "physical_tests": [
            test(
                "standing_reach",
                "Standing reach",
                "cm",
                "higher",
                "Highest point reached flat-footed.",
            ),
            test("wingspan", "Wingspan", "cm", "higher", "Fingertip to fingertip, arms out."),
            test(
                "max_vertical",
                "Max vertical jump",
                "cm",
                "higher",
                "Running vertical jump above standing reach.",
            ),
            test("lane_agility", "Lane agility", "s", "lower", "The standard combine lane drill."),
            test(
                "sprint_three_quarter",
                "3/4-court sprint",
                "s",
                "lower",
                "Baseline to the opposite free-throw line.",
            ),
        ],
        "match_stats": [
            stat("points", "Points", "match", source="points"),
            stat("ppg", "Points per game", "game", formula="points / matches"),
            stat("rebounds", "Rebounds", "match", source="rebound"),
            stat("rpg", "Rebounds per game", "game", formula="rebounds / matches"),
            stat("assists", "Assists", "match", source="assist"),
            stat("apg", "Assists per game", "game", formula="assists / matches"),
            stat("steals", "Steals", "match", source="steal"),
            stat("blocks", "Blocks", "match", source="block"),
            stat("two_made", "2-point field goals", "match", source="field-goal"),
            stat("two_missed", "2-point misses", "match", source="missed-field-goal"),
            stat("three_made", "3-pointers", "match", source="three-pointer"),
            stat("three_missed", "3-point misses", "match", source="missed-three"),
            stat("ft_made", "Free throws made", "match", source="free-throw"),
            stat("ft_missed", "Free throws missed", "match", source="missed-free-throw"),
            stat(
                "fg_percentage",
                "FG%",
                "match",
                formula=(
                    "(two_made + three_made)"
                    " / (two_made + two_missed + three_made + three_missed) * 100"
                ),
                unit="%",
            ),
            stat(
                "three_percentage",
                "3P%",
                "match",
                formula="three_made / (three_made + three_missed) * 100",
                unit="%",
            ),
            stat(
                "ft_percentage",
                "FT%",
                "match",
                formula="ft_made / (ft_made + ft_missed) * 100",
                unit="%",
            ),
        ],
    },
    "athletics": {
        "attributes": [
            attr(
                "event_technique",
                "Event technique",
                "technical",
                "Technique in their own event: running form, jump or throw.",
            ),
            attr(
                "start_reaction",
                "Start and reaction",
                "technical",
                "Reacts and drives out of the start well.",
                ["sprints", "hurdles"],
            ),
            attr(
                "race_tactics",
                "Race tactics",
                "tactical",
                "Positions and paces the race well.",
                ["middle-distance", "long-distance"],
            ),
        ],
        "physical_tests": [
            test("event_100m", "100 m", "s", "lower", "The event itself: a timed 100 m."),
            test("event_400m", "400 m", "s", "lower", "The event itself: a timed 400 m."),
            test("event_1500m", "1500 m", "s", "lower", "The event itself: a timed 1500 m."),
            test(
                "event_long_jump", "Long jump", "m", "higher", "The event itself: best legal jump."
            ),
            test(
                "event_shot_put", "Shot put", "m", "higher", "The event itself: best legal throw."
            ),
        ],
        "match_stats": [
            stat("personal_best", "Personal best", "game", source="result.best"),
            stat("season_best", "Season best", "game", source="result.season_best"),
            stat("wind_legal", "Wind-legal marks", "game", source="result.wind_legal", unit="%"),
            stat("age_graded", "Age-graded", "game", source="result.age_graded", unit="%"),
            stat("progress", "Progress on last season", "game", source="result.progress", unit="%"),
        ],
    },
    "tennis": {
        "attributes": [
            attr("serve", "Serve", "technical", "Pace, placement and variety on serve."),
            attr("return", "Return", "technical", "Neutralises or attacks the opponent's serve."),
            attr(
                "forehand",
                "Forehand",
                "technical",
                "Consistency and weight of shot off the forehand.",
            ),
            attr(
                "backhand",
                "Backhand",
                "technical",
                "Consistency and weight of shot off the backhand.",
            ),
            attr("net_play", "Volley and net play", "technical", "Finishes points at the net."),
            attr(
                "movement",
                "Movement and footwork",
                "physical",
                "Gets to the ball balanced and recovers quickly.",
            ),
            attr(
                "shot_selection",
                "Shot selection",
                "tactical",
                "Chooses when to rally, attack or defend.",
            ),
        ],
        "physical_tests": [
            test(
                "serve_speed",
                "Serve speed",
                "km/h",
                "higher",
                "Fastest first serve on a radar gun.",
            ),
            test(
                "spider_drill",
                "Spider drill",
                "s",
                "lower",
                "Agility drill touching five points around the court.",
            ),
        ],
        "match_stats": [
            stat("aces", "Aces", "match", source="ace"),
            stat("double_faults", "Double faults", "match", source="double-fault"),
            stat("first_serves_in", "First serves in", "match", source="first-serve-in"),
            stat("first_serve_faults", "First-serve faults", "match", source="first-serve-fault"),
            stat(
                "first_serve_percentage",
                "First-serve %",
                "match",
                formula="first_serves_in / (first_serves_in + first_serve_faults) * 100",
                unit="%",
            ),
            stat("unforced_errors", "Unforced errors", "match", source="unforced-error"),
            stat("wins", "Wins", "match", source="outcome.wins"),
            stat("played", "Matches", "match", source="outcome.played"),
            stat("win_rate", "Win rate", "match", formula="wins / played * 100", unit="%"),
            stat(
                "wins_vs_higher", "Wins vs higher-ranked", "match", source="outcome.wins_vs_higher"
            ),
            stat(
                "played_vs_higher",
                "Matches vs higher-ranked",
                "match",
                source="outcome.played_vs_higher",
            ),
            stat(
                "win_rate_vs_higher",
                "Win rate vs higher-ranked",
                "match",
                formula="wins_vs_higher / played_vs_higher * 100",
                unit="%",
            ),
        ],
    },
    "volleyball": {
        "attributes": [
            attr("serving", "Serving", "technical", "Aggressive, accurate serves with few errors."),
            attr(
                "passing",
                "Passing / reception",
                "technical",
                "Delivers the serve receive to the setter.",
                ["outside-hitter", "libero", "opposite"],
            ),
            attr(
                "setting",
                "Setting",
                "technical",
                "Accurate, deceptive sets to every hitter.",
                ["setter"],
            ),
            attr(
                "attacking",
                "Attacking",
                "technical",
                "Hits with power and placement.",
                ["outside-hitter", "opposite", "middle-blocker"],
            ),
            attr(
                "blocking",
                "Blocking",
                "technical",
                "Reads hitters and seals the net.",
                ["middle-blocker", "opposite", "outside-hitter", "setter"],
            ),
            attr(
                "digging",
                "Digging",
                "technical",
                "Keeps hard-driven balls alive.",
                ["libero", "outside-hitter", "setter"],
            ),
        ],
        "physical_tests": [
            test(
                "spike_reach", "Spike reach", "cm", "higher", "Highest touch with an approach jump."
            ),
            test(
                "block_reach",
                "Block reach",
                "cm",
                "higher",
                "Highest touch with a two-foot block jump.",
            ),
            test(
                "vertical_jump", "Vertical jump", "cm", "higher", "Standing countermovement jump."
            ),
        ],
        "match_stats": [
            stat("kills", "Kills", "match", source="kill"),
            stat("attack_errors", "Attack errors", "match", source="attack-error"),
            stat("attack_attempts", "Attack attempts", "match", source="attack-attempt"),
            stat(
                "hitting_efficiency",
                "Hitting efficiency",
                "match",
                formula="(kills - attack_errors) / attack_attempts",
            ),
            stat("aces", "Aces", "match", source="ace"),
            stat("blocks", "Blocks", "match", source="block"),
            stat("digs", "Digs", "match", source="dig"),
        ],
    },
    "golf": {
        "attributes": [
            attr("driving_distance", "Driving distance", "technical", "Length off the tee."),
            attr(
                "driving_accuracy",
                "Driving accuracy",
                "technical",
                "Finds the fairway under pressure.",
            ),
            attr(
                "iron_play", "Iron play", "technical", "Distance control and accuracy into greens."
            ),
            attr("short_game", "Short game", "technical", "Chipping, pitching and bunker play."),
            attr("putting", "Putting", "technical", "Holes short putts and lags long ones."),
            attr(
                "course_management",
                "Course management",
                "tactical",
                "Plays the percentages and avoids big numbers.",
            ),
        ],
        "physical_tests": [
            test(
                "club_head_speed",
                "Club-head speed",
                "km/h",
                "higher",
                "Driver club-head speed on a launch monitor.",
            ),
            test("carry_distance", "Driver carry", "m", "higher", "Average carry of five drives."),
        ],
        "match_stats": [
            stat("strokes", "Strokes", "game", source="stroke"),
            stat("scoring_average", "Scoring average", "game", formula="strokes / rounds"),
            stat("handicap", "Handicap", "game", source="participant.handicap"),
            stat(
                "greens_in_regulation", "Greens in regulation", "game", source="green-in-regulation"
            ),
            stat("putts", "Putts", "game", source="putt"),
            stat("putts_per_round", "Putts per round", "game", formula="putts / rounds"),
            stat("fairways_hit", "Fairways hit", "game", source="fairway-hit"),
        ],
    },
    "swimming": {
        "attributes": [
            attr("start", "Start", "technical", "Reaction, entry and underwater phase."),
            attr("turns", "Turns", "technical", "Fast, tight turns and push-offs."),
            attr(
                "stroke_technique",
                "Stroke technique",
                "technical",
                "Efficient technique in their main stroke.",
            ),
            attr("pacing", "Pacing", "tactical", "Splits the race well for the distance."),
        ],
        "physical_tests": [
            test(
                "css",
                "Critical swim speed",
                "s/100m",
                "lower",
                "From a 400 m and a 200 m time trial.",
            ),
            test(
                "vertical_jump",
                "Vertical jump",
                "cm",
                "higher",
                "Countermovement jump: start power.",
            ),
        ],
        "match_stats": [
            stat("personal_best", "Best time", "game", source="result.best", unit="s"),
            stat("season_best", "Season best", "game", source="result.season_best", unit="s"),
            stat("splits", "Splits", "game", source="result.splits"),
            stat("progress", "Progress on last season", "game", source="result.progress", unit="%"),
        ],
    },
    "boxing": {
        "attributes": [
            attr("footwork", "Footwork", "technical", "Moves in and out of range on balance."),
            attr("defence", "Defence", "technical", "Slips, blocks and rolls punches."),
            attr(
                "punch_selection",
                "Punch selection",
                "technical",
                "Throws the right shot at the right time.",
            ),
            attr("power", "Power", "physical", "Hurts opponents with clean shots."),
            attr(
                "ring_generalship",
                "Ring generalship",
                "tactical",
                "Controls where and how the bout is fought.",
            ),
            attr(
                "conditioning", "Conditioning", "physical", "Keeps output high to the final bell."
            ),
        ],
        "physical_tests": [
            test("punch_force", "Punch force", "N", "higher", "Peak force on a calibrated bag."),
            test("run_3km", "3 km run", "s", "lower", "Time for 3 km on a flat track."),
        ],
        "match_stats": [
            stat("wins", "Wins", "match", source="outcome.wins"),
            stat("losses", "Losses", "match", source="outcome.losses"),
            stat("draws", "Draws", "match", source="outcome.draws"),
            stat(
                "opposition_quality",
                "Opponents' average rank",
                "match",
                source="outcome.opponent_rank",
            ),
            stat("weight", "Weight", "match", source="profile.weight", unit="kg"),
            stat("reach", "Reach", "match", source="profile.reach", unit="cm"),
        ],
    },
    "hockey": {
        "attributes": [
            attr(
                "stick_skills", "Stick skills", "technical", "Close control and elimination skills."
            ),
            attr("passing", "Passing", "technical", "Accurate push, slap and aerial passes."),
            attr(
                "receiving",
                "Receiving",
                "technical",
                "Controls the ball on both sides of the stick.",
            ),
            attr(
                "shooting",
                "Shooting",
                "technical",
                "Scores from field play and deflections.",
                ["forward", "midfielder"],
            ),
            attr(
                "tackling",
                "Tackling",
                "technical",
                "Channels and tackles without fouling.",
                ["defender", "midfielder"],
            ),
            attr(
                "drag_flick",
                "Drag flick",
                "technical",
                "Penalty-corner drag flick power and accuracy.",
            ),
            attr(
                "gk_saves",
                "Goalkeeping",
                "technical",
                "Saves, clearances and command of the circle.",
                ["goalkeeper"],
            ),
        ],
        "physical_tests": [
            test("sprint_30m", "30 m sprint", "s", "lower", "Speed over 30 m."),
            test("yo_yo_ir1", "Yo-Yo IR1", "m", "higher", "Intermittent recovery test, level 1."),
        ],
        "match_stats": [
            stat("goals", "Goals", "match", source="field-goal"),
            stat("assists", "Assists", "match", source="assist"),
            stat("shots", "Shots", "match", source="shot"),
            stat("circle_entries", "Circle entries", "match", source="circle-entry"),
            stat("tackles", "Tackles", "match", source="tackle"),
            stat("goals_per_game", "Goals per game", "game", formula="goals / matches"),
        ],
    },
    "rowing": {
        "attributes": [
            attr(
                "technique",
                "Rowing technique",
                "technical",
                "Catch, drive and recovery; blade work.",
            ),
            attr(
                "rhythm",
                "Rhythm and timing",
                "technical",
                "Moves with the crew and keeps the boat running.",
                ["stroke", "bow", "engine-room"],
            ),
            attr(
                "steering",
                "Steering and calls",
                "tactical",
                "Steers a fair line and makes the right calls.",
                ["cox"],
            ),
        ],
        "physical_tests": [
            test("erg_2km", "2 km erg", "s", "lower", "Time for 2,000 m on an ergometer."),
            test(
                "power_to_weight",
                "Power-to-weight",
                "W/kg",
                "higher",
                "Average watts over 2 km divided by body mass.",
            ),
            test("vo2_max", "VO2 max", "ml/kg/min", "higher", "Laboratory or field estimate."),
        ],
        "match_stats": [
            stat("best_time", "Best race time", "game", source="result.best", unit="s"),
            stat("season_best", "Season best", "game", source="result.season_best", unit="s"),
            stat("progress", "Progress on last season", "game", source="result.progress", unit="%"),
        ],
    },
    "cycling": {
        "attributes": [
            attr(
                "bike_handling",
                "Bike handling",
                "technical",
                "Cornering, descending and riding in a bunch.",
            ),
            attr("pacing", "Pacing", "tactical", "Spreads the effort well for the course."),
            attr(
                "sprint",
                "Sprint",
                "physical",
                "Kick and top speed in a finish.",
                ["sprinter", "all-rounder"],
            ),
            attr(
                "climbing",
                "Climbing",
                "physical",
                "Sustains power uphill.",
                ["climber", "all-rounder"],
            ),
        ],
        "physical_tests": [
            test("ftp", "FTP", "W/kg", "higher", "Functional threshold power per kilogram."),
            test("vo2_max", "VO2 max", "ml/kg/min", "higher", "Laboratory or field estimate."),
            test("peak_power", "Peak power", "W", "higher", "Best 5-second power."),
        ],
        "match_stats": [
            stat("best_time", "Best time", "game", source="result.best", unit="s"),
            stat("wins", "Wins", "game", source="outcome.wins"),
            stat("races", "Races", "game", source="outcome.played"),
            stat("progress", "Progress on last season", "game", source="result.progress", unit="%"),
        ],
    },
    "esports": {
        # Physical speed and strength do not apply; reaction and hand-eye do.
        "skip_universal": ["speed", "acceleration", "strength", "agility"],
        "attributes": [
            attr(
                "reaction",
                "Reaction time",
                "physical",
                "Responds quickly to what happens on screen.",
            ),
            attr(
                "hand_eye",
                "Hand-eye coordination",
                "physical",
                "Precise, repeatable mouse and controller input.",
            ),
            attr(
                "mechanics",
                "Mechanics",
                "technical",
                "Aim, movement and execution of game mechanics.",
            ),
            attr(
                "game_knowledge",
                "Game knowledge",
                "tactical",
                "Knows maps, matchups and the current meta.",
            ),
            attr(
                "communication",
                "Communication",
                "mental",
                "Clear, calm calls that the team can act on.",
            ),
        ],
        "physical_tests": [
            test(
                "reaction_test",
                "Reaction test",
                "ms",
                "lower",
                "Average of ten visual reaction trials.",
            ),
            test(
                "aim_test",
                "Aim trainer score",
                "points",
                "higher",
                "Standard aim-trainer scenario.",
            ),
        ],
        "match_stats": [
            stat("wins", "Wins", "match", source="outcome.wins"),
            stat("played", "Matches", "match", source="outcome.played"),
            stat("win_rate", "Win rate", "match", formula="wins / played * 100", unit="%"),
        ],
    },
}

# Squash and badminton share the racket catalogue, with their own tests; only
# tennis records serve stats.
SERVE_STATS = {
    "aces",
    "double_faults",
    "first_serves_in",
    "first_serve_faults",
    "first_serve_percentage",
}
SPORT_ATTRIBUTES["squash"] = {
    **SPORT_ATTRIBUTES["tennis"],
    "physical_tests": [
        test("ghosting", "Ghosting drill", "s", "lower", "Six-corner movement drill, ten reps."),
        test(
            "spider_drill",
            "Spider drill",
            "s",
            "lower",
            "Agility drill touching the court corners.",
        ),
    ],
    "match_stats": [
        row for row in SPORT_ATTRIBUTES["tennis"]["match_stats"] if row["key"] not in SERVE_STATS
    ],
}
SPORT_ATTRIBUTES["badminton"] = {
    **SPORT_ATTRIBUTES["tennis"],
    "physical_tests": [
        test("smash_speed", "Smash speed", "km/h", "higher", "Fastest smash on a radar gun."),
        test("spider_drill", "Spider drill", "s", "lower", "Six-corner footwork drill."),
    ],
    "match_stats": SPORT_ATTRIBUTES["squash"]["match_stats"],
}


# Which way is better for a stat, for percentiles. Most stats: higher. A stat
# listed in NO_PERCENTILE is context, not a performance (weight, splits), or
# mixes events (an athletics best across different events).
LOWER_STATS = {
    "tackles_missed",
    "double_faults",
    "unforced_errors",
    "attack_errors",
    "bowling_average",
    "economy",
    "runs_conceded",
    "dismissals",
    "scoring_average",
    "strokes",
    "putts",
    "putts_per_round",
    "missed_shots",
    "two_missed",
    "three_missed",
    "ft_missed",
    "losses",
    "opposition_quality",
    "handicap",
}
NO_PERCENTILE = {"weight", "reach", "splits", "played", "played_vs_higher", "races"}
SPORT_STAT_BETTER: dict[tuple[str, str], str | None] = {
    ("swimming", "personal_best"): "lower",
    ("swimming", "season_best"): "lower",
    ("rowing", "best_time"): "lower",
    ("rowing", "season_best"): "lower",
    ("cycling", "best_time"): "lower",
    ("athletics", "personal_best"): None,
    ("athletics", "season_best"): None,
}


def stat_better(sport: str, key: str) -> str | None:
    if (sport, key) in SPORT_STAT_BETTER:
        return SPORT_STAT_BETTER[(sport, key)]
    if key in NO_PERCENTILE:
        return None
    return "lower" if key in LOWER_STATS else "higher"


# --- Scout ratings (Phase 4) ------------------------------------------------------------

# How much a scout saw; the weight their scores carry in the organisation average.
CONFIDENCE = [
    {"key": "low", "label": "Low", "description": "A few minutes, or one moment", "weight": 1},
    {"key": "medium", "label": "Medium", "description": "Most of a match", "weight": 2},
    {"key": "high", "label": "High", "description": "Several full matches", "weight": 3},
]
CONFIDENCE_WEIGHTS = {row["key"]: row["weight"] for row in CONFIDENCE}

WATCHED = [
    {"key": "live", "label": "Watched live"},
    {"key": "video", "label": "On video"},
]

RECOMMENDATIONS = [
    {"key": "monitor", "label": "Monitor"},
    {"key": "trial", "label": "Trial"},
    {"key": "sign", "label": "Sign"},
    {"key": "not_for_us", "label": "Not for us"},
]


# --- Search, shortlists and contact (Phase 5) -----------------------------------------------

# Set on a competition (settings "level"); a player's level is the highest of
# their teams' competitions.
COMPETITION_LEVELS = [
    {"key": "school", "label": "School", "rank": 1},
    {"key": "club", "label": "Club", "rank": 2},
    {"key": "provincial", "label": "Provincial", "rank": 3},
    {"key": "national", "label": "National", "rank": 4},
    {"key": "international", "label": "International", "rank": 5},
]
LEVEL_RANK = {row["key"]: row["rank"] for row in COMPETITION_LEVELS}

SHORTLIST_STATUSES = [
    {"key": "watching", "label": "Watching"},
    {"key": "contacted", "label": "Contacted"},
    {"key": "trial_booked", "label": "Trial booked"},
    {"key": "signed", "label": "Signed"},
    {"key": "rejected", "label": "Rejected"},
]
