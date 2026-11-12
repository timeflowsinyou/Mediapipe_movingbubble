import pygame
import random
import sys
import cv2
import numpy as np
import mediapipe as mp
import mss
import time
import math
import ctypes


# ============================================================
# Initialize pygame
# ============================================================

pygame.init()


# ============================================================
# Select Bubble display
# ============================================================

num_displays = pygame.display.get_num_displays()
desktop_sizes = pygame.display.get_desktop_sizes()

print("Detected displays:", num_displays)
print("Display sizes:", desktop_sizes)


# Use second monitor if available
if num_displays >= 2:
    BUBBLE_DISPLAY = 1
else:
    BUBBLE_DISPLAY = 0


bubble_width, bubble_height = desktop_sizes[BUBBLE_DISPLAY]

print("Bubble display:", BUBBLE_DISPLAY)
print(
    "Bubble resolution:",
    bubble_width,
    "x",
    bubble_height
)


# ============================================================
# IMPORTANT:
#
# Do NOT use pygame.FULLSCREEN here.
#
# FULLSCREEN can be minimized / pushed behind when focus changes.
#
# Instead:
# create a borderless window covering the entire second screen.
# ============================================================

screen = pygame.display.set_mode(
    (bubble_width, bubble_height),
    pygame.NOFRAME,
    display=BUBBLE_DISPLAY
)

screen_width, screen_height = screen.get_size()

pygame.display.set_caption("Bubble Control")

clock = pygame.time.Clock()


# ============================================================
# Windows: Keep Bubble window always on top
# ============================================================

def keep_window_on_top():

    try:

        hwnd = pygame.display.get_wm_info()["window"]

        HWND_TOPMOST = -1

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040

        ctypes.windll.user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE
            | SWP_NOSIZE
            | SWP_NOACTIVATE
            | SWP_SHOWWINDOW
        )

    except Exception as e:

        print(
            "Could not set window TOPMOST:",
            e
        )


# Set TOPMOST once at startup
keep_window_on_top()


# ============================================================
# Initialize MediaPipe Hands
# ============================================================

mp_hands = mp.solutions.hands

hands = mp_hands.Hands(
    model_complexity=0,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)


# ============================================================
# Screen capture settings
#
# ORIGINAL SETTINGS:
# DO NOT CHANGE
# ============================================================

TARGET_FPS = 30

FRAME_DURATION = 1 / TARGET_FPS


SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 780


monitor_area = {
    "top": 0,
    "left": 0,
    "width": SCREEN_WIDTH,
    "height": SCREEN_HEIGHT
}


# ============================================================
# Gesture settings
# ============================================================

# Short MediaPipe losses are ignored.
#
# Example:
#
# LEFT
# LEFT
# no detection
# no detection
# UP
#
# becomes:
#
# LEFT LEFT LEFT LEFT UP
#
NO_GESTURE_TIMEOUT = 0.6


# ============================================================
# Floating behavior
# ============================================================

# At idle, final speed =
#
# controlled speed * 1/3
#
FLOAT_SPEED_RATIO = 1.0 / 3.0


# How smoothly bubbles slow down.
#
# 0.97 at 30 FPS:
# approximately 1.2 s to reach 1/3 speed.
#
DECELERATION_FACTOR = 0.97


# ============================================================
# Bubble class
# ============================================================

