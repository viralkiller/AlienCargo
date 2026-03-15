Here is what we need:
Alien Cargo is a game generator. The index page consists of a textarea "describe your game" and also a "Create Game" button.
We then send an LLM gen request to external microservice 'AIManager' to get a single HTML/JS page containing the game, and allow the user to instantly
access this page and play the game.

These should be core rules and not a part of the instructions sent to the LLM model:
800x450 centered canvas within the full browser view 100vh 100vw, with 16px margin and 16px padding, so things dont get cut off.
A tall < button on the very left edge that allows us to switch between the 'Game creation prompt' area and the actual game.
Imagine we divide the screen into 32 columns only, this tall button will occupy section 1, spanning 100vh and 1/32th wide (while in the game area)
clicking it will cause this button to then occupy section 32, the very right column, spanning again 100vh 1/32 wide. So it toggles between section 1 - far left and
section 32 for right.



Part of instructions to LLM:
Arrow keys to move if applicable, WASD for second player if applicable.
Enter to start game.
Space to shoot.
Games should always have a Restart/Go again button if a player gets killed (you were so close go again?)
Try and keep game code around 1000 lines max. Around 4000 tokens.
For mobile we will generate a 'virtual gamepad', arrow pad on the bottom left corner and mega drive style A,B,C buttons bottom right corner.
Imagine we split the screen into two rows and 3 columns, arrow pad will be in section 4 (going left to right, top to bottom, starting at the left on new row)
The buttons will be in section 6.
Use CSS flex and JS enforcement to get things exactly where we want them.

