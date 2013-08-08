""" ==========================================================
File:        WakaTime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  WakaTi.me <support@wakatime.com>
Website:     https://www.wakati.me/
==========================================================="""

__version__ = '0.3.3'

import sublime
import sublime_plugin

import glob
import os
import platform
import sys
import time
import threading
import uuid
from os.path import expanduser, dirname, realpath, isfile, join, exists


# globals
ACTION_FREQUENCY = 5
ST_VERSION = int(sublime.version())
PLUGIN_DIR = dirname(realpath(__file__))
API_CLIENT = '%s/packages/wakatime/wakatime-cli.py' % PLUGIN_DIR
SETTINGS_FILE = 'WakaTime.sublime-settings'
SETTINGS = {}
LAST_ACTION = 0
LAST_FILE = None
BUSY = False


sys.path.insert(0, join(PLUGIN_DIR, 'packages', 'wakatime'))
import wakatime


def setup_settings_file():
    """ Convert ~/.wakatime.conf to WakaTime.sublime-settings
    """
    global SETTINGS
    # To be backwards compatible, rename config file
    SETTINGS = sublime.load_settings(SETTINGS_FILE)
    api_key = SETTINGS.get('api_key', '')
    if not api_key:
        api_key = ''
        try:
            with open(join(expanduser('~'), '.wakatime.conf')) as old_file:
                for line in old_file:
                    line = line.split('=', 1)
                    if line[0] == 'api_key':
                        api_key = str(line[1].strip())
            try:
                os.remove(join(expanduser('~'), '.wakatime.conf'))
            except:
                pass
        except IOError:
            pass
    SETTINGS.set('api_key', api_key)
    sublime.save_settings(SETTINGS_FILE)


def get_api_key():
    """If api key not set, prompt user to enter one then save
    to WakaTime.sublime-settings.
    """
    global SETTINGS
    api_key = SETTINGS.get('api_key', '')
    if not api_key:
        def got_key(text):
            if text:
                api_key = str(text)
                SETTINGS.set('api_key', api_key)
                sublime.save_settings(SETTINGS_FILE)
        window = sublime.active_window()
        if window:
            window.show_input_panel('Enter your WakaTi.me api key:', '', got_key, None, None)
        else:
            print('Error: Could not prompt for api key because no window found.')
    return api_key


def enough_time_passed(now):
    if now - LAST_ACTION > ACTION_FREQUENCY * 60:
        return True
    return False


def handle_write_action(view):
    thread = SendActionThread(view.file_name(), isWrite=True)
    thread.start()


def handle_normal_action(view):
    thread = SendActionThread(view.file_name())
    thread.start()


class SendActionThread(threading.Thread):

    def __init__(self, targetFile, isWrite=False, force=False):
        threading.Thread.__init__(self)
        self.targetFile = targetFile
        self.isWrite = isWrite
        self.force = force

    def run(self):
        sublime.set_timeout(self.check, 0)

    def check(self):
        global LAST_ACTION, LAST_FILE
        if self.targetFile:
            self.timestamp = time.time()
            if self.force or self.isWrite or self.targetFile != LAST_FILE or enough_time_passed(self.timestamp):
                LAST_FILE = self.targetFile
                LAST_ACTION = self.timestamp
                self.send()

    def send(self):
        api_key = get_api_key()
        if not api_key:
            return
        cmd = [
            API_CLIENT,
            '--file', self.targetFile,
            '--time', str('%f' % self.timestamp),
            '--plugin', 'sublime-wakatime/%s' % __version__,
            '--key', str(bytes.decode(api_key.encode('utf8'))),
            '--verbose',
        ]
        if self.isWrite:
            cmd.append('--write')
        #print(cmd)
        wakatime.main(cmd)


def plugin_loaded():
    setup_settings_file()


# need to call plugin_loaded because only ST3 will auto-call it
if ST_VERSION < 3000:
    plugin_loaded()


class WakatimeListener(sublime_plugin.EventListener):

    def on_post_save(self, view):
        global BUSY
        if not BUSY:
            BUSY = True
            handle_write_action(view)
            BUSY = False

    def on_activated(self, view):
        global BUSY
        if not BUSY:
            BUSY = True
            handle_normal_action(view)
            BUSY = False

    def on_modified(self, view):
        global BUSY
        if not BUSY:
            BUSY = True
            handle_normal_action(view)
            BUSY = False