class Bubble:

    def __init__(self):

        # ----------------------------------------------------
        # Size
        # ----------------------------------------------------

        self.size = random.randint(
            25,
            80
        )


        # ----------------------------------------------------
        # Position
        # ----------------------------------------------------

        self.x = random.randint(
            self.size,
            screen_width - self.size
        )

        self.y = random.randint(
            self.size,
            screen_height - self.size
        )


        # ----------------------------------------------------
        # Appearance
        # ----------------------------------------------------

        self.color = (
            random.randint(100, 200),
            random.randint(100, 200),
            random.randint(200, 255),
        )


        self.alpha = random.randint(
            150,
            220
        )


        self.highlight_pos = (
            random.uniform(0.2, 0.8),
            random.uniform(0.1, 0.3)
        )


        # ====================================================
        # Controlled speed
        # ====================================================

        self.speed = 7.5

        self.speed_multiplier = random.uniform(
            0.5,
            1.5
        )


        self.control_speed = (
            self.speed
            * self.speed_multiplier
        )


        # ====================================================
        # Velocity
        # ====================================================

        # Program starts in random floating mode
        angle = random.uniform(
            0,
            2 * math.pi
        )


        initial_float_speed = (
            self.control_speed
            * FLOAT_SPEED_RATIO
        )


        self.vx = (
            math.cos(angle)
            * initial_float_speed
        )

        self.vy = (
            math.sin(angle)
            * initial_float_speed
        )


        # ====================================================
        # Drift state
        # ====================================================

        # True = random floating direction already assigned
        self.random_drift_active = True


    # ========================================================
    # Start controlled movement
    # ========================================================

    def set_control_direction(
        self,
        direction
    ):

        speed = self.control_speed


        # Every valid gesture immediately cancels drift state
        self.random_drift_active = False


        # ----------------------------------------------------
        # LEFT
        # ----------------------------------------------------

        if direction == "left":

            self.vx = -speed
            self.vy = 0


        # ----------------------------------------------------
        # RIGHT
        # ----------------------------------------------------

        elif direction == "right":

            self.vx = speed
            self.vy = 0


        # ----------------------------------------------------
        # UP
        # ----------------------------------------------------

        elif direction == "up":

            self.vx = 0
            self.vy = -speed


        # ----------------------------------------------------
        # DOWN
        # ----------------------------------------------------

        elif direction == "down":

            self.vx = 0
            self.vy = speed


    # ========================================================
    # Idle movement
    # ========================================================

    def update_idle(self):


        # ----------------------------------------------------
        # Target idle speed = 1/3 controlled speed
        # ----------------------------------------------------

        target_speed = (
            self.control_speed
            * FLOAT_SPEED_RATIO
        )


        # ----------------------------------------------------
        # Current speed
        # ----------------------------------------------------

        current_speed = math.sqrt(
            self.vx ** 2
            +
            self.vy ** 2
        )


        # ====================================================
        # Stage 1:
        #
        # Continue in previous direction,
        # but gradually slow down.
        # ====================================================

        if current_speed > target_speed * 1.02:


            self.vx *= DECELERATION_FACTOR
            self.vy *= DECELERATION_FACTOR


            current_speed = math.sqrt(
                self.vx ** 2
                +
                self.vy ** 2
            )


            # Prevent speed from going below target
            if current_speed < target_speed:

                if current_speed > 0:

                    scale = (
                        target_speed
                        /
                        current_speed
                    )

                    self.vx *= scale
                    self.vy *= scale


        # ====================================================
        # Stage 2:
        #
        # Speed reached approximately 1/3.
        #
        # Choose random floating direction.
        # ====================================================

        else:

            if not self.random_drift_active:

                angle = random.uniform(
                    0,
                    2 * math.pi
                )


                self.vx = (
                    math.cos(angle)
                    *
                    target_speed
                )

                self.vy = (
                    math.sin(angle)
                    *
                    target_speed
                )


                self.random_drift_active = True


        # ====================================================
        # Move bubble
        # ====================================================

        self.x += self.vx
        self.y += self.vy


        # ====================================================
        # Bounce from edges
        # ====================================================

        if self.x <= self.size:

            self.x = self.size
            self.vx = abs(self.vx)


        elif self.x >= screen_width - self.size:

            self.x = (
                screen_width
                -
                self.size
            )

            self.vx = -abs(
                self.vx
            )


        if self.y <= self.size:

            self.y = self.size
            self.vy = abs(
                self.vy
            )


        elif self.y >= screen_height - self.size:

            self.y = (
                screen_height
                -
                self.size
            )

            self.vy = -abs(
                self.vy
            )


    # ========================================================
    # Update
    # ========================================================

    def update(
        self,
        global_direction
    ):


        # ====================================================
        # Gesture control
        # ====================================================

        if global_direction is not None:


            self.set_control_direction(
                global_direction
            )


            self.x += self.vx
            self.y += self.vy


            # -----------------------------------------------
            # Keep bubbles inside screen
            # -----------------------------------------------

            if self.x < self.size:

                self.x = self.size


            elif self.x > screen_width - self.size:

                self.x = (
                    screen_width
                    -
                    self.size
                )


            if self.y < self.size:

                self.y = self.size


            elif self.y > screen_height - self.size:

                self.y = (
                    screen_height
                    -
                    self.size
                )


        # ====================================================
        # No gesture
        # ====================================================

        else:

            self.update_idle()


    # ========================================================
    # Draw bubble
    # ========================================================

    def draw(self):

        bubble_surface = pygame.Surface(
            (
                self.size * 2,
                self.size * 2
            ),
            pygame.SRCALPHA
        )


        # ====================================================
        # Gradient
        # ====================================================

        for radius in range(
            self.size,
            0,
            -1
        ):

            alpha = int(
                self.alpha
                *
                (
                    radius
                    /
                    self.size
                )
            )


            color = (
                self.color[0],
                self.color[1],
                self.color[2],
                alpha
            )


            pygame.draw.circle(
                bubble_surface,
                color,
                (
                    self.size,
                    self.size
                ),
                radius
            )


        # ====================================================
        # Highlight
        # ====================================================

        highlight_size = (
            self.size
            //
            3
        )


        highlight_pos = (
            int(
                self.size
                *
                self.highlight_pos[0]
            ),
            int(
                self.size
                *
                self.highlight_pos[1]
            )
        )


        pygame.draw.ellipse(
            bubble_surface,
            (
                255,
                255,
                255,
                150
            ),
            (
                highlight_pos[0],
                highlight_pos[1],
                highlight_size,
                highlight_size // 2
            )
        )


        # ====================================================
        # Draw
        # ====================================================

        screen.blit(
            bubble_surface,
            (
                int(
                    self.x
                    -
                    self.size
                ),
                int(
                    self.y
                    -
                    self.size
                )
            )
        )


