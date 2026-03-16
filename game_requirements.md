[=] Project Instructions: Alien Cargo [=]

[-] Core Application Architecture & UI Rules (Not sent to LLM) [-]

* **App Concept**: Alien Cargo is a game generator. The index page features a "Describe your game..." textarea and a "Create Game" button.
* It sends an LLM generation request to the external microservice 'AIManager' (using `claude-sonnet-4-5-20250929` for cost efficiency)
to receive a single HTML/JS page containing a fully playable game.
* **Grid Layout & View Toggling**:
* Divide the screen into a strict 32-column CSS grid enforced via JavaScript. Ensure elements explicitly stay on `gridRow = '1'` to prevent vertical wrapping bugs.
* Implement a full-height (100vh) toggle button spanning 1/32 of the width.
* When in **Prompt View**, the button occupies column 32 (far right, labeled `<`), and the prompt area occupies columns 1-31.
* When in **Game View**, the button occupies column 1 (far left, labeled `>`), and the game area occupies columns 2-32.

* **Game Canvas Display**: The game `iframe` must contain an 800x450 centered canvas within the full browser view (100vh/100vw),
including 16px margins and 16px padding to prevent clipping.
* **Generation Lifecycle**:
* Show a progress bar while the API request processes. Track and calculate completion time locally using a JSON storage file (`generation_times.json`) to provide an accurate,
faked progress animation based on the user's historical average.
* Upon successful generation, automatically toggle the UI to the Game View.
* Immediately apply `.focus()` to the game `iframe` once it loads so keyboard event listeners (like "Enter to Start") work without requiring an initial mouse click.
*
Whether mobile or desktop we use a 16:9 wide profile. Virtual gamepad for mobile it is essentially a mini version of desktop.

[-] Instructions Sent to the LLM (Prompt Payload - applies to all game types) [-]

