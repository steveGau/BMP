# BMP Player

A dark-theme digital metronome for Windows. The GUI follows the Digital Metronome layout: title, combo boxes, per-sound loudness bars, BPM dial, pendulum arc, TAP, and a circular play/stop button.

## Run

Double-click `run_BMP.bat`, or from this folder:

```bat
python BMP.py
```

Needs Python 3 with Tkinter (standard on Windows). No extra packages.

GitHub: https://github.com/steveGau/BMP

## Default startup

Matches the reference screenshots:

| Setting | Default |
| --- | --- |
| Window size | `422x912` (min `400x850`) |
| Time signature | `1/4` |
| Sound pattern | `1 Beat 1 2 Sound` |
| Accent | `Accent On` |
| Loudness | `10:1` |
| 1st Sound | `1:1` (locked) |
| 2nd Sound | `10:1` |
| BPM | `50` (range `30–300`) |

## Controls

| Control | What it does |
| --- | --- |
| **Metronome** | Title text |
| Time signature combo | `1/4`, `2/4`, `3/4`, `4/4`, `5/4`, `6/4`, `7/4`, `3/8`, `6/8`, `9/8`, `12/8` |
| Sound combo | `1 Beat 1 Sound`, `1 Beat 1 2 Sound`, `1 Beat 1 2 3 Sound`, `1 Beat 1 2 3 4 Sound` |
| Accent combo | `Accent On`, `Accent Off` |
| Loudness combo | `2:1` … `10:1` only (the first-sound scale `N`) |
| Loudness bars | One bar per click in the selected sound pattern. 1st Sound is locked at `1:1`. Later sounds show `N:k` |
| BPM dial | Drag handle, mouse-wheel, or click trough left/right for **±1** fine step; range **30–300** |
| TAP | Tap tempo; updates the dial |
| Circular button | Play / Stop |

Each combo shows the current value. Click it to open the full list.

When **1 Beat 1 2 3 4 Sound** is selected, four bars appear. With Loudness `10:1` the defaults are `1:1`, `10:5`, `10:3`, `10:1`. Playback volume:

- 1st sound = **1**
- later sound = `(k / N) * 0.2`

So `10:1` plays at **0.02**, `10:2` at **0.04**, `10:5` at **0.10**. Two-sound and three-sound patterns show 2 or 3 bars the same way.

## Tests

From this folder:

```bat
python OLDCODE/test_BMP.py -v
```

## Files

- `BMP.py` — metronome app
- `run_BMP.bat` — launcher
- `OLDCODE/test_BMP.py` — timing, sound, and GUI tests
- `run.txt` — working copy of user prompts

## User prompts

Prompts issued for this project, in order:

### Prompt 1

```
1. create a BMP Player: BMP.py
2. see attached "image Digital Metronome GUI.png"
3. create a GUI similiar "image Digital Metronome GUI.png"
3.1 Text GUI to show : Metronome
3.2Combo GUI to show and select: 1/4, 2/4,...
3.3Combo GUI to show and select: 1 Beat 1 Sound, 1 Beat 1 2 Sound ...
3.4Combo GUI to show and select: Accent On, Accent Off
3.4Combo GUI to show and select BMP: 60,...120
3.5Combo GUI to show and Set: Play, Stop
4.write a batch for BMP.py
```

### Prompt 2

```
1. play few time and loss sound
2. only 1 item in Combo GUIs
3.1 only 1 item in Combo GUI to show and put more items to select: 1/4, 2/4,...
3.2 only 1 item in Combo GUI to show and put more items to select: 1 Beat 1 Sound, 1 Beat 1 2 Sound ...
3.3 only 1 item in Combo GUI to show and put more items to select: Accent On, Accent Off
3.4 only 1 item in Combo GUI to show and dial to select BMP: 60,...120
3.5 Combo GUI to show and Set: Play, Stop
4. test every GUI, if not work, fix it
```

### Prompt 3

```
5. remove Combo GUI to show and Set: Play, Stop
6. set Combo GUI to show and dial to select BMP: 30,...300
```

### Prompt 4

```
7. write README.md, incluse all prompts issued from user
8. commit all files and folder "D:\Users\a2907\Desktop\batch\BMP" to git and to push main to GitHub.
```

### Prompt 5

```
9. https://github.com/steveGau/BMP
```

### Prompt 6

```
add a Combo GUI to set and dial to select 2nd, 3rd, 4th Sound loudnes ratio: e.g.,
"1 Beat 1 2 Sound", 2:1
"1 Beat 1 2 3 Sound", 3:2:1
"1 Beat 1 2 3 4 Sound", 4:3:2:1
```

### Prompt 7

```
I can not tell the Sound loudnes ratio between 1/2 and 1/4
```

### Prompt 8

```
7. rewrite README.md, incluse all prompts issued from user
8. commit all files and folder "D:\Users\a2907\Desktop\batch\BMP" to git and to push main to GitHub.
```

### Prompt 9

```
redo a Combo GUI to set and dial to select 2nd, 3rd, 4th Sound loudnes ratio: e.g.,
2:1
3:1
4:1
5:1
6:1
7:1
8:1
9:1
10:1
```

### Prompt 10

```
2:1
3:1
4:1
5:1
6:1
7:1
8:1
9:1
10:1
```

### Prompt 11

```
1. you misunderstand what I mean, I want Combo GUI "Loundness" to set and dial to select
2:1
3:1
4:1
5:1
6:1
7:1
8:1
9:1
10:1
no other options to select

2. when select "1 Beat 1 2 Sound", or "1 Beat 1 2 3 Sound", or "1 Beat 1 2 3 4 Sound",
only
2:1
3:1
4:1
5:1
6:1
7:1
8:1
9:1
10:1
shown in "1 Beat 1 2 Sound", or "1 Beat 1 2 3 Sound", or "1 Beat 1 2 3 4 Sound",
```

### Prompt 12

```
do What I suggest in the attached image
```

Attached image notes: when **1 Beat 1 2 3 4 Sound** is selected, show four loudness bars (1st / 2nd / 3rd / 4th Sound). 1st sound is 1. 2nd is 1st × (5/10), 3rd is 1st × (3/10), 4th is 1st × (1/10), shown as `10:5`, `10:3`, `10:1`.

### Prompt 13

```
0.1 or 10:1 loudness still to0 loud, let reduce to 20% of the current 0.1 loundness, do the same for 10:2,...
```

### Prompt 14

```
7. rewrite README.md, incluse all prompts issued from user
8. commit all files and folder "D:\Users\a2907\Desktop\batch\BMP" to git and to push main to GitHub.
```

### Prompt 15

```
https://github.com/anthropics/skills
```

### Prompt 16

```
@frontend-design or click the + icon
```

### Prompt 17

```
add capability to GUI BMP, when click at BMP slider bosy , it will shift 1 step to left or right for fine step
```

### Prompt 18

```
1. redo deauft GUI setting with image 1
2. redo deauft GUI size with image 2
3. rewrite README.md, incluse all prompts issued from user
4. commit all files and folder "D:\Users\a2907\Desktop\batch\BMP" to git and to push main to GitHub.
```
