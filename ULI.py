# -*- coding: utf-8; tab-width: 4 -*-

import os
import re
import sys
import select
import time
import yaml
import threading
import urllib
import urllib2
import logging

from subprocess import Popen, PIPE, STDOUT
from termcolor import colored

VERSION = (0, 9, 3)
__version__ = '.'.join(map(str, VERSION))

##******************************
## Logging
##******************************

logger = logging.getLogger("ULI")
lh = logging.FileHandler("/var/log/uli_install.log")
lh.setFormatter(logging.Formatter("%(asctime)s %(name)s[%(process)d] \
                                  %(levelname)s: %(message)s"))

logger.addHandler(lh)
logger.setLevel(logging.DEBUG)

##******************************
## Helper functions
##******************************


def execute(command, input=None, expected_rc=0):
    """Run commands and return the result back to the caller"""
    
    try:
        logger.info("Command: %s" % command)
        proc = Popen(command.split(), shell=False, close_fds=True, stdin=PIPE,
                     stdout=PIPE, stderr=STDOUT)
        stdout_value, stderr_value = proc.communicate(input=input)
        
        if proc.returncode != expected_rc:
            logger.error(stdout_value)
            raise Exception(stdout_value)
        else:
            logger.info(stdout_value)
            return stdout_value
    except:
        raise


def execute_pipe(command1, command2, expected_rc=0):
    """Run commands and return the result back to the caller"""
    
    try:
        logger.info("Command: %s | %s" % (command1, command2))
        out = Popen(command1.split(), shell=False, stdin=PIPE, stdout=PIPE,
                     stderr=STDOUT)
        proc = Popen(command2.split(), shell=False, stdin=out.stdout,
                     stdout=PIPE, stderr=STDOUT)
        stdout_value, stderr_value = proc.communicate()
        
        if proc.returncode != expected_rc:
            logger.error(stdout_value)
            print(stdout_value)
            
            raise Exception(stdout_value)
        else:
            logger.info(stdout_value)
            return stdout_value
    except:
        raise


##******************************
## Classes
##******************************


class UliException(Exception):
    """Just a simple, generic exception class for U.L.I."""
    
    def __init__(self, err):
        self.err = err
    
    def __str__(self):
        logger.exception(self.err)
        return repr(self.err)


