# -*- coding: utf-8 -*-
"""
PyDestreamer
Unofficial Python port of https://github.com/snobu/destreamer
(from a fork https://github.com/sup3rgiu/MStreamDownloader/)

@author: @vrbadev
Available under MIT license.
"""

import argparse
import asyncio
import html
import json
import keyring
import m3u8
import nest_asyncio
import os
import pyppeteer 
import re
import requests_async
import shutil
import signal
import subprocess
import sys
import time
import urllib

from datetime import datetime
from termcolor import colored
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.validation import Validator, ValidationError

nest_asyncio.apply()
argv = None

class NumberValidator(Validator):
    def __init__(self, maximum):
        self.maximum = maximum
        
    def validate(self, document):
        text = document.text

        if text:
            if not text.isdigit():
                i = 0
    
                # Get index of fist non numeric character.
                # We want to move the cursor here.
                for i, c in enumerate(text):
                    if not c.isdigit():
                        break
    
                raise ValidationError(message='This input contains non-numeric characters', cursor_position=i)
            else:
                num = int(text)
                if num >= self.maximum:
                    raise ValidationError(message='This number is bigger than maximum (%d)' % self.maximum-1)
            
            
def isUtilityInstalled(utility):
    for cmdpath in os.environ['PATH'].split(os.pathsep) + [os.getcwd()]:
        try:
            if os.path.isdir(cmdpath) and any([utility in fn for fn in os.listdir(cmdpath)]):
                return True
        except FileNotFoundError:
            continue
    return False


def sanityChecks():
    if isUtilityInstalled('aria2c'):
        print(colored('Aria2c is installed and ready.', 'green'))
    else:
        print(colored('You need aria2c in $PATH or this script\'s folder for this to work!', 'red'))
        exit(1)
        
    if isUtilityInstalled('ffmpeg'):
        print(colored('FFmpeg is installed and ready.', 'green'))
    else:
        print(colored('You need FFmpeg in $PATH or this script\'s folder for this to work!', 'red'))
        exit(1)
    
    if not os.path.exists(argv.outputDirectory):
        os.makedirs(argv.outputDirectory)
        print('Creating output directory:', argv.outputDirectory)


def osFixPath(path):
    path = re.compile(r"[\/]").split(path)
    return os.path.abspath(os.path.join(*path))


