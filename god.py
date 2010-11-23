"""Hi there! It's me, God"""

import os
import sys
import time
import urllib
import urllib2

from termcolor import colored
import ULI

########################################
## Header
########################################

START_VERSION = ULI.VERSION

os.system("clear")

print("#" * 60)
print("##")
print("## %s" % colored("U.L.I. - Unattended Linux Installer", "cyan", attrs=["bold"]))
print("## ===================================")
print("##")
print("## Author  : Daniel Kerwin (daniel@linuxaddicted.de)")
print("## Version : %s" % ULI.__version__)
print("##")
print("#" * 60)
print

U = ULI.Installer()

########################################
## Self update of ULI.py
########################################

try:
    U.start_task("Connection to backend server %s" % U.download_url)
    r = urllib2.urlopen("%s/ULI_2.py" % U.download_url)
    U.stop_task("ok")
except urllib2.URLError, e:
    U.stop_task("failed")
    if not hasattr(e, "code"):
        raise
    else:
        U.stop_task("failed")
        U._error("Failed to download ULI.py update: %s" % e)
        raise

try:
    U.start_task("Self-updating U.L.I. from backend")
    dl = urllib.urlretrieve("%s/ULI_2.py" % U.download_url, os.path.join(os.path.dirname(__file__), 'ULI_UPDATE.py'))
    if not os.path.exists(dl[0]):
        U.stop_task("failed")
        U._error("Failed to download ULI.py")
    else:
        U.stop_task("ok")
except:
    raise

import ULI_UPDATE
UPDATE_VERSION = ULI_UPDATE.VERSION

if UPDATE_VERSION > START_VERSION:
    U = ULI_UPDATE.Installer()
    U.start_task("Switching U.L.I. version (%s > %s)" % ('.'.join(map(str, UPDATE_VERSION)), '.'.join(map(str, START_VERSION))))
    time.sleep(0.5)
    U.stop_task("ok")
else:
    U.start_task("Skipped U.L.I. update (%s == %s)" % ('.'.join(map(str, UPDATE_VERSION)), '.'.join(map(str, START_VERSION))))
    time.sleep(0.5)
    U.stop_task("skip")

########################################
## Run the install
########################################

U.bootstrap()

sys.exit(0)