class Installer:
    """Installer class: This is where the magic happens"""
    
    spinner_stop = False
    
    class Spinner(threading.Thread):
        def run(self):
                global spinner_stop
                sys.stdout.flush()
                type = 0
                while spinner_stop != True:
                        if type == 0:
                            sys.stdout.write("\b/")
                        if type == 1:
                            sys.stdout.write("\b-")
                        if type == 2:
                            sys.stdout.write("\b\\")
                        if type == 3:
                            sys.stdout.write("\b|")
                        type += 1
                        if type == 4:
                            type = 0
                        sys.stdout.flush()
                        time.sleep(0.2)
    
    def __init__(self, after_reload=False):
        
        global spinner_stop
        
        self.root = '/install'
        if not os.path.exists(self.root):
            os.mkdir(self.root)
        
        self.backend = self.__get_backend_addr()
        self.download_url = "http://%s/U.L.I." % self.backend
        self.plugin_url = "http://%s/U.L.I./ULI_Plugins.py" % self.backend
        self.mac_escaped = self.__get_mac_addr().replace(':', '_').lower()
        self.local_config = os.path.join(os.path.dirname(__file__), 'uli.yaml')
        self.msg_length = 0
        self.spinner_active = False
        self.nfs_mount = "/mnt/images"
    
    def __print(self, msg, color=None, nl=True, attr=None):
        """Print colored messages to STDOUT"""
        if nl:
            print(colored(msg, color, attrs=attr))
        else:
            print(colored(msg, color, attrs=attr)),
        sys.stdout.flush()
    
    def __error(self, msg):
        """Print errors to STDOUT and raise"""
        print(colored("\n[error] %s\n" % msg, "red", attrs=["bold"]))
        sys.stdout.flush()
        raise UliException(msg)
    
    def __get_mac_addr(self):
        """Get MAC address of eth0"""
        
        MAC = re.compile('^\s+link\/ether\s+([0-9a-fA-F\:]+)\s+')
        ipd = execute('/sbin/ip addr list eth0')
        for i in ipd.splitlines():
            if MAC.match(i):
                return MAC.match(i).group(1)
    
    def __get_backend_addr(self):
        """Get backend IP from routing table (default gw)"""
        
        GW = re.compile(
                    r'^default\svia\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s')
        routes = execute('/sbin/ip route list')
        for r in routes.splitlines():
            if GW.match(r):
                return GW.match(r).group(1)
    
    def __get_screen_dim(self):
        """Return lines and columns auf current terminal"""
        
        try:
            return map(int, os.popen('stty size', 'r').read().split())
        except OSError:
            logger.error("Failed to get terminal size (Fallback: 80x24)")
            return [24, 80]
    
    def __url_exists(self, url):
        """Raise if URL is not valid"""
        
        try:
            r = urllib2.urlopen(url)
            return True
        except urllib2.URLError, e:
            if not hasattr(e, "code"):
                raise
            else:
                return False
    
    def __url_fetch(self, url, target):
        """Download item from url to target"""
        
        d = urllib.urlretrieve(url, target)
        return os.path.exists(d[0])
    
    def start_task(self, msg, spinner=True):
        """Print task description and initialize the spinner"""
        
        if spinner:
            progress = self.Spinner()
            global spinner_stop
            spinner_stop = False
        
        output = ">> %s  " % msg
        self.msg_length = len(output)        
        colored_output = output.replace(">>", colored(">>", "cyan", attrs=["bold"]))
        
        self.__print(colored_output, None, False)
        
        if spinner:
            self.spinner_active = True
            progress.start()
    
    def stop_task(self, state, spinner=True):
        """Print task result and terminate spinner"""
        
        if spinner:
            global spinner_stop
            spinner_stop = True
        
        s_map = {'ok': ('[ ok ]', 'green',),
                 'failed': ('[ !! ]', 'red',),
                 'warning': ('[ !? ]', 'red',),
                 'skip': ('[ -- ]', 'yellow',),
                }
        
        ws = " " * (self.__get_screen_dim()[1] - self.msg_length - len(s_map[state][0]))
        self.__print("\b %s%s" % (ws, s_map[state][0]),
                                  s_map[state][1], attr=["bold"])
        
        if spinner:
            self.spinner_active = False
    
    def bootstrap(self):
        """This is the bootstrap"""
        
        try:
            self.download_config()
            self.parse_config()
            
            if self.config['global']['interactive'] is True:
                self.mount_nfs()
                self.image_selection()
            
            self.verify_disks()
            self.partitioning()
            self.mdadm()
            self.lvm()
            self.filesystems()
            self.install()
            self.mount_pseudo()
            self.configure()
            self.grub()
            self.byebye()
        except:
            if self.spinner_active:
                self.stop_task("failed")
                raise
    
    def download_config(self):
        """Config download (personal or fallback)"""
        
        downloaded = False
        configs = {0: {'can_fail': True, 'type': 'host',
                       'cfg': '%s.yaml' % self.mac_escaped,
                       'url': '%s/%s.yaml' %
                        (self.download_url, self.mac_escaped), },
                   1: {'can_fail': False, 'type': 'fallback',
                       'cfg': '00_00_00_00_00_01.yaml',
                       'url': '%s/00_00_00_00_00_01.yaml' %
                        self.download_url, },
                  }
        
        for c in configs:
            self.start_task("Attempting to download %s-config %s" %
                            (configs[c]['type'], configs[c]['cfg']))
            if self.__url_exists(configs[c]['url']):
                try:
                    if self.__url_fetch(configs[c]['url'],
                                          self.local_config):
                        self.stop_task("ok")
                    else:
                        self.stop_task("failed")
                        self.__error("Failed to download %s" %
                                    configs[c]['cfg'])
                except:
                    raise
            else:
                if configs[c]['can_fail']:
                        self.stop_task("skip")
                else:
                    self.stop_task("failed")
                    self.__error("Failed to download config %s => %s" %
                                (configs[c]['cfg'], e))
                    raise
    
    def parse_config(self):
        """Parse the YAML config"""
        
        try:
            self.start_task("Parsing downloaded YAML config")
            self.config = yaml.load(file(self.local_config, 'r'))
            self.stop_task("ok")
        except yaml.YAMLError, e:
            self.stop_task("failed")
            self.__error("Failed to parse YAML config: %s" % e)
            raise
    
    def mount_nfs(self):
        """Mount the NFS images share"""
        
        try:
            self.start_task("Mounting images NFS share")
            if not os.path.isdir("/mnt/images"):
                os.mkdir('/mnt/images')
            if os.path.ismount("/mnt/images"):
                execute("/bin/umount /mnt/images")
            execute("/bin/mount -t nfs %s:/data/images /mnt/images -o intr,bg" % self.backend)
            self.stop_task("ok")
        except Exception, e:
            self.stop_task("failed")
            self.__error("Failed to mount images via NFS: %s" % e)
            raise
    
    def image_selection(self):
        """Display image list and wait for the selection"""
        
        try:
            self.start_task("Interctive mode. Select image\n\n", spinner=False)
            images = sorted(filter(lambda x: os.path.isfile(os.path.join(self.nfs_mount, x)) and not x.startswith('.'), os.listdir(self.nfs_mount)))
            for id, value in enumerate(images):
                self.__print("\t%d) %s" % (id, value))
            
            self.__print("\n\t666) Image from config: %s\n" % self.config['global']['image'])
            choice = "undef"
            
            while True:
                if not choice.isdigit() and (choice not in images or choice != 666):
                    choice = raw_input(">> Selection: ")
                else:
                    choice = int(choice)
                    break
            
            if choice != 666:
                self.config['global']['image'] = images[choice]
            self.__print(">> Set image to '%s'" % images[choice])
        except Exception, e:
            self.stop_task("failed")
            self.__error("Failed to select image: %s" % e)
            raise
    
    def verify_disks(self):
        """Verify all disks are found and sizes match"""
        
        if len(self.config['diskmgmt']['partitions']) > 4:
            self.__error("You cannot create more than 4 partitions in U.L.I")
            raise
        
        try:
            self.start_task("Resetting and verifying disk(s)")
            
            lvm_devices = list(self.config['diskmgmt']['disks'])
            if "lvm" in self.config:
                for v in self.config['lvm']['vg']:
                    vg = self.config['lvm']['vg'][v]
                    for pv in self.config['lvm']['vg'][v]['pv']:
                        lvm_devices.append(pv)
            
            VG_PV = re.compile('^\s+(\w+)\s+(?:%s)' % '|'.join(lvm_devices))
            vgs = execute("/sbin/vgs -o vg_name,pv_name --noheading")
            for v in vgs.splitlines():
                if VG_PV.match(v):
                    execute("/sbin/vgchange -an %s" % VG_PV.match(v).group(1))
            
            execute("/sbin/vgchange -an")
            
            if os.path.exists('/dev/md'):
                for md in os.listdir('/dev/md'):
                    execute("/sbin/mdadm --stop /dev/md/%s" % md)
            
            for i in range(0, 4):
                try:
                    execute("/sbin/mdadm --stop /dev/md%d" % i)
                except:
                    pass
            
            disks_found = []
            DEV = re.compile('^\/\S+\s+(\/dev\/\w+)\s+')
            lshw = execute('/usr/sbin/lshw -C disk -short')
            for i in lshw.splitlines():
                if DEV.match(i):
                    disks_found.append(DEV.match(i).group(1))
            
            for d in self.config['diskmgmt']['disks']:
                if not d in disks_found:
                    self.stop_task("failed")
                    self.__error("Disk %s not found on system (%s)" %
                                (d, ",".join(disks_found)))
                    raise
            
            self.stop_task("ok")
        except:
            self.__error("Failed to prepare disk(s)")
            raise
    
    def make_disk_img(self):
        """Create a new VM disk image"""
        
        if self.config['diskmgmt']['type'] == "vm" and \
           size in self.config['diskmgmt']:
            disk_img = "/data/%s.img" % self.config["global"]["hostname"]
            self.start_task("Creating a new VM disk (%s | %s)" %
                            (disk_img, self.config['diskmgmt']['size']))
            if os.path.exists(disk_img):
                self.stop_task("failed")
                self.__error("Disk image %s already exists!" % disk_img)
            
            ## Calculate free space (bytes + 1G)
            fs_stat = os.statvfs('/data')
            fs_free = (fs_stat.f_bsize * fs_stat.f_bavail) - 1073741824
            
            ## Calculate disk image requirements
            exp_map = {'M': 1024 ** 2, 'G': 1024 ** 3}
            img_size = self.config['diskmgmt']['size'][:-1] * \
                           exp_map[self.config['diskmgmt']['size'][-1]]
            
            if fs_free <= img_size:
                self.stop_task("failed")
                self.__error("Cannot create VM image. Insufficient disk \
                                space (%s < %s)" % (fs_free, img_size))
            
            with open(disk_img, "w") as f:
                f.truncate(img_size)
            self.stop_task("ok")
            
            os.path.ismount
    
    def partitioning(self):
        """This is how i act on partitions"""
        
        try:
            partitions = self.config['diskmgmt']['partitions']
            self.start_task("Disk partitioning (%s)" %
                            ", ".join(self.config['diskmgmt']['disks']))
            for d in self.config['diskmgmt']['disks']:
                echo_str = ""
                p_id = 1
                p_ids = {}
                for p in partitions:
                    p_ids[p_id] = partitions[p]['type']
                    if not partitions[p]['size']:
                        partitions[p]['size'] = ''
                    echo_str += ",%s\n" % partitions[p]['size']
                    p_id += 1
                if len(partitions) < 4:
                    echo_str += ",\n"
                echo_str += ";\n"
                execute(command="/sbin/sfdisk %s -uM" % d, input=echo_str)
                
                for id in p_ids:
                    execute("/sbin/sfdisk --id %s %d %s" % (d, id, p_ids[id]))
                execute("/sbin/sfdisk -R %s" % d)
                
                for id in p_ids:
                    execute("/bin/dd if=/dev/urandom of=%s%d bs=5k count=1024"
                            % (d, id))
                    try:
                        execute("/sbin/mdadm --zero-superblock %s%d" % (d, p_id))
                    except:
                        pass
            
            self.stop_task("ok")
        except:
            self.stop_task("failed")
            raise
    
    def mdadm(self):
        """Software raid"""
        
        self.start_task("Creating software raid")
        if self.config['diskmgmt']['type'] != "md":
            self.stop_task("skip")
            return
        
        for p_id in self.config['diskmgmt']['partitions']:
            md_id = p_id - 1
            devs = ""
            if os.path.exists("/dev/md%d" % md_id):
                execute("/sbin/mdadm --stop /dev/md%d" % md_id)
            
            for d in self.config['diskmgmt']['disks']:
                devs += "%s%d " % (d, p_id)
                try:
                    execute("/sbin/mdadm --zero-superblock %s%d" % (d, p_id))
                except:
                    pass
            
            execute("/sbin/mdadm --create --force --metadata=0.90 --verbose \
                     /dev/md%d --level=1 --auto=yes --raid-devices=2 %s" %
                     (md_id, devs))
        self.stop_task("ok")
    
    def lvm(self):
        """Logical volume stuff"""
        
        self.start_task("Creating LVM infrastructure")
        if "lvm" not in self.config:
            self.stop_task("skip")
            return
        
        for v in self.config['lvm']['vg']:
            vg = self.config['lvm']['vg'][v]
            for pv in vg['pv']:
                execute("/sbin/pvcreate -ff -y %s" % pv)
            execute("/sbin/vgcreate %s %s" % (v, " ".join(vg['pv'])))
            for lv in vg['lv']:
                execute("/sbin/lvcreate -n %s -L %s %s" %
                        (lv, vg['lv'][lv], v))
        
        self.stop_task("ok")
    
    def filesystems(self):
        
        opts = {"ext2": "-F", "ext3": "-F", "reiserfs": "-f"}
        
        self.start_task("Creating and mounting filesystems")
        if "fs" not in self.config:
            self.stop_task("failed")
            self.__error("fs key is missing in config but required!")
            raise
        
        try:
            for fs in sorted(self.config['fs']):
                if fs == "none":
                    execute("/sbin/mkswap %s" % self.config['fs'][fs]['dev'])
                    continue
                stripped_fs = fs.lstrip('/')
                if not os.path.exists(os.path.join(self.root, stripped_fs)):
                    os.mkdir(os.path.join(self.root, stripped_fs))
                execute("/sbin/mkfs.%s %s %s" %
                        (self.config['fs'][fs]['type'],
                         opts[self.config['fs'][fs]['type']],
                         self.config['fs'][fs]['dev']))
                execute("/bin/mount -t %s %s %s" %
                        (self.config['fs'][fs]['type'],
                         self.config['fs'][fs]['dev'],
                         os.path.join(self.root, stripped_fs)))
            self.stop_task("ok")
        except:
            self.stop_task("failed")
            raise
    
    def install(self):
        
        try:
            self.start_task("Installing %s" % self.config['global']['image'])
            execute("/bin/tar -C %s -xjSpf %s/%s" % (self.root, self.nfs_mount, self.config['global']['image']))
            
            #self.start_task("Downloading and installing %s" %
            #                self.config['global']['image'].split('/')[-1])
            # 
            #execute_pipe("/usr/bin/ssh -x install@%s cat %s" %
            #             (self.backend, self.config['global']['image']),
            #              "tar -C %s -xjpSf -" % self.root)
            self.stop_task("ok")
        except:
            self.stop_task("failed")
            raise
    
    def mount_pseudo(self):
        
        try:
            self.start_task("Mounting pseudo filesystems")
            if not os.path.exists(os.path.join(self.root, 'proc')):
                os.mkdir(os.path.join(self.root, 'proc'))
            if not os.path.exists(os.path.join(self.root, 'sys')):
                os.mkdir(os.path.join(self.root, 'sys'))
            execute("/bin/mount -t proc -o bind /proc %s" %
                    os.path.join(self.root, 'proc'))
            execute("/bin/mount -t sysfs -o bind /sys %s" %
                    os.path.join(self.root, 'sys'))
            self.stop_task("ok")
        except:
            self.stop_task("failed")
            raise
    
    def configure(self):
        """Update/create system configs"""
        
        self.start_task("System configuration")
        
        if "net" in self.config:
            os.chdir("%s/etc/init.d" % self.root)
            c = open("%s/etc/conf.d/net" % self.root, 'w')
            c.write('modules=( "iproute2")\n')
            
            for nic in sorted(self.config['net']):
                if not os.path.exists("net.%s" % nic):
                    os.symlink("net.lo", "net.%s" % nic)
                
                c.write('config_%s=( "%s" )\n' %
                        (nic, self.config['net'][nic]['ip']))
                if 'routes' in self.config['net'][nic]:
                    c.write('routes_%s=( "%s" )\n' %
                            (nic, self.config['net'][nic]['routes']))
                
                execute("/usr/bin/chroot %s /sbin/rc-update add net.%s default" % (self.root, nic))
            c.close()
        
        c = open("%s/etc/conf.d/hostname" % self.root, 'w')
        c.write('HOSTNAME="%s"\n' % self.config['global']['hostname'])
        c.close()
        
        c = open("%s/etc/hosts" % self.root, 'w')
        c.write("127.0.0.1\t%s.%s %s localhost\n" %
                (self.config['global']['hostname'],
                 self.config['global']['domainname'],
                 self.config['global']['hostname']))
        c.close()
        
        c = open("%s/etc/fstab" % self.root, 'w')
        c.write("## Created by U.L.I.\n\n")
        for fs in sorted(self.config['fs']):
            default_opts = "noatime"
            if self.config['fs'][fs]['type'] == "swap":
                default_opts = "sw"
            c.write("%s\t\t%s\t%s\t%s\t0 0\n" %
                    (self.config['fs'][fs]['dev'],
                     fs,
                     self.config['fs'][fs]['type'],
                     default_opts))
        c.write("\nshm\t/dev/shm\ttmpfs\tnodev,nosuid,noexec\t0 0\n")
        c.write("proc\t/proc\tproc\tdefaults\t0 0\n")
        c.write("sysfs\t/sys\tsysfs\tnosuid,nodev,noexec,relatime\t0 0\n")
        c.close()
        
        c = open("%s/boot/grub/grub.conf" % self.root, 'w')
        c.write("default 0\ntimeout 10\n\n")
        c.write("title Gentoo Linux\n")
        c.write("root (hd0,0)\n")
        c.write("kernel /boot/vmlinuz root=%s\n\n" % self.config["fs"]["/"]["dev"])
        c.close()
        
        self.stop_task("ok")
    
    def grub(self):
        """Install grub"""
        
        self.start_task("Installing GRUB bootloader")
        c = 0
        for d in self.config['diskmgmt']['disks']:
            execute(command="/sbin/grub --batch --no-curses --no-floppy",
                    input="find /boot/grub/stage1\ndevice (hd%d) %s\nroot \
                          (hd%d,0)\nsetup (hd%d)\nquit\n" % (c, d, c, c))
            c += 1
        self.stop_task("ok")
    
    def plugins(self):
        """Download and run plugins"""
        
        self.start_task("Downloading plugins")
        if self.__url_exists(self.plugin_url):
            try:
                if not self.__url_fetch(self.plugin_url, self.local_plugin):
                    self.stop_task("failed")
                    self.__error("Failed to download %s" % self.download_url)
                    raise
                self.stop_task("ok")
            except:
                self.stop_task("failed")
                raise
    
    def byebye(self):
        """Say bye bye"""
        
        print(colored("""
            .--------------. 
    .--.   (    Bye bye!    ) 
   |o_o |   .--------------´
   |:_/ |  ´ 
  //   \ \ 
 (| ULI | ) 
/'\_   _/`\ 
\___)=(___/""", color="cyan"))
        print

if __name__ == "__main__":
    print("This is a lib not a executable")
    sys.exit(1)
