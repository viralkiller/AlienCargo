Alien Cargo is a vertical scrolling space shooter (traveling 'up' along the screen).
The ship points North (bottom to top).
View: Top-down with a slight perspective angle to create a 2.5D effect. Think Outrun the racing game perspective, but with a spaceship.

### Coordinates
- **+Z**: Moving Forward (Up the screen)
- **-Z**: Moving Backward (Down the screen)
- **+Y**: Altitude (Distance above the grid surface)
- **-Y**: Descent (Closer to the grid surface)
- **+X/-X**: Lateral movement (Right/Left)

### The Infinite Corridor (Scrolling System)
Since movement is primarily forward (+Z), the world is generated as an **infinite 3-lane corridor**.
- **Lanes**: The universe is strictly tiled into 3 horizontal sectors relative to the ship: Left (-1), Center (0), and Right (1).
- **Generation**: As the ship moves forward in Z, we spawn new rows of these 3 sectors ahead.
- **Garbage Collection**: Strictly cull sectors that fall behind the ship (negative Z relative to ship) to keep memory usage constant.
- **Boundaries**: The ship is confined to this corridor not by hard walls, but by an **exponential repulsion field** (an "invisible magnetic wall") that pushes back harder the further the ship strays from the center.

### The "Liquid" Spacetime Grid
The spacetime grid behaves less like a rigid wireframe and more like a **viscous liquid ocean**.
- **Flow**: The grid texture flows continuously like a river.
- **Gravity Wells**: Planets and Black Holes create deep depressions (dips) in the grid.
- **Whirlpools**: Gravity wells exert a tangential force, creating a **whirlpool effect** where the grid visually spins and flows into the "sink" of the planet/black hole.
- **Waves**: The grid surface undulates with gentle, rolling noise-based waves, and the ship "bobs" on these waves physically.

### Celestial Objects
- **Scale**: Objects are **massive**.
    - **Black Holes**: Huge, screen-spanning whirlpools (Radius ~20-30). They dominate the view and should be spawned slightly off-center so the player can just barely navigate around their event horizon.
    - **Planets**: Large obstacles (Radius ~12-25) that require significant lateral movement to dodge.
- **Satellites**: Planets may have **1-3 orbiting asteroids/moons**. These orbit in a ring around the planet's equator.
- **Asteroids**: Can be smooth or jagged (noise deformed). They orbit locally around planets rather than floating freely in deep space.

### Ship Physics
- **Movement**: Physics-based, using velocity, acceleration, and friction (inertia).
- **Feel**: The ship should feel responsive but have weight. It shouldn't stop instantly (drift).
- **Controls**:
    - **Forward**: Automatic cruise speed with "brake" (Arrow Down) to slow down.
    - **Lateral**: Fast, snappy acceleration (Arrow Left/Right) to dodge the massive obstacles.