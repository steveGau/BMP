# BMP Player

A dark-theme digital metronome for Windows. The GUI follows the attached Digital Metronome layout: title, combo boxes, BPM dial, pendulum arc, TAP, and a circular play/stop button.

## Run

Double-click `run_BMP.bat`, or from this folder:

```bat
python BMP.py
```

Needs Python 3 with Tkinter (standard on Windows). No extra packages.

## Controls

| Control | What it does |
| --- | --- |
| **Metronome** | Title text |
| Time signature combo | `1/4`, `2/4`, `3/4`, `4/4`, `5/4`, `6/4`, `7/4`, `3/8`, `6/8`, `9/8`, `12/8` |
| Sound combo | `1 Beat 1 Sound`, `1 Beat 1 2 Sound`, `1 Beat 1 2 3 Sound`, `1 Beat 1 2 3 4 Sound` |
| Accent combo | `Accent On`, `Accent Off` |
| BPM dial | Drag or mouse-wheel, **30–300** |
| TAP | Tap tempo; updates the dial |
| Circular button | Play / Stop |

Each combo shows the current value. Click it to open the full list.

## Tests

```bat
python -m unittest test_BMP.py -v
```

## Files

- `BMP.py` — metronome app
- `run_BMP.bat` — launcher
- `test_BMP.py` — timing, sound, and GUI tests

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
