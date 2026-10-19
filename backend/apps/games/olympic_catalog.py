"""The Olympic programme as data: sport -> discipline -> events.

Based on the Paris 2024 and LA 2028 Summer programmes and the Milano Cortina 2026
Winter programme. VERIFY the exact event list against the Games being modelled;
programmes change between editions. Each sport names its International
Federation, the locked preset its events use, the usual round format and how
bronze is decided. A sport whose preset is not built yet is listed but cannot be
added until that preset exists.
"""

from __future__ import annotations

MEN, WOMEN, MIXED, OPEN = "men", "women", "mixed", "open"
TEAM, INDIVIDUAL = "team", "individual"

STANDARD, BRONZE_MATCH, TWO_BRONZE = "standard", "bronze_match", "two_bronze"


def ev(name: str, gender: str, kind: str = INDIVIDUAL, *, preset: str | None = None) -> dict:
    return {"name": name, "gender": gender, "kind": kind, "preset": preset}


def both(name: str, kind: str = INDIVIDUAL, *, preset: str | None = None) -> list[dict]:
    return [
        ev(f"Men's {name}", MEN, kind, preset=preset),
        ev(f"Women's {name}", WOMEN, kind, preset=preset),
    ]


def sport(
    key: str,
    label: str,
    federation: str,
    federation_name: str,
    season: str,
    preset: str,
    disciplines: list[dict],
    *,
    round_format: str,
    medal_type: str = STANDARD,
    note: str = "",
) -> dict:
    return {
        "key": key,
        "label": label,
        "federation": federation,
        "federation_name": federation_name,
        "season": season,
        "preset": preset,
        "round_format": round_format,
        "medal_type": medal_type,
        "note": note,
        "disciplines": disciplines,
    }


def disc(name: str, events: list[dict], *, preset: str | None = None, **extra) -> dict:
    return {"name": name, "events": events, "preset": preset, **extra}


