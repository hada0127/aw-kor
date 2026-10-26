## Findings

**Confirmed** means supported by a public source; **(unverified)** marks gaps. Research checked 2026-10-26.

### a) Terrain names, IDs, and map RAM

- **Lake / 湖:** The official Japanese GBWA2 terrain guide lists sea (海), shoals (浅瀬), and reefs (岩礁), but no separate lake terrain. “Lake” in AW2 mission guides appears to refer to a body of sea terrain on the map, not a distinct tile type. [Nintendo GBWA2 terrain guide](https://www.nintendo.co.jp/n08/bgwj/unit2/subwin1/landform.html) — official.
- **Pipe:** The Japanese guide distinguishes impassable pipe (パイプ) from breakable pipe seam (パイプ(継ぎ目)). [Nintendo GBWA2 terrain guide](https://www.nintendo.co.jp/n08/bgwj/unit2/subwin1/landform.html) — official.
- **Cannons and lasers:** The Japanese names are キャノン砲 (cannon), ミニキャノン砲 (mini cannon), レーザー砲 (laser cannon), and ヘルレーザー (Hell Laser). The regular laser fires in a cross and can hit either side; Hell Laser fires forward and does not damage its own side. [Nintendo GBWA2 terrain guide](https://www.nintendo.co.jp/n08/bgwj/unit2/subwin1/landform.html) — official.
- **“A laser”:** I found no separate “A laser” terrain name in the official list. The likely match is ヘルレーザー, the forward-firing superweapon, but interpreting the project’s label as that is **(unverified)**. [Nintendo GBWA2 terrain guide](https://www.nintendo.co.jp/n08/bgwj/unit2/subwin1/landform.html) — official.
- **Numeric terrain IDs:** I did not find a public authoritative tile-ID table for AW2E or the Japanese compilation. The AW2 map editor documents special terrain handling, but not numeric game IDs. [awsmaped project notes](https://github.com/joaofrancese/awsmaped) — secondary.
- **AW2E map RAM address/format and JP translation:** **(unverified)**. I found an AW2E RAM map index, but its page did not expose an address or buffer format in the retrieved material. The Japanese compilation’s corresponding RAM layout was not established. [NeoROMhacking AW2 page](https://neoromhacking.net/gamepage.php?id=934) — secondary.

### b) Missions with relevant terrain and HQ-capture losses

- **Duty & Honor:** Kanbei vs. Adder; two cross-firing laser cannons near the player’s western starting area. The quick route is to push north toward the ten Yellow Comet cities while avoiding the lasers’ firing lines; Adder capturing all ten causes defeat. [GameSpot walkthrough](https://www.gamespot.com/articles/advance-wars-2-black-hole-rising-walkthrough/1100-6072205/) — secondary; [GameFAQs walkthrough](https://gamefaqs.gamespot.com/gba/589391-advance-wars-2-black-hole-rising/faqs/24123) — secondary.
- **Andy’s Time:** Andy vs. Flak; introduces a Black Cannon. The guide recommends taking neutral factories and attacking the cannon from range. [GameFAQs walkthrough](https://gamefaqs.gamespot.com/gba/589391-advance-wars-2-black-hole-rising/faqs/24123) — secondary.
- **Drake’s Dilemma:** Drake and Kanbei vs. Hawke; has two Black Cannons and a large lake used by naval units. The guide describes a quick opening using submarines to scout and battleships to attack exposed units, then advancing toward the cannons. [GameFAQs walkthrough](https://gamefaqs.gamespot.com/gba/589391-advance-wars-2-black-hole-rising/faqs/24123) — secondary.
- **Show Stopper:** Sonja vs. Lash; lasers appear in a fog-of-war mission. **(Unverified: route details not extracted.)** [Advance Wars campaign mission category](https://advancewars.fandom.com/wiki/Category%3AAdvance_Wars_2_Campaign) — secondary.
- **Final Front / final campaign mission:** Sources mention a Hell Laser/Deathray and Black Hole cannons. **(Unverified: exact mission terrain and fastest route not extracted.)** [GameFAQs walkthrough](https://gamefaqs.gamespot.com/gba/589391-advance-wars-2-black-hole-rising/faqs/24123) — secondary.
- **Enemy HQ capture:** The walkthrough warns that HQ capture can cause loss and gives an example where Lash sends infantry toward Sami’s HQ. It also describes an HQ-recapture objective in **Liberation** (Grit vs. Lash). This establishes that HQ capture is a relevant defeat condition in at least some missions, but I did not locate a complete mission list or exact campaign-specific defeat dialogue. **(Unverified.)** [GameFAQs walkthrough](https://gamefaqs.gamespot.com/gba/589391-advance-wars-2-black-hole-rising/faqs/24123) — secondary.

### c) Hidden CO unlocks and save bits

- The AW2 guide reports that COs are purchased through Hachi’s Battle Maps after meeting unlock conditions. Nell unlocks after the Normal Campaign; Hachi after the Hard Campaign and buying his other items; Sturm after an S average in Normal or Hard Campaign. Other CO unlocks are generally tied to completing their army’s campaign. [GameFAQs secrets section](https://gamefaqs.gamespot.com/gba/589391-advance-wars-2-black-hole-rising/faqs/24123) — secondary. Exact conditions for each CO and whether the Japanese compilation differs are **(unverified)**.
- The requested save-data bits were not established from public sources. A forum post gives RAM cheat addresses for an AW2 hack, not persistent save flags; those should not be treated as save-data offsets. [AW2 hack discussion](https://www.reddit.com/r/Advance_Wars/comments/gyjsfr) — secondary.

### d) mGBA link support and AW2 link requirements

- Upstream mGBA lists link-cable support as **partial**; its FAQ does not establish that 0.10.x standalone can link two headless instances. Therefore the specific “two headless instances” capability is **(unverified)**. [mGBA FAQ](https://mgba.io/faq.html) — official.
- A separate mGBA fork, **mGBA Splitscreen**, documents two to four linked instances in one core, including per-player ROMs. This is a fork, not evidence about upstream mGBA 0.10.x. [mGBA Splitscreen project](https://github.com/Spuds0588/mgba-splitscreen) — secondary.
- AW2’s guide says Link Mode connects 2–4 GBAs by cable and can also play certain maps with players who lack the game. The official manual distinguishes **Multi-Pack Link Mode** and refers to it separately from other link features. Whether AW2 link battles specifically require multiple game paks, and whether single-pak play is supported for those battles, remains **(unverified)**. [GameFAQs walkthrough](https://gamefaqs.gamespot.com/gba/589391-advance-wars-2-black-hole-rising/faqs/24123) — secondary; [Nintendo AW2 manual](https://www.nintendo.com/eu/media/downloads/games_8/emanuals/game_boy_advance_8/Manual_GameBoyAdvance_AdvanceWars2BlackHoleRising_EN_DE_FR_ES_IT.pdf) — official.

RECEIPT: model=unknown effort=unknown role=research-external