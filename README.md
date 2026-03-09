# Reverse:1999 Summon Link Grabber
A simple tool that captures the summon history link from Reverse:1999 automatically.
The program temporarily enables a local proxy (mitm), listens for the summon history request, and extracts the URL required for gacha history trackers.

# Disclaimer
This project simply reads network requests made by the game client and does not modify game data.
Use at your own risk.

# Quick Start (EXE version)
The easiest way to use the tool is the precompiled .exe version.
## Steps:
* Download the latest release from the Releases page.
* Run R1999LinkGrabber.exe
* Open summon history
You should see:
```
Proxy enabled: 127.0.0.1:8080
Starting capture...
Launch the game and open summon history
```
* Run Reverse:1999
* Open the Summon History page in the game.
When the link is captured, the program will display something like:
```
=== SUMMON LINK FOUND ===
https://game-re-en-service.sl916.com/query/summon?...
Link copied to clipboard
```
The link is now copied to your clipboard and ready to paste into a tracker.

# Running Python Script
If you prefer to run the original Python script instead of the compiled executable, follow the steps below.
## Requirements (Python script version)
* Python 3.10 – 3.12 (Tested on Python 3.12.10)
* Windows (Tested on Windows 11 25H2)
* mitmproxy
* pyperclip

You can download Python from: https://www.python.org/downloads/release/python-31210/

## Installation
Clone the repository:
```
git clone https://github.com/lonelytragedy/r1999-SummonHistoryLinkGrabber.git
cd r1999-SummonHistoryLinkGrabber
```
Install dependencies:
```
pip install mitmproxy pyperclip
```
Start the script with:
```
python R1999LinkGrabber.py
```
Then:
* Launch Reverse: 1999
* Open the Summon History page
* The program will automatically detect the summon history request and output the link.

# Important Warning
Do not close the console window using the X (close button) in the top corner of the window.
Closing the program this way may leave the system proxy enabled.
Please only exit the program using one of the following methods:
* Press Ctrl + C in the console
* Let the script finish normally after the summon link is captured

These methods allow the program to properly disable the proxy automatically.

# How to Manually Disable the Proxy (If Needed)
If the proxy remains enabled after closing the program, you can disable it manually.
Windows 10 / Windows 11
* Open Settings
* Go to Network & Internet
* Select Proxy
* Under Manual proxy setup, turn Off:
```
Use a proxy server
```
The proxy address that may have been set by the program is:
```
127.0.0.1:8080
```
Once Use a proxy server is disabled, your internet connection will return to normal.
