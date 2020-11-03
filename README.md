# PyDestreamer
Python port of destreamer - Microsoft Stream video downloader.

This project was inspired by <https://github.com/snobu/destreamer>, rewritten into Python from <https://github.com/sup3rgiu/MStreamDownloader>.

## Setup
You need Python 3.x to run the script.

Make sure you have installed these packages, eg. using pip: 

```pip install argparse asyncio html json keyring m3u8 nest_asyncio pyppeteer re requests_async shutil signal subprocess time urllib termcolor prompt_toolkit```

Extract the latest **ffmpeg** release (download from <https://github.com/BtbN/FFmpeg-Builds/releases>) and **aria2c** (download from <https://github.com/aria2/aria2/releases>) either into arbitrary directory and don't forget to add paths to PATH environtment variable, or simply into the directory containing the python script.

## Usage

```
usage: PyDestreamer [-h] -v VIDEOURLS [VIDEOURLS ...] [-u USERNAME]
                    [-p PASSWORD] [-o OUTPUTDIRECTORY] [-q QUALITY]
                    [-k NOKEYRING] [-c CONN]

Python port of destreamer.
Project originally based on https://github.com/snobu/destreamer.
Fork powered by @vrbadev.

optional arguments:
  -h, --help            show this help message and exit
  -v VIDEOURLS [VIDEOURLS ...], --videoUrls VIDEOURLS [VIDEOURLS ...]
  -u USERNAME, --username USERNAME
                        Your Microsoft Email
  -p PASSWORD, --password PASSWORD
  -o OUTPUTDIRECTORY, --outputDirectory OUTPUTDIRECTORY
  -q QUALITY, --quality QUALITY
                        Video Quality, usually [0-5]
  -k NOKEYRING, --noKeyring NOKEYRING
                        Do not use system keyring
  -c CONN, --conn CONN  Number of simultaneous connections [1-16]

examples:
	Standard usage:
		python PyDestreamer.py -v https://web.microsoftstream.com/video/...
```