# ============================================================
# Create bubbles
# ============================================================

NUMBER_OF_BUBBLES = 50


bubbles = [
    Bubble()
    for _ in range(NUMBER_OF_BUBBLES)
]


# ============================================================
# Direction state
# ============================================================

current_global_direction = None

last_gesture_time = 0


# ============================================================
# Used for periodically refreshing TOPMOST
# ============================================================

last_topmost_refresh = time.time()


# ============================================================
# Main loop
# ============================================================

running = True


with mss.mss() as sct:


    while running:

        frame_start = time.time()


        # ====================================================
        # Pygame events
        # ====================================================

        for event in pygame.event.get():

            if event.type == pygame.QUIT:

                running = False


            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:

                    running = False


        # ====================================================
        # Keep second-screen Bubble window on top
        #
        # Refresh about once per second.
        #
        # SWP_NOACTIVATE means it should NOT steal keyboard
        # focus from your video / meeting window.
        # ====================================================

        if (
            time.time()
            -
            last_topmost_refresh
            >
            1.0
        ):

            keep_window_on_top()

            last_topmost_refresh = time.time()


        # ====================================================
        # Capture screen
        #
        # ORIGINAL PIPELINE
        # ====================================================

        screenshot = sct.grab(
            monitor_area
        )


        img = np.array(
            screenshot
        )


        frame = cv2.cvtColor(
            img,
            cv2.COLOR_BGRA2BGR
        )


        h, w, _ = frame.shape


        # ====================================================
        # MediaPipe processing
        # ====================================================

        frame.flags.writeable = False


        frame_rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )


        hand_results = hands.process(
            frame_rgb
        )


        # ====================================================
        # Direction detected in this frame
        # ====================================================

        new_direction = None


        # ====================================================
        # Process hand landmarks
        # ====================================================

        if hand_results.multi_hand_landmarks:


            for hand_landmarks, hand_info in zip(
                hand_results.multi_hand_landmarks,
                hand_results.multi_handedness
            ):


                label = (
                    hand_info
                    .classification[0]
                    .label
                )


                # ============================================
                # Only use LEFT hand
                # ============================================

                if label == "Left":


                    lmList = []


                    for idx in [
                        5,
                        8,
                        9,
                        12,
                        13,
                        16
                    ]:


                        lm = (
                            hand_landmarks
                            .landmark[idx]
                        )


                        lmList.append(
                            lm
                        )


                    # ========================================
                    # Calculate direction
                    # ========================================

                    if len(lmList) >= 6:


                        # X
                        l1x = (
                            lmList[1].x
                            -
                            lmList[0].x
                        )


                        l2x = (
                            lmList[3].x
                            -
                            lmList[2].x
                        )


                        l3x = (
                            lmList[5].x
                            -
                            lmList[4].x
                        )


                        lx = (
                            l1x
                            +
                            l2x
                            +
                            l3x
                        ) / 3


                        # Y
                        l1y = (
                            lmList[1].y
                            -
                            lmList[0].y
                        )


                        l2y = (
                            lmList[3].y
                            -
                            lmList[2].y
                        )


                        l3y = (
                            lmList[5].y
                            -
                            lmList[4].y
                        )


                        ly = (
                            l1y
                            +
                            l2y
                            +
                            l3y
                        ) / 3


                        # ====================================
                        # Determine direction
                        # ====================================

                        if lx > 0.10:

                            new_direction = "left"


                        elif lx < -0.08:

                            new_direction = "right"


                        elif ly > 0.15:

                            new_direction = "down"


                        elif ly < -0.15:

                            new_direction = "up"


        # ====================================================
        # Gesture state
        # ============================================================

        current_time = time.time()


        # ====================================================
        # Valid gesture
        # ============================================================

        if new_direction is not None:


            # Immediately change direction
            current_global_direction = (
                new_direction
            )


            # Reset timeout
            last_gesture_time = (
                current_time
            )


        # ====================================================
        # No valid gesture this frame
        # ============================================================

        else:


            # ------------------------------------------------
            # Temporary loss
            #
            # Keep old direction / speed
            # ------------------------------------------------

            if (
                current_global_direction
                is not None
                and
                current_time
                -
                last_gesture_time
                <
                NO_GESTURE_TIMEOUT
            ):

                pass


            # ------------------------------------------------
            # Signal really disappeared
            #
            # Bubble.update_idle() starts gradual slowdown.
            # ------------------------------------------------

            else:

                current_global_direction = None


        # ====================================================
        # Draw bubbles
        # ============================================================

        screen.fill(
            (0, 0, 25)
        )


        for bubble in bubbles:


            bubble.update(
                current_global_direction
            )


            bubble.draw()


        pygame.display.flip()


        # ====================================================
        # Maintain FPS
        # ============================================================

        frame_time = (
            time.time()
            -
            frame_start
        )


        if frame_time < FRAME_DURATION:

            time.sleep(
                FRAME_DURATION
                -
                frame_time
            )


        clock.tick(
            TARGET_FPS
        )


# ============================================================
# Cleanup
# ============================================================

hands.close()

pygame.quit()

sys.exit()