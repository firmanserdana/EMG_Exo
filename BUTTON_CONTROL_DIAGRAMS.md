# Button Control Mode - Operation Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ESP32 Glove Control System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────┐      ┌──────────────┐      ┌─────────────┐     │
│  │  Web UI    │      │  TCP Client  │      │  Button Pin │     │
│  │ 192.168.   │      │   Control    │      │  GPIO 33/32 │     │
│  │   4.1      │      │              │      │             │     │
│  └─────┬──────┘      └──────┬───────┘      └──────┬──────┘     │
│        │                    │                     │             │
│        └────────────────────┴─────────────────────┘             │
│                             │                                    │
│                    ┌────────▼────────┐                          │
│                    │  Control Mode   │                          │
│                    │   Selector      │                          │
│                    │                 │                          │
│                    │  WEB / TCP /    │                          │
│                    │  BUTTON / AUTO  │                          │
│                    └────────┬────────┘                          │
│                             │                                    │
│           ┌─────────────────┼─────────────────┐                │
│           │                 │                 │                │
│  ┌────────▼────────┐ ┌──────▼──────┐ ┌───────▼────────┐       │
│  │   WEB Mode      │ │  TCP Mode   │ │  BUTTON Mode   │       │
│  │                 │ │             │ │                │       │
│  │ - Web Control   │ │ - Computer  │ │ - Push Button  │       │
│  │ - Manual        │ │   Control   │ │ - Toggle       │       │
│  └─────────────────┘ └─────────────┘ └────────┬───────┘       │
│                                               │                │
│                                               │                │
│                             ┌─────────────────▼──────────┐     │
│                             │  Gesture Controller        │     │
│                             │                           │     │
│                             │  Current Gesture: 0-8     │     │
│                             │  Finger States: "000000"  │     │
│                             └─────────────┬─────────────┘     │
│                                           │                    │
│                                           │                    │
│                             ┌─────────────▼─────────────┐     │
│                             │  Actuator Controller      │     │
│                             │                           │     │
│                             │  - Digital Outputs        │     │
│                             │  - DAC (Pressure/Speed)   │     │
│                             └─────────────┬─────────────┘     │
│                                           │                    │
└───────────────────────────────────────────┼────────────────────┘
                                            │
                                            ▼
                                   ┌────────────────┐
                                   │  Pneumatic     │
                                   │  Actuators     │
                                   │                │
                                   │  5 Fingers +   │
                                   │  Abduction     │
                                   └────────────────┘
```

## Button Control Mode State Machine

```
                    ┌──────────────────────────────┐
                    │   System Powers On           │
                    │   or Mode Switched           │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   BUTTON MODE ACTIVE         │
                    │                              │
                    │   button_gesture_active = 0  │
                    │   gesture = 0 (Relax)        │
                    │   current_button_gesture = 1 │
                    └──────────────┬───────────────┘
                                   │
                                   │ Main Loop
                                   ▼
             ┌─────────────────────────────────────────┐
             │                                         │
     ┌───────▼──────────┐                   ┌──────────▼────────┐
     │  Button = HIGH   │                   │   Button = LOW    │
     │  (Not Pressed)   │                   │   (Pressed)       │
     │                  │                   │                   │
     │  No Action       │                   │  Check Debounce   │
     │  Continue Loop   │                   └──────────┬────────┘
     └───────┬──────────┘                              │
             │                                         │
             │                         ┌───────────────▼────────────────┐
             │                         │  Time Since Last Press > 200ms? │
             │                         └───────────────┬────────────────┘
             │                                         │
             │                                  Yes    │    No
             │                         ┌───────────────┴────────────┐
             │                         │                            │
             │                         ▼                            ▼
             │          ┌──────────────────────────┐    ┌──────────────────┐
             │          │  Check Current State     │    │  Ignore Press    │
             │          └──────────────┬───────────┘    │  (Debouncing)    │
             │                         │                └──────────────────┘
             │                         │
             │          ┌──────────────┴─────────────┐
             │          │                            │
             │          ▼                            ▼
             │   ┌─────────────┐           ┌────────────────┐
             │   │  State = 0  │           │   State = 1    │
             │   │  (Relax)    │           │   (Active)     │
             │   └──────┬──────┘           └────────┬───────┘
             │          │                           │
             │          ▼                           ▼
             │   ┌─────────────────┐        ┌──────────────────┐
             │   │  Activate       │        │  Return to       │
             │   │  Gesture        │        │  Relax           │
             │   │                 │        │                  │
             │   │  gesture = X    │        │  gesture = 0     │
             │   │  state = 1      │        │  state = 0       │
             │   └────────┬────────┘        └──────┬───────────┘
             │            │                        │
             │            │                        │
             │            └────────┬───────────────┘
             │                     │
             │                     ▼
             │          ┌──────────────────────┐
             │          │  Update Actuators    │
             │          │                      │
             │          │  - Set finger states │
             │          │  - Set pressure/speed│
             │          └──────────┬───────────┘
             │                     │
             └─────────────────────┘
                      Loop Continues
