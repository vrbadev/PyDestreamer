# PyDestreamer
Python port of destreamer - Microsoft Stream video downloader.

This project was inspired by <https://github.com/snobu/destreamer>, rewritten into Python from <https://github.com/sup3rgiu/MStreamDownloader>.

Latest python script is available [here on github](https://github.com/vrbadev/PyDestreamer/).

## Setup
You need Python 3.x to run the script.

### Windows-specific steps
Extract the latest **ffmpeg** release (download from <https://github.com/BtbN/FFmpeg-Builds/releases>) and **aria2c** (download from <https://github.com/aria2/aria2/releases>) either into arbitrary directory and don't forget to add paths to PATH environtment variable, or simply into the directory containing the python script.

### Linux-specific steps
On a fresh Debian install, run
```
sudo apt-get update
sudo apt-get install ffmpeg aria2 python3 python3-pip
```

Make sure you have installed all required modules.
Most of them should be included in default python3 installation, the rest can be installed using pip:

```pip install m3u8 nest_asyncio pyppeteer requests_async termcolor prompt_toolkit```

### Login process settings
The function ```async def defaultLogin(page, email, password)``` tries to find specific HTML elements in the login form on Microsoft Stream website. It is usually composed of default Microsoft login form and a form specific for your university/company. Element identifiers used in the python script are working for the CTU login, but you will probably need to change them slightly.

Elements corresponding to ```input[type="email"]```, ```input[type="submit"]``` and ```div[id="usernameError"]``` are common as they are located at the default Microsoft login form. When username is entered and submit button pressed the form brings you to your university/company login form - username is copied automatically, but elements ```input[type="password"]```, ```span[id="submitButton"]``` and ```span[id="errorText"]``` **may be different** in your case. Easiest way to find the correct identifiers is to perform the login manually with Chrome Web Inspector opened and focused on the required elements, then you should be able to find them in the HTML code. If the login is successful it will redirect you back to Microsoft login form to choose if password should be remembered, the "No" button corresponds to ```input[id="idBtn_Back"]```. That is the end of the login process followed by redirection to Microsoft Stream homepage.


## Usage

```
usage: PyDestreamer [-h] -v VIDEOURLS [VIDEOURLS ...] [-u USERNAME] [-p PASSWORD] [-o OUTPUTDIRECTORY] [-q QUALITY]
                    [-k NOKEYRING] [-c CONN] [--noHeadless] [--manualLogin] [--overwrite] [--keepTemp]

Python port of destreamer.
Project originally based on https://github.com/snobu/destreamer.
Fork powered by @vrbadev.

optional arguments:
  -h, --help            show this help message and exit
  -v VIDEOURLS [VIDEOURLS ...], --videoUrls VIDEOURLS [VIDEOURLS ...]
                        One or more links to Microsoft Stream videos
  -u USERNAME, --username USERNAME
                        Your Microsoft Account e-mail
  -p PASSWORD, --password PASSWORD
                        Your Microsoft Account password
  -o OUTPUTDIRECTORY, --outputDirectory OUTPUTDIRECTORY
                        Save directory for videos and temporary files
  -q QUALITY, --quality QUALITY
                        Video Quality, usually [0-5]
  -k NOKEYRING, --noKeyring NOKEYRING
                        Do not use system keyring (saved password)
  -c CONN, --conn CONN  Number of simultaneous connections [1-16]
  --noHeadless          Don not run Chromium in headless mode
  --manualLogin         Force login manually
  --overwrite           Overwrite downloaded temporary files
  --keepTemp            Do not remove temporary files

examples:
        Standard usage:
                python PyDestreamer.py -v https://web.microsoftstream.com/video/...
```