SUMMER = [
    sport(
        "aquatics",
        "Aquatics",
        "World Aquatics",
        "World Aquatics",
        "summer",
        "swimming",
        [
            disc(
                "Swimming",
                [
                    *both("100 m freestyle"),
                    *both("200 m freestyle"),
                    *both("100 m backstroke"),
                    *both("100 m breaststroke"),
                    *both("100 m butterfly"),
                    *both("200 m individual medley"),
                    *both("4 x 100 m freestyle relay", TEAM),
                    ev("Mixed 4 x 100 m medley relay", MIXED, TEAM),
                ],
                preset="swimming",
                round_format="heats_semis_final",
            ),
            disc(
                "Diving",
                [
                    *both("10 m platform"),
                    *both("3 m springboard"),
                    *both("Synchronised 10 m platform", TEAM),
                ],
                preset="diving",
                round_format="qualification_final",
            ),
            disc(
                "Artistic swimming",
                [ev("Team", OPEN, TEAM), ev("Duet", OPEN, TEAM)],
                preset="artistic_swimming",
                round_format="single_final",
            ),
            disc(
                "Water polo",
                both("Water polo", TEAM),
                preset="water_polo",
                round_format="groups_knockout",
                medal_type=BRONZE_MATCH,
            ),
            disc(
                "Marathon swimming",
                both("10 km"),
                preset="marathon_swimming",
                round_format="single_final",
            ),
        ],
        round_format="heats_semis_final",
    ),
    sport(
        "archery",
        "Archery",
        "WA",
        "World Archery",
        "summer",
        "archery",
        [
            disc(
                "Archery", [*both("Individual"), *both("Team", TEAM), ev("Mixed team", MIXED, TEAM)]
            )
        ],
        round_format="ranking_round_knockout",
        medal_type=BRONZE_MATCH,
        note="Ranking round of 72 arrows, then set-system matches (VERIFY).",
    ),
    sport(
        "athletics",
        "Athletics",
        "WA",
        "World Athletics",
        "summer",
        "athletics_track",
        [
            disc(
                "Track",
                [
                    *both("100 m"),
                    *both("400 m"),
                    *both("1500 m"),
                    *both("110 m / 100 m hurdles"),
                    *both("4 x 100 m relay", TEAM),
                ],
                preset="athletics_track",
                round_format="heats_semis_final",
            ),
            disc(
                "Vertical jumps",
                [*both("High jump"), *both("Pole vault")],
                preset="athletics_field_heights",
                round_format="qualification_final",
            ),
            disc(
                "Horizontal jumps",
                [*both("Long jump"), *both("Triple jump")],
                preset="athletics_field_attempts",
                round_format="qualification_final",
            ),
            disc(
                "Throws",
                [
                    *both("Shot put"),
                    *both("Discus throw"),
                    *both("Hammer throw"),
                    *both("Javelin throw"),
                ],
                preset="athletics_field_attempts",
                round_format="qualification_final",
            ),
            disc(
                "Road",
                [*both("Marathon"), *both("20 km race walk")],
                preset="athletics_road",
                round_format="single_final",
            ),
            disc(
                "Combined events",
                [
                    ev("Men's decathlon", MEN),
                    ev("Women's heptathlon", WOMEN, preset="combined_events_heptathlon"),
                ],
                preset="combined_events_decathlon",
                round_format="single_final",
            ),
        ],
        round_format="heats_semis_final",
    ),
    sport(
        "badminton",
        "Badminton",
        "BWF",
        "Badminton World Federation",
        "summer",
        "badminton",
        [
            disc(
                "Badminton",
                [*both("Singles"), *both("Doubles", TEAM), ev("Mixed doubles", MIXED, TEAM)],
            )
        ],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "baseball_softball",
        "Baseball / softball",
        "WBSC",
        "World Baseball Softball Confederation",
        "summer",
        "baseball",
        [
            disc("Baseball", [ev("Men's baseball", MEN, TEAM)], preset="baseball"),
            disc("Softball", [ev("Women's softball", WOMEN, TEAM)], preset="softball"),
        ],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
        note="On the LA 2028 programme.",
    ),
    sport(
        "basketball",
        "Basketball",
        "FIBA",
        "FIBA",
        "summer",
        "basketball",
        [
            disc("Basketball", both("Basketball", TEAM), preset="basketball"),
            disc("3x3 basketball", both("3x3", TEAM), preset="basketball_3x3"),
        ],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "boxing",
        "Boxing",
        "World Boxing",
        "World Boxing (VERIFY governing body)",
        "summer",
        "boxing",
        [
            disc(
                "Boxing",
                [
                    *both("Flyweight"),
                    *both("Featherweight"),
                    *both("Welterweight"),
                    *both("Heavyweight"),
                ],
            )
        ],
        round_format="knockout",
        medal_type=TWO_BRONZE,
    ),
    sport(
        "breaking",
        "Breaking",
        "WDSF",
        "World DanceSport Federation",
        "summer",
        "breaking",
        [disc("Breaking", [ev("B-Boys", MEN), ev("B-Girls", WOMEN)])],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
        note="Paris 2024 only; not on the LA 2028 programme (VERIFY).",
    ),
    sport(
        "canoe",
        "Canoe",
        "ICF",
        "International Canoe Federation",
        "summer",
        "canoe_sprint",
        [
            disc(
                "Canoe sprint",
                [*both("K1 500 m"), *both("C1 1000 m"), *both("K4 500 m", TEAM)],
                preset="canoe_sprint",
                round_format="heats_semis_final",
            ),
            disc(
                "Canoe slalom",
                [*both("K1"), *both("C1")],
                preset="canoe_slalom",
                round_format="qualification_final",
            ),
        ],
        round_format="heats_semis_final",
    ),
    sport(
        "cricket",
        "Cricket",
        "ICC",
        "International Cricket Council",
        "summer",
        "cricket_t20",
        [disc("Cricket (T20)", both("T20", TEAM))],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
        note="On the LA 2028 programme.",
    ),
    sport(
        "cycling",
        "Cycling",
        "UCI",
        "Union Cycliste Internationale",
        "summer",
        "cycling_road",
        [
            disc(
                "Road",
                [*both("Road race"), *both("Time trial", preset="cycling_time_trial")],
                preset="cycling_road",
                round_format="single_final",
            ),
            disc(
                "Track",
                [
                    *both("Sprint", preset="cycling_sprint"),
                    *both("Keirin", preset="cycling_keirin"),
                    *both("Team pursuit", TEAM, preset="cycling_team_pursuit"),
                    *both("Omnium"),
                ],
                preset="cycling_track",
                round_format="heats_semis_final",
            ),
            disc(
                "BMX",
                [*both("BMX racing"), *both("BMX freestyle", preset="bmx_freestyle")],
                preset="bmx",
                round_format="heats_semis_final",
            ),
            disc(
                "Mountain bike",
                both("Cross-country"),
                preset="mountain_bike",
                round_format="single_final",
            ),
        ],
        round_format="single_final",
    ),
    sport(
        "equestrian",
        "Equestrian",
        "FEI",
        "Fédération Equestre Internationale",
        "summer",
        "show_jumping",
        [
            disc(
                "Jumping",
                [ev("Individual jumping", OPEN), ev("Team jumping", OPEN, TEAM)],
                preset="show_jumping",
            ),
            disc(
                "Dressage",
                [ev("Individual dressage", OPEN), ev("Team dressage", OPEN, TEAM)],
                preset="dressage",
            ),
            disc(
                "Eventing",
                [ev("Individual eventing", OPEN), ev("Team eventing", OPEN, TEAM)],
                preset="eventing",
            ),
        ],
        round_format="qualification_final",
        note="Riders of every gender compete together.",
    ),
    sport(
        "fencing",
        "Fencing",
        "FIE",
        "Fédération Internationale d'Escrime",
        "summer",
        "fencing",
        [
            disc(
                "Fencing",
                [
                    *both("Épée individual"),
                    *both("Foil individual"),
                    *both("Sabre individual"),
                    *both("Épée team", TEAM, preset="fencing_team"),
                ],
            )
        ],
        round_format="pools_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "flag_football",
        "Flag football",
        "IFAF",
        "International Federation of American Football",
        "summer",
        "flag_football",
        [disc("Flag football", both("Flag football", TEAM))],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
        note="On the LA 2028 programme.",
    ),
    sport(
        "football",
        "Football",
        "FIFA",
        "FIFA",
        "summer",
        "soccer",
        [disc("Football", both("Football", TEAM))],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "golf",
        "Golf",
        "IGF",
        "International Golf Federation",
        "summer",
        "golf_stroke",
        [disc("Golf", both("Individual stroke play"))],
        round_format="single_final",
        note="72 holes of stroke play; a playoff decides tied medals (VERIFY).",
    ),
    sport(
        "gymnastics",
        "Gymnastics",
        "FIG",
        "Fédération Internationale de Gymnastique",
        "summer",
        "gymnastics_artistic",
        [
            disc(
                "Artistic",
                [
                    *both("All-around"),
                    *both("Team", TEAM),
                    ev("Men's floor", MEN),
                    ev("Women's beam", WOMEN),
                ],
                preset="gymnastics_artistic",
            ),
            disc(
                "Rhythmic",
                [ev("Individual all-around", WOMEN), ev("Group all-around", WOMEN, TEAM)],
                preset="gymnastics_rhythmic",
            ),
            disc("Trampoline", both("Trampoline"), preset="trampoline"),
        ],
        round_format="qualification_final",
    ),
    sport(
        "handball",
        "Handball",
        "IHF",
        "International Handball Federation",
        "summer",
        "handball",
        [disc("Handball", both("Handball", TEAM))],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "hockey",
        "Hockey",
        "FIH",
        "International Hockey Federation",
        "summer",
        "field_hockey",
        [disc("Hockey", both("Hockey", TEAM))],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "judo",
        "Judo",
        "IJF",
        "International Judo Federation",
        "summer",
        "judo",
        [
            disc(
                "Judo",
                [
                    *both("-60 kg / -48 kg"),
                    *both("-73 kg / -57 kg"),
                    *both("-90 kg / -70 kg"),
                    *both("+100 kg / +78 kg"),
                    ev("Mixed team", MIXED, TEAM),
                ],
            )
        ],
        round_format="repechage_knockout",
        medal_type=TWO_BRONZE,
    ),
    sport(
        "lacrosse",
        "Lacrosse sixes",
        "World Lacrosse",
        "World Lacrosse",
        "summer",
        "lacrosse_sixes",
        [disc("Lacrosse sixes", both("Sixes", TEAM))],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
        note="On the LA 2028 programme.",
    ),
    sport(
        "modern_pentathlon",
        "Modern pentathlon",
        "UIPM",
        "Union Internationale de Pentathlon Moderne",
        "summer",
        "modern_pentathlon",
        [disc("Modern pentathlon", both("Individual"))],
        round_format="qualification_final",
        note="Obstacle discipline replaces riding from LA 2028 (VERIFY).",
    ),
    sport(
        "rowing",
        "Rowing",
        "World Rowing",
        "World Rowing",
        "summer",
        "rowing",
        [
            disc(
                "Rowing",
                [*both("Single sculls"), *both("Double sculls", TEAM), *both("Eight", TEAM)],
            )
        ],
        round_format="heats_repechage_final",
    ),
    sport(
        "rugby_sevens",
        "Rugby sevens",
        "World Rugby",
        "World Rugby",
        "summer",
        "rugby_sevens",
        [disc("Rugby sevens", both("Rugby sevens", TEAM))],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "sailing",
        "Sailing",
        "World Sailing",
        "World Sailing",
        "summer",
        "sailing",
        [
            disc(
                "Sailing",
                [
                    *both("ILCA dinghy"),
                    *both("iQFOiL windsurfing"),
                    ev("Mixed Nacra 17", MIXED, TEAM),
                ],
            )
        ],
        round_format="series_medal_race",
    ),
    sport(
        "shooting",
        "Shooting",
        "ISSF",
        "International Shooting Sport Federation",
        "summer",
        "shooting",
        [
            disc(
                "Shooting",
                [*both("10 m air rifle"), *both("10 m air pistol"), *both("Trap"), *both("Skeet")],
            )
        ],
        round_format="qualification_final",
    ),
    sport(
        "skateboarding",
        "Skateboarding",
        "World Skate",
        "World Skate",
        "summer",
        "skateboarding",
        [disc("Skateboarding", [*both("Street"), *both("Park")])],
        round_format="qualification_final",
    ),
    sport(
        "sport_climbing",
        "Sport climbing",
        "IFSC",
        "International Federation of Sport Climbing",
        "summer",
        "sport_climbing",
        [
            disc(
                "Sport climbing",
                [*both("Boulder and lead"), *both("Speed", preset="climbing_speed")],
            )
        ],
        round_format="qualification_final",
    ),
    sport(
        "squash",
        "Squash",
        "WSF",
        "World Squash Federation",
        "summer",
        "squash",
        [disc("Squash", both("Singles"))],
        round_format="knockout",
        medal_type=BRONZE_MATCH,
        note="On the LA 2028 programme.",
    ),
    sport(
        "surfing",
        "Surfing",
        "ISA",
        "International Surfing Association",
        "summer",
        "surfing",
        [disc("Surfing", both("Shortboard"))],
        round_format="heats_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "table_tennis",
        "Table tennis",
        "ITTF",
        "International Table Tennis Federation",
        "summer",
        "table_tennis",
        [
            disc(
                "Table tennis",
                [*both("Singles"), *both("Team", TEAM), ev("Mixed doubles", MIXED, TEAM)],
            )
        ],
        round_format="knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "taekwondo",
        "Taekwondo",
        "World Taekwondo",
        "World Taekwondo",
        "summer",
        "taekwondo",
        [
            disc(
                "Taekwondo",
                [*both("-58 kg / -49 kg"), *both("-68 kg / -57 kg"), *both("+80 kg / +67 kg")],
            )
        ],
        round_format="repechage_knockout",
        medal_type=TWO_BRONZE,
    ),
    sport(
        "tennis",
        "Tennis",
        "ITF",
        "International Tennis Federation",
        "summer",
        "tennis",
        [
            disc(
                "Tennis",
                [*both("Singles"), *both("Doubles", TEAM), ev("Mixed doubles", MIXED, TEAM)],
            )
        ],
        round_format="knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "triathlon",
        "Triathlon",
        "World Triathlon",
        "World Triathlon",
        "summer",
        "triathlon",
        [disc("Triathlon", [*both("Individual"), ev("Mixed relay", MIXED, TEAM)])],
        round_format="single_final",
    ),
    sport(
        "volleyball",
        "Volleyball",
        "FIVB",
        "Fédération Internationale de Volleyball",
        "summer",
        "volleyball",
        [
            disc("Volleyball", both("Volleyball", TEAM), preset="volleyball"),
            disc("Beach volleyball", both("Beach volleyball", TEAM), preset="beach_volleyball"),
        ],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "weightlifting",
        "Weightlifting",
        "IWF",
        "International Weightlifting Federation",
        "summer",
        "weightlifting",
        [
            disc(
                "Weightlifting",
                [*both("-61 kg / -49 kg"), *both("-89 kg / -71 kg"), *both("+102 kg / +81 kg")],
            )
        ],
        round_format="single_final",
    ),
    sport(
        "wrestling",
        "Wrestling",
        "UWW",
        "United World Wrestling",
        "summer",
        "wrestling",
        [
            disc("Freestyle", [*both("Freestyle -57 kg"), *both("Freestyle -74 kg")]),
            disc("Greco-Roman", [ev("Greco-Roman -67 kg", MEN), ev("Greco-Roman -87 kg", MEN)]),
        ],
        round_format="repechage_knockout",
        medal_type=TWO_BRONZE,
    ),
]