```

## Gesture Selection Flow

```
┌──────────────────────────────────────────────────────────┐
│                    Web Interface                         │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  Button Mode Configuration                     │    │
│  │                                                 │    │
│  │  Active Gesture: [Dropdown ▼]                 │    │
│  │                                                 │    │
│  │  Options:                                      │    │
│  │    • HandClose (1)      ◄─ Default            │    │
│  │    • HandOpen (2)                              │    │
│  │    • HookGrasp (3)                             │    │
│  │    • LateralGrasp (4)                          │    │
│  │    • ThumbFlexion (5)                          │    │
│  │    • IndexFlexion (6)                          │    │
│  │    • MRPFlexion (7)                            │    │
│  │    • IndexPointing (8)                         │    │
│  └────────────────────────────────────────────────┘    │
│                           │                             │
└───────────────────────────┼─────────────────────────────┘
                            │
                            │ HTTP GET Request
                            │ /button-gesture?value=X
                            │
                            ▼
              ┌─────────────────────────────┐
              │  ESP32 Web Server           │
              │                             │
              │  current_button_gesture = X │
              │                             │
              │  Saves to variable          │
              │  (persists until changed)   │
              └─────────────────────────────┘
```

## Timing Diagram

```
Time (ms) →

Button       ─┐     ┌───┐     ┌───┐         ┌───┐     ┌───
Signal        └─────┘   └─────┘   └─────────┘   └─────┘
              Press    Bounce    Release      Press    Release
              
Debounce     ─────────────────────────────────────────────────
Timer                 200ms                    200ms
                  ◄─────────►               ◄─────────►
                  
Action         Activate      Ignore          Return       Ignore
               Gesture                       to Relax

State          0 → 1         (no change)     1 → 0       (no change)

Gesture        0 → X         X               X → 0       0
```

## Pin Configuration

```
ESP32 Board (v2)                      ESP32 Board (v1)
┌───────────────┐                     ┌───────────────┐
│               │                     │               │
│  GPIO 33 ●────┼──┐                 │  GPIO 32 ●────┼──┐
│               │  │                  │               │  │
│  GND ●────────┼──┼──┐              │  GND ●────────┼──┼──┐
│               │  │  │               │               │  │  │
└───────────────┘  │  │               └───────────────┘  │  │
                   │  │                                  │  │
              ┌────▼──▼────┐                        ┌────▼──▼────┐
              │  Push       │                        │  Push       │
              │  Button     │                        │  Button     │
              └─────────────┘                        └─────────────┘

Internal Pull-up Enabled               Internal Pull-up Enabled
Button Pressed = LOW                   Button Pressed = LOW
Button Released = HIGH                 Button Released = HIGH
```

## Integration with Other Modes

```
                          ┌─────────────────┐
                          │   User Input    │
                          │                 │
                          │ Web / TCP / BTN │
                          └────────┬────────┘
                                   │
                    ┌──────────────┴───────────────┐
                    │                              │
                    ▼                              ▼
         ┌──────────────────┐          ┌──────────────────┐
         │  AUTO Mode       │          │  FORCE Mode      │
         │                  │          │                  │
         │  - TCP Active?   │          │  - FORCE_WEB     │
         │    → TCP Mode    │          │  - FORCE_TCP     │
         │  - No TCP?       │          │  - FORCE_BUTTON  │
         │    → WEB Mode    │          │                  │
         └──────────────────┘          └──────────────────┘
                    │                              │
                    └──────────────┬───────────────┘
                                   │
                         ┌─────────▼──────────┐
                         │  Active Mode       │
                         │                    │
                         │  WEB / TCP / BTN   │
                         └─────────┬──────────┘
                                   │
                         ┌─────────▼──────────┐
                         │  Gesture Control   │
                         └─────────┬──────────┘
                                   │
                         ┌─────────▼──────────┐
                         │  Actuators         │
                         └────────────────────┘
```

## Example Usage Scenario

```
Step 1: Setup
┌──────────────────────────────────────────────┐
│ User connects button to GPIO 33 and GND     │
│ User accesses http://192.168.4.1            │
└──────────────────┬───────────────────────────┘
                   │
Step 2: Mode Selection
┌──────────────────▼───────────────────────────┐
│ User clicks "Force BUTTON Mode"             │
│ System switches to BUTTON_MODE              │
│ Button config panel appears                 │
└──────────────────┬───────────────────────────┘
                   │
Step 3: Gesture Selection
┌──────────────────▼───────────────────────────┐
│ User selects "HookGrasp" from dropdown      │
│ current_button_gesture = 3                   │
└──────────────────┬───────────────────────────┘
                   │
Step 4: Operation
┌──────────────────▼───────────────────────────┐
│ User presses button                          │
│ → gesture = 3 (HookGrasp activated)         │
│                                              │
│ User presses button again                    │
│ → gesture = 0 (Return to relax)             │
│                                              │
│ User presses button again                    │
│ → gesture = 3 (HookGrasp activated)         │
└──────────────────────────────────────────────┘

Result: Simple toggle control for selected gesture
```