async def downloadVideo(videoUrls, email, password, outputDirectory):
    global browser
    email = await handleEmail(email)
    
    # handle password
    if password is None: # password not passed as argument
        if argv.noKeyring is False:
            try:
                password = keyring.get_password("PyDestreamer", email)
                if password is None: # no previous password saved
                    password = await prompt("Password not saved. Please enter your password, PyDestreamer will not ask for it next time: ")
                    keyring.set_password("PyDestreamer", email, password)
                else:
                    print("\nReusing password saved in system's keychain!")
            except:
                print("X11 is not installed on this system. PyDestreamer can't use keytar to save the password.")
                password = await prompt("No problem, please manually enter your password: ")
        else:
            password = await prompt("\nPlease enter your password: ")
    else:
        if argv.noKeyring is False:
            try:
                keyring.set_password("PyDestreamer", email, password)
                print("Your password has been saved. Next time, you can avoid entering it!")
            except:
                pass # X11 is missing. Can't use keytar
     
    print('\nLaunching headless Chrome to perform the OpenID Connect dance...')
    browser = await pyppeteer.launch(options={'headless': not argv.noHeadless and not argv.manualLogin, 'args': ['--no-sandbox', '--disable-dev-shm-usage', '--lang=en-US']})
    
    page = await browser.newPage()
    
    print('Navigating to STS login page...')
    await page.goto('https://web.microsoftstream.com/', options={ 'waitUntil': 'networkidle2' })
    
    if not argv.manualLogin:
        if not await defaultLogin(page, email, password):
            await browser.close()
            return
    else:
        await prompt("Login manually inside the browser and then press Enter.")
    
    await page.waitForRequest(lambda req: 'microsoftstream.com/' in req.url and req.method == 'GET')
    
    print('We are logged in. ')
    await asyncio.sleep(5)
    cookie = await extractCookies(page)
    if cookie is None:
        browser.close()
        return
    print('Got required authentication cookies.')
    
    for videoUrl in videoUrls:
        print(colored('\nStart downloading video: %s\n' % videoUrl, 'green'))
        
        videoID = videoUrl[videoUrl.index("/video/")+7:][0:36] # use the video id (36 character after '/video/') as temp dir name
        full_tmp_dir = os.path.join(argv.outputDirectory, videoID)
        
        await page.goto('https://euwe-1.api.microsoftstream.com/api/videos/%s?api-version=1.0-private' % videoID, options={'headers': {'Cookie': cookie}})
        response = await page.content()
        req = html.unescape(response[response.index('{'):response.rindex('}')+1])
        obj = json.loads(req)
        
        if 'error' in obj:
            if obj["error"]["code"] == 'Forbidden':
                errorMsg = 'You are not authorized to access this video.\n'
            else:
                errorMsg = '\nError downloading this video! %s: %s.\n' % (obj["error"]["code"], obj["error"]["message"])
            print(colored(errorMsg, 'red'))
            await browser.close()
            return
        
        #☺ creates tmp dir
        if not os.path.exists(full_tmp_dir):
            os.makedirs(full_tmp_dir)
        else:
            if argv.overwrite:
                print("Overwrite enabled - removing old temporary files")
                shutil.rmtree(full_tmp_dir)
                os.makedirs(full_tmp_dir)
        
        title = obj["name"].strip()
        print('\nVideo title is:', title)
        title = re.sub('/[/\\?%*:|"<>]/g', '-', title) # remove illegal characters
        isoDate = obj["publishedDate"]
        if isoDate is not None and isoDate != '':
            date = datetime.strptime(isoDate[:-2], '%Y-%m-%dT%H:%M:%S.%f')
            
            uploadDate = '%02d_%02d_%02d' % (date.day, date.month, date.year)
            title = 'Lesson ' + uploadDate + ' - ' + title
        else:
            pass # print("no upload date found")
   
        playbackUrls = obj["playbackUrls"]
        hlsUrl = ''
        for elem in playbackUrls:
            if elem['mimeType'] == 'application/vnd.apple.mpegurl':
                u = urllib.parse.urlparse(elem['playbackUrl'])
                for qpart in u.query.split("&"):
                    parts = qpart.split("=", maxsplit=1)
                    if parts[0] == "playbackurl":
                        hlsUrl = parts[1]
                        break
                break
        
        response = await requests_async.get(hlsUrl)
        parsedManifest = m3u8.loads(response.text).data
           
        question = '\n'
        video_options = list()
        count = 0
        i = 0
        for playlist in parsedManifest["playlists"]:
            if 'resolution' in playlist['stream_info']:
                question = question + '[' + str(i) + '] ' + playlist['stream_info']['resolution'] + '\n'
                count = count + 1
                video_options.append(playlist)
            else:
                # if "RESOLUTION" key doesn't exist, means the current playlist is the audio playlist
                # fix this for multiple audio tracks
                audioObj = parsedManifest['playlists'][i]
            i += 1
        
        #  if quality is passed as argument use that, otherwise prompt
        if argv.quality is None:
            question = question + 'Choose the desired resolution: '
            res_choice = int(await prompt(question, validator=NumberValidator(count)))
        else:
            argv_quality = int(argv.quality)
            if argv_quality < 0 or argv.quality > count-1:
                print(colored('Desired quality is not available for this video (available range: 0-%d)\nI am going to use the best resolution available:' % (count-1), 'yellow'), parsedManifest["playlists"][count-1]['resolution'])
                res_choice = count-1
            else:
                res_choice = argv.quality
                print(colored('Selected resolution:', 'yellow'), parsedManifest["playlists"][res_choice]['resolution'])
        
        videoObj = video_options[res_choice]
           
        basePlaylistsUrl = hlsUrl[0:hlsUrl.rindex("/") + 1]
           
        # **** VIDEO ****
        videoLink = basePlaylistsUrl + videoObj['uri']
           
        # *** Get protection key (same key for video and audio segments) ***
        response = (await requests_async.get(videoLink, headers={'Cookie': cookie})).text
        parsedManifest = m3u8.loads(response).data
        
        keyUri = parsedManifest['segments'][0]['key']['uri']
        cdp = await page.target.createCDPSession()
        local_key_path = os.path.join(full_tmp_dir, 'protectionKey')
        await cdp.send('Page.setDownloadBehavior', { 'behavior': 'allow', 'downloadPath': osFixPath(full_tmp_dir)})
        try:
            # should download protectionKey file, but throws error: net::ERR_ABORTED
            await page.goto(keyUri, options={'headers': {'Cookie': cookie}})
        except pyppeteer.errors.PageError as e:
            pass
        
        await asyncio.sleep(2)
        if os.path.exists(local_key_path):
            print(colored("Protection key downloaded.", "green"))
        else:
            print(colored("Failed to download the protection key!", "red"))
            await browser.close()
            return
        
        if os.name == 'nt':
            keyReplacement = local_key_path.replace("\\", "/")
        else:
            keyReplacement = os.path.abspath(local_key_path)
        
        
        # creates two m3u8 files:
        # - video_full.m3u8: to download all segements (replacing realtive segements path with absolute remote url)
        # - video_tmp.m3u8: used by ffmpeg to merge all downloaded segements (in this one we replace the remote key URI with the absoulte local path of the key downloaded above)
        baseUri = videoLink[0:(videoLink.rindex("/") + 1)]
        video_full = response.replace('Fragments', baseUri+'Fragments') # local path to full remote url path
        video_tmp = response.replace(keyUri, keyReplacement) # remote URI to local abasolute path
        video_tmp = video_tmp.replace('Fragments', os.path.abspath(os.path.join(full_tmp_dir, 'video_segments/Fragments')))
        video_full_path = os.path.join(full_tmp_dir, 'video_full.m3u8')
        video_tmp_path = os.path.join(full_tmp_dir, 'video_tmp.m3u8')
        with open(video_full_path, 'w') as file:
            file.write(video_full)
        with open(video_tmp_path, 'w') as file:
            file.write(video_tmp)
           
        n = argv.conn
        if n > 16:
            n = 16
        elif n < 1:
            n = 1
        
        aria2c_codes = ['All downloads were successful.','An unknown error occurred.','Time out occurred.','A resource was not found.','Aria2 saw the specified number of "Resource not found" error. See --max-file-not-found option.','A download aborted because download speed was too slow. See --lowest-speed-limit option.','Network problem occurred.','There were unfinished downloads. This error is only reported if all finished downloads were successful and there were unfinished downloads in a queue when aria2 exited by pressing ctrl-c by an user or sending term or int signal.','Remote server did not support resume when resume was required to complete download.','There was not enough disk space available.','Piece length was different from one in .Aria2 control file. See --allow-piece-length-change option.','Aria2 was downloading same file at that moment.','Aria2 was downloading same info hash torrent at that moment.','File already existed. See --allow-overwrite option.','Renaming file failed. See --auto-file-renaming option.','Aria2 could not open existing file.','Aria2 could not create new file or truncate existing file.','File I/o error occurred.','Aria2 could not create directory.','Name resolution failed.','Aria2 could not parse metalink document.','Ftp command failed.','Http response header was bad or unexpected.','Too many redirects occurred.','Http authorization failed.','Aria2 could not parse bencoded file (usually ".Torrent" file).','".Torrent" file was corrupted or missing information that aria2 needed.','Magnet uri was bad.','Bad/unrecognized option was given or unexpected option argument was given.','The remote server was unable to handle the request due to a temporary overloading or maintenance.','Aria2 could not parse json-rpc request.','Reserved. Not used.','Checksum validation failed.']

        print("Downloading video fragments (aria2c)...")
        aria2cCmd = 'aria2c -i "' + video_full_path + '" -j ' + str(n) + ' -x ' + str(n) + ' -d "' + os.path.join(full_tmp_dir, 'video_segments') + '" --disable-ipv6 --auto-file-renaming=false --allow-overwrite=false --conditional-get=true --header="Cookie:' + cookie + '"';
        p = subprocess.Popen(aria2cCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()
        print(colored("Return code: %d (%s)", "green" if p.returncode == 0 else "red") % (p.returncode, aria2c_codes[p.returncode]))
        
        # download async. I'm Speed
        # **** AUDIO ****
        audioLink = basePlaylistsUrl + audioObj['uri']
        
        # same as above but for audio segements
        response = (await requests_async.get(audioLink, headers={'Cookie': cookie})).text
        baseUri = audioLink[0:audioLink.rindex("/") + 1]
        audio_full = response.replace('Fragments', baseUri+'Fragments')
        audio_tmp = response.replace(keyUri, keyReplacement)
        audio_tmp = audio_tmp.replace('Fragments', os.path.abspath(os.path.join(full_tmp_dir, 'audio_segments/Fragments')))
        audio_full_path = os.path.join(full_tmp_dir, 'audio_full.m3u8')
        audio_tmp_path = os.path.join(full_tmp_dir, 'audio_tmp.m3u8')
        with open(audio_full_path, 'w') as file:
            file.write(audio_full)
        with open(audio_tmp_path, 'w') as file:
            file.write(audio_tmp)
           
        print("Downloading audio fragments (aria2c)...")
        aria2cCmd = 'aria2c -i "' + audio_full_path + '" -j ' + str(n) + ' -x ' + str(n) + ' -d "' + os.path.join(full_tmp_dir, 'audio_segments') + '" --disable-ipv6 --auto-file-renaming=false --allow-overwrite=false --conditional-get=true --header="Cookie:' + cookie + '"';
        p = subprocess.Popen(aria2cCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()
        print(colored("Return code: %d (%s)", "green" if p.returncode == 0 else "red") % (p.returncode, aria2c_codes[p.returncode]))
           

        # *** MERGE audio and video segements in an mp4 file ***
        if os.path.exists(os.path.join(outputDirectory, title+'.mp4')):
            title = title + '-' + str(time.time_ns())
        
        videoPath = os.path.abspath(os.path.join(outputDirectory, title+".mp4"))

        print("Merging fragments (ffmpeg) into MP4...")
        ffmpegCmd = 'ffmpeg -protocol_whitelist file,http,https,tcp,tls,crypto -allowed_extensions ALL -i "' + os.path.abspath(audio_tmp_path) + '" -protocol_whitelist file,http,https,tcp,tls,crypto -allowed_extensions ALL -i "' + os.path.abspath(video_tmp_path) + '" -async 1 -c copy -bsf:a aac_adtstoasc -n "' + videoPath + '"'

        p = subprocess.Popen(ffmpegCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()
        noerr = p.returncode == 0 and os.path.exists(videoPath)
        print(colored("Return code: %d, file exists: %s", "green" if noerr else "red") % (p.returncode, str(os.path.exists(videoPath))))

        if noerr:
            print(colored('Video saved as: \'%s\'\n', 'green') % videoPath)
            
            # remove tmp dir
            if not argv.keepTemp:
                shutil.rmtree(full_tmp_dir)
            else:
                print("Keeping video temporary files as requested.")
        else:
            print(colored('Failed to process the video with ffmpeg! Keeping temporary files.\n', 'red'))

        
        
    await browser.close()
    print(colored('All jobs done!\n', 'green'))
    

async def defaultLogin(page, email, password):
    await page.waitForSelector('input[type="email"]')
    await page.keyboard.type(email)
    await page.click('input[type="submit"]')
    try:
        await page.waitForSelector('div[id="usernameError"]', { 'timeout': 1000 })
        print(colored('Bad email', 'red'))
        asyncio.get_event_loop().stop()
    except:
        pass # email ok
    
    # await sleep(2000) # maybe needed for slow connections
    await page.waitForSelector('input[type="password"]')
    await page.keyboard.type(password)
    await page.click('span[id="submitButton"]')
    
    try:
        await page.waitForSelector('span[id="errorText"]', { 'timeout': 1000 })
        print(colored('Bad password!', 'red'))
        return False
    except:
        pass # password ok
    
    try:
        await page.waitForSelector('input[id="idBtn_Back"]', { 'timeout': 30000 })
        await page.click('input[id="idBtn_Back"]') # Don't remember me
    except:
        pass # button not appeared, ok...
        
    return True


async def handleEmail(email):
    # handle email reuse
    if email is None:
        if os.path.exists('./config.json'):
            try:
                with open('./config.json', 'r') as file:
                    data = json.load(file)
                    email = data["email"]
                    print('Reusing previously saved email/username: %s\nIf you need to change it, use the -u argument.' % email)
            except Exception as e:
                print(e)
                print(colored('There has been an error parsing your informations. Continuing in the manual way...\n', 'red'))
                email = (await prompt("Email/username not saved. Please enter your email/username, PyDestreamer will not ask for it next time: ")).strip()
                saveConfig({ 'email': email })
        else:
            email = await prompt("Email/username not saved. Please enter your email/username, PyDestreamer will not ask for it next time: ")
            saveConfig({ 'email': email })
    else:
        saveConfig({ 'email': email })
    return email

async def prompt(question, validator=None):
    # Create Prompt.
    session = PromptSession(question)

    # Run echo loop. Read text from stdin, and reply it back.
    while True:
        try:
            return await session.prompt_async(validator=validator)
        except (EOFError, KeyboardInterrupt):
            return None

def saveConfig(infos):
    data = json.dumps(infos, separators=(',', ':'))
    try:
        with open('./config.json', 'w') as file:
            file.write(data)
        print(colored('Email/username saved successfully. Next time you can avoid to insert it again.', 'green'))
    except:
        print(colored('There has been an error saving your email/username offline. Continuing...', 'red'))
        
        
async def extractCookies(page):
    async def extract():
        jar = await page.cookies("https://.api.microsoftstream.com")
        authzCookie = None
        sigCookie = None
        for di in jar:
            if di['name'] == 'Authorization_Api':
                authzCookie = di
            if di['name'] == 'Signature_Api':
                sigCookie = di
        return authzCookie, sigCookie
    
    authzCookie, sigCookie = await extract()
    
    if authzCookie is None or sigCookie is None:
        await asyncio.sleep(5)
        authzCookie, sigCookie = await extract()
    
    if authzCookie is None or sigCookie is None:
        await asyncio.sleep(5)
        authzCookie, sigCookie = await extract()
        
    if authzCookie is None or sigCookie is None:
        print('Unable to read cookies. Try launching one more time, this is not an exact science.')
        return None
        
    return 'Authorization=%s Signature=%s' % (authzCookie["value"], sigCookie["value"])

async def signal_handler(sig, frame):
    print("Terminating...")
    if browser in globals():
        await browser.close()
    exit(1)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(prog='PyDestreamer', description='Python port of destreamer.\nProject originally based on https://github.com/snobu/destreamer.\nFork powered by @vrbadev.', epilog='examples:\n\tStandard usage:\n\t\tpython %(prog)s.py -v https://web.microsoftstream.com/video/...\n', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-v', '--videoUrls', type=str, nargs='+', required=True, help='One or more links to Microsoft Stream videos')
    parser.add_argument('-u', '--username', type=str, required=False, help='Your Microsoft Account e-mail')
    parser.add_argument('-p', '--password', type=str, required=False, help='Your Microsoft Account password')
    parser.add_argument('-o', '--outputDirectory', type=str, required=False, default='videos', help='Save directory for videos and temporary files')
    parser.add_argument('-q', '--quality', type=int, required=False, help='Video Quality, usually [0-5]')
    parser.add_argument('-k', '--noKeyring', type=bool, required=False, default=False, help='Do not use system keyring (saved password)')
    parser.add_argument('-c', '--conn', type=int, required=False, default=16, help='Number of simultaneous connections [1-16]')
    parser.add_argument('--noHeadless', required=False, default=False, action="store_true", help="Don not run Chromium in headless mode")
    parser.add_argument('--manualLogin', required=False, default=False, action="store_true", help="Force login manually")
    parser.add_argument('--overwrite', required=False, default=False, action="store_true", help="Overwrite downloaded temporary files")
    parser.add_argument('--keepTemp', required=False, default=False, action="store_true", help="Do not remove temporary files")

    argv = parser.parse_args(["-h"] if len(sys.argv) == 1 else sys.argv[1:])
    
    sanityChecks()
    
    asyncio.run(downloadVideo(argv.videoUrls, argv.username, argv.password, argv.outputDirectory))
    
    