WINTER = [
    sport(
        "alpine_skiing",
        "Alpine skiing",
        "FIS",
        "International Ski and Snowboard Federation",
        "winter",
        "alpine_single_run",
        [
            disc("Speed", [*both("Downhill"), *both("Super-G")], preset="alpine_single_run"),
            disc("Technical", [*both("Giant slalom"), *both("Slalom")], preset="alpine_two_runs"),
            disc(
                "Team",
                both("team combined", TEAM),
                preset="alpine_two_runs",
            ),
        ],
        round_format="multi_run",
    ),
    sport(
        "biathlon",
        "Biathlon",
        "IBU",
        "International Biathlon Union",
        "winter",
        "biathlon",
        [
            disc(
                "Biathlon",
                [
                    *both("Sprint"),
                    *both("Pursuit", preset="biathlon_mass"),
                    *both("Individual", preset="biathlon_individual"),
                    *both("Mass start", preset="biathlon_mass"),
                    *both("Relay", TEAM, preset="biathlon_mass"),
                    ev("Mixed relay", MIXED, TEAM, preset="biathlon_mass"),
                ],
            )
        ],
        round_format="single_final",
    ),
    sport(
        "bobsleigh",
        "Bobsleigh",
        "IBSF",
        "International Bobsleigh and Skeleton Federation",
        "winter",
        "sliding",
        [
            disc(
                "Bobsleigh",
                [
                    ev("Two-man", MEN, TEAM),
                    ev("Four-man", MEN, TEAM),
                    ev("Women's monobob", WOMEN),
                    ev("Two-woman", WOMEN, TEAM),
                ],
            ),
            disc("Skeleton", both("Skeleton")),
        ],
        round_format="multi_run",
    ),
    sport(
        "cross_country",
        "Cross-country skiing",
        "FIS",
        "International Ski and Snowboard Federation",
        "winter",
        "cross_country",
        [
            disc(
                "Cross-country",
                [
                    *both("Sprint", preset="cross_country_mass"),
                    *both("10 km"),
                    *both("Mass start", preset="cross_country_mass"),
                    *both("Relay", TEAM, preset="cross_country_mass"),
                ],
            )
        ],
        round_format="heats_semis_final",
    ),
    sport(
        "curling",
        "Curling",
        "World Curling",
        "World Curling",
        "winter",
        "curling",
        [disc("Curling", [*both("Curling", TEAM), ev("Mixed doubles", MIXED, TEAM)])],
        round_format="round_robin_knockout",
        medal_type=BRONZE_MATCH,
    ),
    sport(
        "figure_skating",
        "Figure skating",
        "ISU",
        "International Skating Union",
        "winter",
        "figure_skating",
        [
            disc(
                "Figure skating",
                [
                    *both("Singles"),
                    ev("Pairs", MIXED, TEAM),
                    ev("Ice dance", MIXED, TEAM),
                    ev("Team event", MIXED, TEAM, preset="figure_skating_team"),
                ],
            )
        ],
        round_format="short_free",
    ),
    sport(
        "freestyle",
        "Freestyle skiing and snowboard",
        "FIS",
        "International Ski and Snowboard Federation",
        "winter",
        "freestyle_judged",
        [
            disc(
                "Freestyle skiing",
                [
                    *both("Moguls", preset="freestyle_moguls"),
                    *both("Aerials", preset="freestyle_aerials"),
                    *both("Slopestyle"),
                    *both("Halfpipe"),
                    *both("Ski cross", preset="ski_cross"),
                ],
                preset="freestyle_judged",
            ),
            disc(
                "Snowboard",
                [
                    *both("Halfpipe"),
                    *both("Big air", preset="freestyle_big_air"),
                    *both("Snowboard cross", preset="ski_cross"),
                    *both("Parallel giant slalom", preset="parallel_giant_slalom"),
                ],
                preset="freestyle_judged",
            ),
        ],
        round_format="qualification_final",
    ),
    sport(
        "ice_hockey",
        "Ice hockey",
        "IIHF",
        "International Ice Hockey Federation",
        "winter",
        "ice_hockey",
        [disc("Ice hockey", both("Ice hockey", TEAM))],
        round_format="groups_knockout",
        medal_type=BRONZE_MATCH,
        note=(
            "Olympic group stage: 3 for a regulation win, 2 for an overtime or shoot-out "
            "win, 1 for an overtime or shoot-out loss, 0 for a regulation loss (VERIFY)."
        ),
    ),
    sport(
        "luge",
        "Luge",
        "FIL",
        "International Luge Federation",
        "winter",
        "luge",
        [
            disc(
                "Luge",
                [
                    *both("Singles"),
                    ev("Doubles", OPEN, TEAM, preset="luge_doubles"),
                    ev("Team relay", MIXED, TEAM, preset="luge_relay"),
                ],
            )
        ],
        round_format="multi_run",
    ),
    sport(
        "nordic_combined",
        "Nordic combined",
        "FIS",
        "International Ski and Snowboard Federation",
        "winter",
        "nordic_combined",
        [
            disc(
                "Nordic combined",
                [
                    ev("Individual normal hill", MEN),
                    ev("Individual large hill", MEN),
                    ev("Team", MEN, TEAM),
                ],
            )
        ],
        round_format="single_final",
    ),
    sport(
        "short_track",
        "Short track speed skating",
        "ISU",
        "International Skating Union",
        "winter",
        "short_track",
        [
            disc(
                "Short track",
                [*both("500 m"), *both("1000 m"), *both("1500 m"), ev("Mixed relay", MIXED, TEAM)],
            )
        ],
        round_format="heats_semis_final",
    ),
    sport(
        "ski_jumping",
        "Ski jumping",
        "FIS",
        "International Ski and Snowboard Federation",
        "winter",
        "ski_jumping",
        [
            disc(
                "Ski jumping",
                [
                    *both("Normal hill"),
                    ev("Men's large hill", MEN, preset="ski_jumping_large"),
                    ev("Mixed team", MIXED, TEAM),
                ],
            )
        ],
        round_format="qualification_final",
    ),
    sport(
        "ski_mountaineering",
        "Ski mountaineering",
        "ISMF",
        "International Ski Mountaineering Federation",
        "winter",
        "ski_mountaineering",
        [disc("Ski mountaineering", [*both("Sprint"), ev("Mixed relay", MIXED, TEAM)])],
        round_format="heats_semis_final",
        note="New for Milano Cortina 2026.",
    ),
    sport(
        "speed_skating",
        "Speed skating",
        "ISU",
        "International Skating Union",
        "winter",
        "speed_skating",
        [
            disc(
                "Speed skating",
                [
                    *both("500 m"),
                    *both("1500 m"),
                    *both("5000 m / 3000 m"),
                    *both("Mass start", preset="speed_skating_mass_start"),
                    *both("Team pursuit", TEAM),
                ],
            )
        ],
        round_format="single_final",
    ),
]


def preset_for(sport_row: dict, discipline: dict, event: dict | None = None) -> str:
    return (event or {}).get("preset") or discipline.get("preset") or sport_row["preset"]


def all_sports() -> list[dict]:
    return [*SUMMER, *WINTER]


def find_sport(key: str) -> dict | None:
    return next((row for row in all_sports() if row["key"] == key), None)


def event_key(sport_key: str, discipline: str, event_name: str) -> str:
    return f"{sport_key}|{discipline}|{event_name}"