----
Output EXCLUSIVELY valid HTML containing all necessary CSS and JavaScript within it. Do not include markdown formatting tags like ```html.
Keep code around 1000 lines max (~4000 tokens).
Do NOT load external images, audio, or libraries. STRICTLY FORBIDDEN: Do NOT use `localStorage` or `sessionStorage`.

Controls Desktop:
Arrow keys to move (if applicable).
WASD to move for a second player (if applicable).
Space to shoot.
Require hitting "Enter" OR a specific "Mouse Click" on the canvas to start the game.

Controls Mobile - Virtual Gamepad:
Generate an on-screen virtual gamepad for mobile devices.
Split the mobile screen into a grid of 2 rows and 3 columns.
Place a D-pad/Arrow pad in section 4 (bottom-left area).
Place Mega Drive-style A, B, C buttons in section 6 (bottom-right area).

Games must always feature a distinct Game Over state and a clickable "Restart/Go Again" button if a player is killed.

Use CSS flex and JavaScript enforcement to accurately position these elements.
----


First determine whether the game will be a 2d scroller type game in which case we use Phaser, or a 3D game i.e. Starfox space shooter in which case use ThreeJS
Then we have the following 'experts',

[Platform Game]

**Core Mechanics & Physics**
The engine must prioritize "Game Feel" via a variable jump height (holding the button jumps higher) and "Coyote Time"
(allowing a jump for a few frames after leaving a platform).
Movement should use basic acceleration and friction rather than instant stops.
The collision system must handle "one-way" platforms and sloped terrain.

**Level Structure & Progression**
Aim for a "World" system: 4 Worlds, each containing 4 Levels (16 total).

* **Level Length:** 90–120 seconds of gameplay.
* **Difficulty Curve:** Introduce a new mechanic (e.g., moving platforms) in Level 1-1, combine it with hazards in 1-2, and master it by 1-4.
* **Bosses:** Every 4th level features a "Rule of Three" boss. The player must dodge patterns and strike the boss three times during vulnerable states to win.

**Entities & Hazards**

* **Enemies:** Include "Patrollers" (turn at edges), "Jumpers" (timed vertical movement), and "Projectiles" (fixed-rate turrets). Enemies are defeated by jumping on their heads or using power-ups.
* **Power-ups:** Include a "Growth" item (extra hit point), a "Projectile" item (ability to shoot), and a rare "Invincibility" star.
* **Collectibles:** Scatter 50–100 coins per level for score, plus 3 "Hidden Medals" for completionists.

**Technical Implementation**
Use a "State Machine" for the player: Idle, Run, Jump, Fall, Hurt, and Die.
Use a Tilemap system (e.g., Tiled) for levels rather than hard-coding coordinates.
For browser performance, use a fixed timestep (60fps) to ensure physics remain consistent across different monitor refresh rates.

[Racing game]

Core Mechanics & PhysicsThe engine relies on fake 3D (raster projection) rather than true 3D space. The player's car sprite remains locked in the lower-center of the screen; steering actually shifts the road and world laterally relative to the car. Implement acceleration, top speed, and deceleration. Crucially, apply a centrifugal force system: when the track curves, the player's car must be pushed toward the outside edge of the curve proportional to their speed, forcing the player to counter-steer.Track Rendering (The "Pseudo-3D" Effect)Construct the track using a 1D array of "Segments." Each segment holds data for its curve magnitude, elevation (hills), and attached scenery sprites.Raster Drawing: Iterate through the track segments within the camera's draw distance from back to front (Painter’s Algorithm).Perspective Projection: Calculate the screen Y-coordinate and scale factor based on $1/Z$ (distance). Draw the road by rendering horizontal polygons (trapezoids) from the bottom of the screen to the horizon.Speed Illusion: Alternate road and grass colors (e.g., light/dark gray, light/dark green) every few segments. Scrolling through these segments creates the illusion of forward momentum.Game Structure & ProgressionDesign a continuous environment with branching paths.Time Attack: The core loop relies on a countdown timer. The player starts with 60 seconds. Reaching a checkpoint fork grants a time extension.Traffic: Populate the road with slower-moving AI cars. Collisions should drastically kill the player's speed and push them to the side, rather than destroying the car.

[R-type style space shooter]

Core Mechanics & The "Force" Pod
The game relies on forced horizontal auto-scrolling; the background and terrain constantly move left, simulating forward flight. The player ship has 8-way movement but is strictly clamped to the screen boundaries.
Crucially, implement two signature mechanics:

Charge Beam: Tapping fire shoots rapid, weak lasers, but holding the button charges a meter. Releasing it fires a massive, piercing beam that damages multiple enemies.

The Satellite Pod: A collectible, indestructible companion orb. It can attach to the front or rear of the player's ship to block incoming bullets and fire its own weapons. It can also be launched forward to lodge into enemies and act as an autonomous turret.

Level Structure & Entities
Unlike open-space shooters, the level geometry itself is a primary hazard.

Terrain: Players must navigate tight corridors, moving walls, and indestructible structures. Touching terrain results in instant death.

Enemy Waves: Spawn enemies deterministically based on the camera's X-coordinate. Use diverse behaviors: weak swarmers, heavily-armored stationary turrets, and ships that ambush from the left side of the screen.

Bosses: End stages with screen-filling, multi-segmented bosses. They should have specific, isolated weak points and unleash complex, sweeping bullet patterns.

[1v1 beat em up like street fighter]

Core Mechanics & State Machine
Characters must operate on a strict, frame-deterministic State Machine (Idle, Walk, Crouch, Jump, Attack, Block, Hitstun, Knockdown). Movement is deliberate: unlike platformers, jumps have committed, fixed arcs with no mid-air steering. The camera must strictly track the midpoint between the two players, clamping their movement so they cannot walk past the screen edges. Implement a 99-second round timer and a best-of-three round system.

Collision: Hitboxes & Hurtboxes
Do not use standard monolithic physics bodies for collisions. The engine must use a dual-box system:

Hurtboxes: The vulnerable areas mapping the character's body.

Hitboxes: The damage-dealing areas spawned only during specific frames of an attack.
When a Hitbox intersects the opponent's Hurtbox, a strike occurs. Crucially, implement Pushback: successful hits or blocks must physically push both characters apart to maintain spacing and prevent sprite overlapping.

Combat & Frame Data
Every attack must be explicitly divided into three phases: Startup (vulnerable wind-up), Active (hitboxes generated), and Recovery (vulnerable cool-down).

Hitstun & Blockstun: Taking a hit temporarily freezes the defender's state. If the Hitstun duration exceeds the attacker's Recovery time, a "Combo" is mathematically possible.

Defense: Holding away from the opponent triggers a Block. High blocks defend aerial and standing attacks; low blocks (down-back) defend crouching attacks.

Input Buffering
Do not read inputs as instant events. Maintain a rolling "Input Buffer" array tracking the last 30 frames of joystick/keyboard states. The engine must scan this buffer to detect sequential motion inputs (e.g., Down, Down-Forward, Forward + Punch) to trigger Special Moves like projectiles.

[Final Fight style beat em up]

Core Mechanics & The "Belt Scroll" Perspective
The game uses a faux-3D "belt scroll" system. Characters move along three axes simulated in 2D: X (horizontal), Y (depth into the background), and Z (vertical jumping).

Depth Collision: A crucial mechanic is that attacks must only connect if characters share a similar Y-depth (within a small pixel threshold).

Combat System: Implement a standard 3-hit combo triggered by rapid button presses. Include a Jump Kick, a Close-Range Grab/Throw (triggered automatically when walking directly into an enemy's hitbox), and a "Desperation Attack" that knocks back all surrounding enemies at the cost of a small chunk of the player's own health.

Level Structure & Progression
The camera scrolls right but relies on a strict "Lock and Clear" pacing system.

Wave Spawning: The camera stops scrolling when a trigger line is crossed, locking the screen boundaries. The player must defeat all spawned enemies before a flashing "GO!" arrow permits further forward movement.

Stages: Design 4 to 6 distinct environments (e.g., Slums, Subway, Elevator). End each stage with a Boss possessing a massive health bar, "super armor" (cannot be interrupted during certain wind-ups), and unique area-denial attacks.

Entities & Interactive Objects

Enemy Archetypes: "Grunts" (basic melee), "Weapon Users" (pipes/knives with disjointed hitboxes), and "Chargers" (quick horizontal dash attacks). The AI director should restrict aggression so only 2 or 3 enemies actively attack the player at once, while others circle.

Breakables: Place destructible crates containing score items or health-restoring "Food."

[Starfox style 3d shooter]

Core Mechanics & The "Rail" System
The game is a forced-scrolling 3D "rail shooter." The camera and the player's base pivot point move continuously forward along the global Z-axis at a constant speed. The player controls the ship's local X (horizontal) and Y (vertical) offsets within a strict invisible bounding box on the screen to dodge obstacles and aim.

Game Feel: When the player moves, the 3D ship model must visibly pitch and roll in the direction of movement, smoothly interpolating back to center when input ceases.

The Barrel Roll: Implement a quick lateral dash (triggered by double-tapping a direction) that grants brief invincibility frames and deflects minor projectiles.

Combat & Targeting

Weapons: Equip the ship with rapid-fire primary lasers and a limited inventory of "Bombs" that deal massive area-of-effect damage.

Aiming: Project a 2D crosshair at a fixed distance ahead of the ship. Projectiles should travel from the ship's nose directly toward this reticle.

Enemies: Spawn enemy waves using Z-axis distance triggers. Enemies should follow predetermined sweeping flight paths (Bezier curves) rather than complex reactive AI.

Level Structure & Bosses
Create a localized stage filled with static environmental hazards (arches, asteroids, closing doors). The level culminates in a Boss Fight. During the boss encounter, the forward "rail" scrolling halts, trapping the player and the boss in a fixed Z-depth arena until the boss's multi-stage weak points are destroyed.

[Doom style fake 3d shooter]

Core Mechanics & The Raycaster
The game environment is fundamentally a 2D top-down grid, but it is rendered in first-person using Raycasting. For every vertical pixel column on the screen (e.g., 1280 columns), cast a ray from the player's position outward within a 60-degree Field of View (FOV). Step the ray forward until it intersects a solid grid cell. The distance to this intersection determines the height of the vertical line drawn on screen. Crucial: You must multiply the distance by the cosine of the angle relative to the player's facing direction to eliminate the spherical "fish-eye" distortion effect.

Entities & Billboard Sprites
Enemies, weapons, and decorations are not 3D models; they are 2D "Billboard" sprites scaled based on their distance from the player. To ensure sprites are properly hidden behind walls, implement a 1D Z-Buffer: an array storing the wall distance for every screen column. When rendering a sprite, only draw its vertical pixel strips if its distance is closer to the camera than the value stored in the Z-Buffer for that specific column.

Combat & AI
Player weapons should primarily be "Hitscan" (e.g., pistols, shotguns): when the player fires, simply cast a single ray straight forward to instantly check if an enemy bounding box is hit before a wall is. Enemy AI operates entirely on the 2D grid, relying on basic line-of-sight raycasts to determine if they can see the player to shoot or chase them.

[Chrono Trigger style RPG Game]

The game uses a 2D top-down perspective with tile-based maps. Crucially, eliminate "random encounters." Enemies must be visible roaming the map. When the player collides with an enemy or crosses an invisible trigger line, do not load a separate battle screen. Instead, smoothly lock the camera, slide in the combat UI overlays, and transition into battle directly on the current exploration map.

Combat: ATB and Techs
Implement an Active Time Battle (ATB) system rather than strict turn-based combat. Every character and enemy has an internal timer that fills at a rate dictated by their "Speed" stat.

Spatial Attacks: Because battles happen on the map, character and enemy positioning matters. Implement Area of Effect (AoE) logic for "Techs" (skills): some attacks should damage enemies within a radial circle, while others strike all enemies caught in a straight line between the attacker and the target.

Combo System: Implement "Dual/Triple Techs." If two (or three) specific party members both have full ATB gauges simultaneously, they can expend their turns and Magic Points (MP) together to unleash a powerful combined attack.

State Management & Progression
The engine needs a robust global state manager to track "Story Flags" and inventory. Design an Overworld map (a zoomed-out, scaled-down version of the world) to connect distinct Town and Dungeon tilemaps. Implement a branching dialogue system that pauses NPC movement and AI when a text box is active.

[Silent Hill style game]

Core Mechanics & Atmosphere
The game prioritizes tension, puzzle-solving, and exploration over action. Implement two signature sensory mechanics:

The Flashlight: The environment is naturally bathed in oppressive darkness or fog. The player's primary tool is a pocket flashlight that casts a harsh, narrow cone of light, illuminating only what is directly in front of them while leaving the periphery unseen.

The Radio: A static-emitting radio acts as a crude early-warning system. As hidden enemies get closer, the auditory static grows louder and more frantic, building dread before the physical threat is even visible.

Camera & Controls
Replicate the classic PS1/PS2 era feel using "Tank Controls": pressing Up moves the character forward relative to their own facing direction, while Left/Right rotates them. Pair this with a system of Fixed Camera Volumes. Instead of a free-look camera, define invisible trigger zones in the environment that snap the camera to predefined, cinematic angles that track the player, deliberately obscuring what lies around the next corner.

Combat & Entities
Combat should feel deliberately heavy, clunky, and desperate. Use simple placeholder animations for a slow melee swing (e.g., a steel pipe) and a firing stance. Enemies should feature erratic, twitchy movement logic. They should also react to the flashlight—turning it off might allow the player to sneak past them in the dark.





[Other]

If the game appears to be something that does not fit the aforementioned experts, then generate something you see fit.


[LoginManager]
LoginManager is an external microservice that handles user reg/login/jwt and credit management for ecosystem of our various external websites.
Alien Cargo users get 5 free pre-reg and 5 free post-reg credits after which they must purchase more via tiers.html





