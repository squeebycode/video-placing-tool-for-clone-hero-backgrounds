# video-placing-tool-for-clone-hero-backgrounds
Manually placing every video from one folder to the next was taking way too much time, so I had Claude write a python script that would automate the entire process. I have no coding experience outside of some scratch in high school and tinkering with Lua scripting in roblox as a teen. This is entirely written and modified by Claude. Out there on the interwebs exists entire dumps of Guitar Hero/Rock Band Maps, and entire dumps of every background video per song for those maps. This python script allows you to set the folder of both of those to easily move the background videos to the song folders with very minimal to at times NO manual intervention. 

This is written for Windows, and probably will not be updated. Ever. If you want a more detailed description of the program, check out https://github.com/squeebycode/video-placing-tool-for-clone-hero-backgrounds/blob/main/Claude's%20README.md

# Clone Hero Video Placer

By default the script looks in `Documents\Clone Hero\Songs` and `Documents\Video Dumps` inside your user folder. If yours are elsewhere (including a Documents folder redirected to OneDrive), pass `--songs` and `--dumps`, or edit `SONGS_ROOT` / `DUMPS_ROOT` near the top of the script (RECOMMENDED).

## Quick start

1. **Unzip** the video dumps into your dumps folder, one folder per song (it doesn't really matter how its nested).
2. Open a terminal (Command Prompt or PowerShell) in the folder with the script. (You want to open the script from the terminal so you can specify what arguments to use)
3. **Preview first.** Nothing is moved:
   ```
   python place_videos.py --dry-run
   ```
   On Windows, use `py place_videos.py --dry-run` if `python` isn't recognized. You can also run `python place_videos.py --dry-run --auto` and then check the logs to see how many would have been moved automatically and correctly. (If using the Dumps from https://docs.google.com/spreadsheets/d/13B823ukxdVMocowo1s5XnT3tzciOfruhUVePENKc01o/edit?gid=1870223413#gid=1870223413 (songs) and https://docs.google.com/spreadsheets/u/0/d/1mKjWQptErA6qolvxx-EYQUl1mECp1_7Q4BEd3zZb69w/htmlview (backgrounds), this should work flawlessly.)
4. **Place the obvious ones automatically:**
   ```
   python place_videos.py --auto
   ```
   Exact matches are moved without asking. It stops to ask about everything else.
5. **Run it normally for what's left:**
   ```
   python place_videos.py
   ```
   You could also just do this option from the get-go and select y or n, but it is painstaking for how many songs there are if you are doing many dumps. 
6. Check `place_videos.log` (next to the script) for a full record.
