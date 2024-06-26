#!/usr/bin/env python
import os
import subprocess
import getpass
import re
from subprocess import check_output
#to remove, disable or uninstall unused filesystems
def disable_filesystem_loading():
    fsList = ["squashfs", "cramfs", "udf", "usb-storage"]
    for l_mname in fsList:
        install_line = f"install {l_mname} /bin/false\n"
        modprobe_conf_path = f"/etc/modprobe.d/{l_mname}.conf"

        try:
            with open(modprobe_conf_path, 'r') as f:
                if not any(install_line in line for line in f):
                    with open(modprobe_conf_path, 'a') as f:
                        print(f" - setting module: \"{l_mname}\" to be not loadable")
                        f.write(install_line)
                    
                    print(f" - unloading module \"{l_mname}\"")
                    subprocess.run(["modprobe", "-r", l_mname])
                else:
                    print(f"{l_mname} is set to be not loadable")
        except FileNotFoundError:
            with open(modprobe_conf_path, 'w') as f:
                print(f" - setting module: \"{l_mname}\" to be not loadable")
                f.write(install_line)
        
            print(f" - unloading module \"{l_mname}\"")
            subprocess.run(["modprobe", "-r", l_mname])
        

        blacklist_line = f"blacklist {l_mname}\n"
        with open(modprobe_conf_path, 'r') as f:
            if not any(blacklist_line in line for line in f):
                with open(modprobe_conf_path, 'a') as f:
                    print(f" - deny listing \"{l_mname}\"")
                    f.write(blacklist_line)
            else:
                print(f"{l_mname} is blacklisted ")

#disabling automounting of file systems
def disable_autofs():
    result = subprocess.run(["dpkg","-s","autofs"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if result.returncode==0:
        print("autofs installed chekcing dependencies...")
        depRes = subprocess.run(["apt-cache", "depends", "autofs"], capture_output=True, text=True)
        rdepRes = subprocess.run(["apt-cache", "depends", "autofs"], capture_output=True, text=True)

        if "Depnds" in depRes.stdout or "Reverse Depends" in rdepRes.stdout:
            print("Dependencies found for autofs, so masking and stopping the module..")
            subprocess.run(["system", "stop", "autofs"])
            subprocess.run(["system", "mask", "autofs"])
        else:
            print("No dependencies found, uninstalling  autofs")
            subprocess.run(["apt", "purge", "autofs"])
    else:
        print("autofs not installed, no action required!")


def installingAIDE():
    is_installed = subprocess.run(["dpkg", "-s", "aide"], stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if is_installed.returncode == 0:
        print("AIDE is already installed.")
    else:
        print("Installing AIDE")
        aideCMD = ["sudo","DEBIAN_FRONTEND=noninteractive","apt","install","aide", "aide-common","-y"]
        aideinstalled = subprocess.run(aideCMD, stdout=subprocess.DEVNULL)
        if aideinstalled.returncode==0:
            print("AIDE installed successfully!")
        else:
            print(aideinstalled.std)
            print("Error in installing AIDE, cheack manually!")
#Periodic checking of the filesystem integrity to detect changes to the filesystem.
        
def schedulingAideChecks():
    #/etc/systemd/system/aidecheck.service
    servicePath = "/etc/systemd/system/aidecheck.service"
    timerPath = "/etc/systemd/system/aidecheck.timer"
    service_content = """[Unit]
Description=Aide Check

[Service]
Type=simple
ExecStart=/usr/bin/aide.wrapper --config /etc/aide/aide.conf --check

[Install]
WantedBy=multi-user.target
"""
    timer_content = """[Unit]
Description=Aide check every day at 5AM

[Timer]
OnCalendar=*-*-* 05:00:00
Unit=aidecheck.service

[Install]
WantedBy=multi-user.target
"""
    if not os.path.exists(servicePath) or service_content != open(servicePath).read():
        print("Creating serviceFile for aide checks!")
        with open(servicePath, mode='w') as ServiceFile:
            ServiceFile.write(service_content)
    else:
        print("ServiceFile for AIDE checks exist!")
    if not os.path.exists(timerPath) or timer_content != open(timerPath).read():
        print("Creating timerFile for AIDE checks!")
        with open(timerPath, mode="w") as timerFile:
            timerFile.write(timer_content)
    else:
        print("Timer file for AIDE checks already exists!")
    subprocess.run("chown root:root /etc/systemd/system/aidecheck.*", shell=True)
    subprocess.run("chmod 0644 /etc/systemd/system/aidecheck.*", shell=True)
    subprocess.run("systemctl daemon-reload", shell=True)
    subprocess.run("systemctl enable aidecheck.service", shell=True)
    subprocess.run("systemctl --now enable aidecheck.timer", shell=True)

def bootloaderPassword():
    if not os.path.exists("/etc/grub.d/CIS"):
        print("Setting bootloader password...")
        password = getpass.getpass("Enter password for your bootloader: ")
        password_confirm = getpass.getpass("Re-enter password: ")
        if password != password_confirm:
            print("Passwords do not match. Please try again.")
            bootloaderPassword()
        else:
            command = ["grub-mkpasswd-pbkdf2"]
            result = subprocess.run(command, input=f"{password}\n{password_confirm}\n", capture_output=True, text=True)

            if result.returncode == 0:
                conf_content = f"""cat <<EOF 
                set superusers="bootloader" 
                password_pbkdf2 bootloader {result.stdout[68:]}
                EOF
                """
                with open("/etc/grub.d/CIS","w") as configFile:
                    configFile.write(conf_content)
                print("Bootloader password is set")
            else:
                print("Error , password could not be set, try manually!")
                print(result.stderr)
    else:
        print("Bootloader password is already set!")

def bootconfigPermission():
     print("Restricting permissions on bootloader config files")
     subprocess.run(["chown","root:root","/boot/grub/grub.cfg"])
     subprocess.run(["chmod","u-wx,go-rwx","/boot/grub/grub.cfg"])

def setTerminalvalue():
    path = "/etc/sysctl.conf"
    flag=False
    with open(path,"r") as confFile:
        confLines = confFile.readlines()
    for line in confLines:
        if line == "kernel.randomize_va_space = 2\n":
            flag=True
            break
    if flag == True:
        print("ASLR randomization is set")
    else:
        print("Setting up ASLR randomization...")
        with open(path,"a") as file:
            file.write("kernel.randomize_va_space = 2\n")
        subprocess.run(["sysctl","-w","kernel.randomize_va_space=2"])
        print("Done...")

def prelinkRmBinaryrestore():
     subprocess.run("prelink -ua", shell=True)
     subprocess.run(["apt", "purge","prelink"])

def disableAutomaticErrorReporting():
    
    print("Checking for automatic error reporting system...")
    apportPath = "/etc/default/apport"
    with open(apportPath, "r") as apportFile:
        lines = apportFile.readlines()
    enable_found = False
    for i in range(len(lines)):
        if lines[i].startswith("enabled=0"):
            enable_found = True
            break
    if not enable_found:
        print("Disabling apport service..")
        for i in range(len(lines)):
            if lines[i].startswith("enabled="):
                lines[i] = "enabled=0\n"
                break
        with open(apportPath, "w") as apportFile:
            apportFile.writelines(lines)
        subprocess.run(["systemctl", "stop", "apport.service"])
        subprocess.run(["systemctl", "--now", "disable", "apport.service"])
    else:
        print("Automatic error reporting system is disabled!")


def coreDumpRestriction():
    pathLimits = "/etc/security/limits.conf"
    pathsysctl = "/etc/sysctl.conf"
    with open(pathLimits, "r") as limitsFile:
        lines = limitsFile.readlines()
    hard_flag = False
    for line in lines:
        if line == "*\thard\tcore\t0\n":
            hard_flag = True
            break
    if hard_flag:
        print("Core dumps for all user is Disabled!")
    else:
        print("Disabling core dump for all users...")
        for i in range(len(lines)):
            if lines[i].startswith("# End of file\n"):
                lines[i] = "*\thard\tcore\t0\n# End of file\n"
        with open(pathLimits, "w") as limitsFile:
            limitsFile.writelines(lines)

    suid_flag = False
    with open(pathsysctl,"r") as sysctlFile:
        sysLines= sysctlFile.readlines()
    for line in sysLines:
        if line == "fs.suid_dumpable = 0\n":
            suid_flag=True
            break
    if suid_flag:
        print("Core dumps from suid binaries been disabled!")
    else:
        print("Disabling core dumps from suid bnaries...")
        with open(pathsysctl, "a") as sysctlFile:
            sysctlFile.write("fs.suid_dumpable = 0\n")
        subprocess.run(["sysctl","-w","fs.suid_dumpable=0"])

"""
    coreDumpPath = "/etc/systemd/coredump.conf"
    storage_modified = False
    process_size_max_modified = False
    try:
        with open(coreDumpPath, "r") as coreDumpFile:
            coreDumpLines = coreDumpFile.readlines()        
        for line in coreDumpLines:
            if "Storage=none" in line:
                storage_modified = True
            if "ProcessSizeMax=0" in line:
                process_size_max_modified = True
    except:
        print("config file for core dump don't exist")
    if not (storage_modified and process_size_max_modified):
        print("Modifying/creating config file to limit the core dump sixe to 0 Byte...")
        with open(coreDumpPath, "r") as coreDumpFile:
            coreDumpLines = coreDumpFile.readlines()
        with open(coreDumpPath, "w") as coreDumpFile:
            for i in range(len(coreDumpLines)):
                if coreDumpLines[i].startswith("#Storage="):
                    coreDumpLines[i] = "Storage=none\n"
                if coreDumpLines[i].startswith("#ProcessSizeMax="):
                    coreDumpLines[i] = "ProcessSizeMax=0\n"
            coreDumpFile.writelines(coreDumpLines)
        subprocess.run(["systemctl", "daemon-reload"])
    else:
        print("Core dump size is restricted to 0 Byte!")
"""
    
def configureApparmor():
    result = subprocess.run(["dpkg","-s", "apparmor"],stdout=subprocess.DEVNULL)
    if result.returncode==0:
        print("apparmor is already installed!")
        if os.path.exists("/usr/sbin/aa-enforce"):
            print("apparmor utils are avilable")
        else:
            subprocess.run(["apt","install", "apparmor-utils","-y"],stdout=subprocess.DEVNULL)
    else:
        print("installing Apparmor...")
        subprocess.run(["apt", "install","apparmor","-y"],stdout=subprocess.DEVNULL)
        subprocess.run(["apt", "install","apparmor-utils","-y"],stdout=subprocess.DEVNULL)

    apparmorPath = "/etc/default/grub"
    with open(apparmorPath,"r") as apparmorFile:
        apparmorLines = apparmorFile.readline()
    apparmor_flag = False
    for line in apparmorLines:
        if line ==  """
\n""":
            apparmor_flag=True
            break

    if apparmor_flag:
        print("Apparmor security profile already enabled and enforced!")
    else:
        print("enabling and enforcing Apparmor security profile...")
        for i in range(len(apparmorLines)):
            if apparmorLines[i].startswith("GRUB_CMDLINE_LINUX="):
                apparmorLines[i] = """GRUB_CMDLINE_LINUX="apparmor=1 security=apparmor"\n"""
        with open(apparmorPath,"w") as apparmorFile:
            apparmorFile.writelines(apparmorLines)
        subprocess.run(["update-grub"])
        subprocess.run("aa-enforce /etc/apparmor.d/*",shell=True)


def cmdLineBanners():
    cmdMsg = "Authorized uses only. All activity may be monitored and reported.\n"
    with open("/etc/issue", "r") as cmdFile:
        if cmdMsg not in cmdFile.read():
            print("Setting Command line banner..")
            with open("/etc/issue", "a") as cmdFile:
                cmdFile.write(cmdMsg)
        else:
            print("Command Line banner is already set!")
    with open("/etc/issue.net", "r") as cmdFile:
        if cmdMsg not in cmdFile.read():
            with open("/etc/issue.net", "a") as cmdFile:
                cmdFile.write(cmdMsg)
    if os.path.exists("/etc/issue"):
        subprocess.run("chown root:root $(readlink -e /etc/issue)", shell=True)
        subprocess.run("chmod u-x,go-wx $(readlink -e /etc/issue)", shell=True)
    if os.path.exists("/etc/issue.net"):
        subprocess.run("chown root:root $(readlink -e /etc/issue.net)", shell = True)
        subprocess.run("chmod u-x,go-wx $(readlink -e /etc/issue.net)", shell = True)


#<-------------------WARNING!!!!!!------------->
#--------RUN below funtion only when GUI is not required-------
def removeGDM():
    subprocess.run(["apt", "purge","gdm3"])
#<------------------------------------------------------------->

def loginBannerMsg():
    l_pkgoutput = ""
    if os.system("command -v dpkg-query > /dev/null 2>&1") == 0:
        l_pq = "dpkg-query -W"
    elif os.system("command -v rpm > /dev/null 2>&1") == 0:
        l_pq = "rpm -q"
    else:
        return

    l_pcl = ["gdm", "gdm3"]
    for l_pn in l_pcl:
        if os.system(f"{l_pq} {l_pn} > /dev/null 2>&1") == 0:
            l_pkgoutput += f"\n - Package: \"{l_pn}\" exists on the system\n - checking configuration"

    if l_pkgoutput:
        l_gdmprofile = "gdm"  
        l_bmessage = "'Authorized uses only. All activity may be monitored and reported'"

        if not os.path.isfile(f"/etc/dconf/profile/{l_gdmprofile}"):
            print(f"Creating profile \"{l_gdmprofile}\"")
            with open(f"/etc/dconf/profile/{l_gdmprofile}", 'w') as profile_file:
                profile_file.write(f"user-db:user\nsystem-db:{l_gdmprofile}\nfile-db:/usr/share/{l_gdmprofile}/greeter-dconf-defaults")

        if not os.path.isdir(f"/etc/dconf/db/{l_gdmprofile}.d/"):
            print(f"Creating dconf database directory \"/etc/dconf/db/{l_gdmprofile}.d/\"")
            os.makedirs(f"/etc/dconf/db/{l_gdmprofile}.d/")
        

        l_kfile = f"/etc/dconf/db/{l_gdmprofile}.d/01-banner-message"
        dbPath = f"/etc/dconf/db/{l_gdmprofile}.d/"
        flag=False
        file = False
        for file in os.listdir(dbPath):
            filePath = os.path.join(dbPath,file)
            if os.path.isfile(filePath):
                for line in open(filePath,"r").readlines():
                    if "banner-message-enable" in line:
                        l_kfile = filePath
                        file = True
                    if "banner-message-enable=true"in line:
                        l_kfile = filePath
                        flag=True
                        break
        if flag ==True:
            if not any("banner-message-text=" in line for line in open(l_kfile)):
                print("Setting login banner message...")
                with open(l_kfile, 'a') as keyfile:
                    keyfile.write(f"\nbanner-message-text={l_bmessage}")
            else:
                print("Login banner message already set")
        else:
            if file==True:
                with open(l_kfile,"r") as bannerFile:
                    bannerLines = bannerFile.readlines()
                if not any("banner-message-text" in line for line in open(l_kfile)):
                    for i in range(len(bannerLines)):
                        if "banner-message-enable" in bannerLines[i]:
                            bannerFile[i] = f"\n[org/gnome/login-screen]\nbanner-message-enable=true\nbanner-message-text={l_bmessage}"
                with open(l_kfile,"w") as bannerFile:
                    bannerFile.writelines(bannerLines)
            else:
                with open(l_kfile,"w") as bannerFile:
                    bannerFile.write(f"\n[org/gnome/login-screen]\nbanner-message-enable=true\nbanner-message-text={l_bmessage}")
        os.system("dconf update")
    else:
        print("\n\n - GNOME Desktop Manager isn't installed\n - Recommendation is Not Applicable\n - No remediation required\n")

def disableLoginUserList():
    gdmProfile = "gdm"
    gdmProfilePath = f"/etc/dconf/profile/{gdmProfile}"
    gdmDbPath = f"/etc/dconf/db/{gdmProfile}.d/"

    if not os.path.isfile(gdmProfilePath):
        print(f"creating {gdmProfile} profile ")
        with open(gdmProfilePath,"w") as gdmProfileFile:
            gdmProfileFile.write(f"user-db:user\nsystem-db:{gdmProfile}\nfile-db:/usr/share/{gdmProfile}/greeter-dconf-defaults")
    if not os.path.isdir(gdmDbPath):
        print("creating database directory fot gdm profile")
        subprocess.run(["mkdir", "f/etc/dconf/db/{gdmProfile}.d/"])

    gdmKeyfileContent = f"\n[org/gnome/login-screen]\n# Do not show the user list\ndisable-user-list=true"
    gdmKeyFilePath = f"{gdmDbPath}00-login-screen"
    flag = False
    fileExist = False       
    for file in os.listdir(gdmDbPath):
        filePath = os.path.join(gdmDbPath,file)
        if os.path.isfile(filePath):
            for line in open(filePath,"r").readlines():
                if "[org/gnome/login-screen/]" in line:
                    gdmKeyFile = filePath
                    fileExist = True
                if "disable-user-list=true" in line:
                    flag = True
    if flag == True:
        print("User list already disabled on Login Screen")
    else:
        if fileExist == True:
            with open(gdmKeyFilePath,"a") as gdmKeyFile:
                gdmKeyFile.write("\n# Do not show the user list\ndisable-user-list=true")
        else:
            with open( gdmKeyFilePath,"w") as gdmKeyFile:
                gdmKeyFile.write(gdmKeyfileContent)

def screenLockIdle():
    keyfilepath = "/etc/dconf/db/gdm.d/00-screensaver"
    idleTime = "900"
    lockTime = "5"
    keyfileContent = f"""# Specify the dconf path\n[org/gnome/desktop/session]\n\n# Number of seconds of inactivity before the screen goes blank\n# Set to 0 seconds if you want to deactivate the screensaver.\nidle-delay = uint32 {idleTime}\n\n# Specify the dconf path\n[org/gnome/desktop/screensaver]\n\n# Number of seconds after the screen is blank before locking the screen\nlock-delay = uint32 {lockTime}\n"""
    
    if not os.path.exists(keyfilepath) or keyfileContent != open(keyfilepath).read():
        print("Creating/updating config file for Idle screen time and Lock time")
        with open(keyfilepath,"w") as Screenfile:
            Screenfile.write(keyfileContent)
        os.system("dconf update")
    else:
        print("Idle-delay and Lock_delay are already set!")
def patternCheckScreen(directory,pattern,something):
    if not directory:
            print(f" {something}-delay is not set, so it cannot be locked\n - Please follow Recommendation \"Ensure GDM screen locks when the user is idle\" and follow this Recommendation again")
    else:
        for root,dirs, files in os.walk(directory):
            for file in files:
                path = os.path.join(root,file)
                try:
                    for line in open(path,"r").readlines():
                        if pattern in line:
                                print(f" {something}-delay is locked in {path} ")
                                return
                except:
                    continue
        print(f"Creating entry to lock {something}-delay")
        path = os.path.join(directory, 'locks', '00-screensaver')
        if os.path.isfile(path):
            with open(path, 'a') as lockFile:
                lockFile.write(f"\n# Lock desktop screensaver {something}-delay setting\n{pattern}\n")
        else:
            os.makedirs(os.path.join(directory, 'locks'), exist_ok=True)
            with open(path, 'w') as lockFile:
                lockFile.write(f"\n# Lock desktop screensaver {something}-delay setting\n{pattern}\n")

def screenLockFile():
    packageInstalled = ""
    if os.system("command -v dpkg-query > /dev/null 2>&1") == 0:
        packageManager = "dpkg-query -W"
    elif os.system("command -v rpm > /dev/null 2>&1") == 0:
        packageManager = "rpm -q"
    else:
        return

    packageList = ["gdm", "gdm3"]
    for package in packageList:
        if os.system(f"{packageManager} {package} > /dev/null 2>&1") == 0:
            packageInstalled += f"\n - Package: \"{package}\" exists on the system\n - Remediating configuration if needed"
    if packageInstalled:
        print(packageInstalled)

        # Look for idle-delay to determine profile in use, needed for remaining tests
        directoryPath = "/etc/dconf/db/"

        keyfileDirectoryidle = None
        keyfileDirectorylock = None
        settingIdle = "idle-delay = uint32"
        settingLock = "lock-delay = uint32"
        idledelayPattern = '/org/gnome/desktop/session/idle-delay'
        lockdelayPattern = "/org/gnome/desktop/screensaver/lock-delay"
        for root, dirs, files in os.walk(directoryPath):
            for file in files:
                    filepath = os.path.join(root,file)
                    try:
                        for line in open(filepath,"r").readlines():
                            if settingIdle in line:
                                keyfileDirectoryidle = root
                                break
                    except:
                        continue
        for root, dirs, files in os.walk(directoryPath):
            for file in files:
                    filepath = os.path.join(root,file)
                    try:
                        for line in open(filepath,"r").readlines():
                            if settingLock in line:
                                keyfileDirectorylock = root
                                break
                    except:
                        continue
        patternCheckScreen(keyfileDirectoryidle,idledelayPattern,"idle")
        patternCheckScreen(keyfileDirectorylock,lockdelayPattern,"lock")
    else:
        print(" - GNOME Desktop Manager package is not installed on the system\n - Recommendation is not applicable")


def findFilepath(directoryPath, tofind):
    for roots, dirs, files in os.walk(directoryPath):
            for file in files:
                for line in open(file,"r").readlines():
                    if tofind in line:
                        return os.path.join(roots,file)
    return "else"
def createupdateEntry(filePath, entryFor, entryValue):
    flag=False
    writeFlag =False
    if os.path.isfile(filePath):
        with open(filePath,"r") as mountFile:
            mountLines = mountFile.readlines()
        for i in range(len(mountLines)):
            if entryValue in mountLines[i]:
                flag = True
            if "[org/gnome/desktop/media-handling]" in mountLines[i]:
                writeFlag = True
                writeline = i
        if flag ==True:
            print(f" {entryFor} is set to false in {filePath}")
        else:
            if writeFlag==True:
                print(f"Creating or updating {entryFor} entry in {filePath}")
                mountLines[writeline] = f"\n[org/gnome/desktop/media-handling]\n{entryValue}\n"
                with open(filePath,"w") as mountFile:
                    mountFile.writelines(mountLines)
    else:
        print(f"Creating or updating {entryFor} entry in {filePath}")
        with open(filePath,"w") as mountFile:
                mountFile.write(f"\n[org/gnome/desktop/media-handling]\n{entryValue}\n")

def disableAutoMounting():
    packageInstalled = ""
    profileName = "gdm"
    if os.system("command -v dpkg-query > /dev/null 2>&1") == 0:
        packageManager = "dpkg-query -W"
    elif os.system("command -v rpm > /dev/null 2>&1") == 0:
        packageManager = "rpm -q"
    else:
        return

    packageList = ["gdm", "gdm3"]
    for package in packageList:
        if os.system(f"{packageManager} {package} > /dev/null 2>&1") == 0:
            packageInstalled += f"\n - Package: \"{package}\" exists on the system\n - Remediating configuration if needed"

    if packageInstalled:
        print(packageInstalled)
        dbPath = "/etc/dconf/db/*.d/"
        mountFilepath = f"/etc/dconf/db/{profileName}.d/00-media-automount"
        mountFilepath2 = f"/etc/dconf/db/{profileName}.d/00-media-automount"
        autorunFilepath = f"/etc/dconf/db/{profileName}.d/00-media-autorun"
        
        
        mountFilepath = findFilepath(dbPath,"automount")
        mountFilepath2 =findFilepath(dbPath,"automount-open")
        autorunFilepath =findFilepath(dbPath,"autorun-never")
        if mountFilepath =="else":
            mountFilepath = f"/etc/dconf/db/{profileName}.d/00-media-automount"
        if mountFilepath2 == "else":
            mountFilepath2 = f"/etc/dconf/db/{profileName}.d/00-media-automount"
        if autorunFilepath == "else":
            autorunFilepath = f"/etc/dconf/db/{profileName}.d/00-media-autorun"

        
        if os.path.isfile(f"/etc/dconf/profile/{profileName}"):
            print(f"dconf database profile exit in: /etc/dconf/profile/{profileName}")
        else:
            print(f"Creating profile \"{profileName}\"")
            with open(f"/etc/dconf/profile/{profileName}", 'w') as profile_file:
                profile_file.write(f"user-db:user\nsystem-db:{profileName}\nfile-db:/usr/share/{profileName}/greeter-dconf-defaults")

        if  os.path.isdir(f"/etc/dconf/db/{profileName}.d/"):
            print(f" dconf database directory in /etc/dconf/db/{profileName}.d/")
        else:
            print(f"Creating dconf database directory \"/etc/dconf/db/{profileName}.d/\"")
            os.makedirs(f"/etc/dconf/db/{profileName}.d/")

        createupdateEntry(mountFilepath,"automount","automount=false")
        createupdateEntry(mountFilepath2,"automount-open","automount-open=false")
        createupdateEntry(autorunFilepath,"autorun-never","autorun-never=true")
        
    else:
        print(" - GNOME Desktop Manager package is not installed on the system\n - Recommendation is not applicable")
    os.system("dconf update")

def patternCheckmount(directory,pattern,something, fileName):
    if not directory:
            print(f" {something} is not set, so it cannot be locked\n - Please follow Recommendation \"Ensure GDM screen locks when the user is idle\" and follow this Recommendation again")
    else:
        for root,dirs, files in os.walk(directory):
            for file in files:
                path = os.path.join(root,file)
                try:
                    for line in open(path,"r").readlines():
                        if pattern in line:
                                print(f" {something} is locked in {path} ")
                                return
                except:
                    continue
        print(f"Creating entry to lock {something}")
        path = os.path.join(directory, 'locks', fileName)
        if os.path.isfile(path):
            with open(path, 'a') as lockFile:
                lockFile.write(f"\n# Lock desktop media-handling {something} setting\n{pattern}")
        else:
            os.makedirs(os.path.join(directory, 'locks'), exist_ok=True)
            with open(path, 'w') as lockFile:
                lockFile.write(f"\n# Lock desktop media-handling {something} setting\n{pattern}")
            
def getDirectory(path,setting):
    for root, dirs, files in os.walk(path):
            for file in files:
                    filepath = os.path.join(root,file)
                    try:
                        for line in open(filepath,"r").readlines():
                            if setting in line:
                                return root
                    except:
                        continue
def mountLockFile():
    packageInstalled = ""
    if os.system("command -v dpkg-query > /dev/null 2>&1") == 0:
        packageManager = "dpkg-query -W"
    elif os.system("command -v rpm > /dev/null 2>&1") == 0:
        packageManager = "rpm -q"
    else:
        return

    packageList = ["gdm", "gdm3"]
    for package in packageList:
        if os.system(f"{packageManager} {package} > /dev/null 2>&1") == 0:
            packageInstalled += f"\n - Package: \"{package}\" exists on the system\n - Remediating configuration if needed"
    if packageInstalled:
        print(packageInstalled)

        # Look for idle-delay to determine profile in use, needed for remaining tests
        directoryPath = "/etc/dconf/db/"

        keyfileDirectorymount = None
        keyfileDirectorymountOpen = None
        keyfileDirectoryautorun = None
        settingmount = "automount"
        settingmountopen = "automount-open"
        settingautorun = "autorun-never"
        mountPattern = '/org/gnome/desktop/media-handeling/aoutomount'
        mountOpenPattern = "/org/gnome/desktop/media-handeling/automount-open"
        autorunPattern = "/org/gnome/desktop/media-handeling/autorun-never"
        
        keyfileDirectorymount =getDirectory(directoryPath,settingmount)
        keyfileDirectorymountOpen = getDirectory(directoryPath,settingmountopen)
        keyfileDirectoryautorun = getDirectory(directoryPath,settingautorun)
        patternCheckmount(keyfileDirectorymount,mountPattern,"automount","00-media-automount")
        patternCheckmount(keyfileDirectorymountOpen,mountOpenPattern,"automount-open","00-media-automount")
        patternCheckmount(keyfileDirectoryautorun,autorunPattern,"autorun-never","00-media-autorun")
    else:
        print(" - GNOME Desktop Manager package is not installed on the system\n - Recommendation is not applicable")

def systemdTimesyncdEnabled():
    isEnabled = subprocess.run(["systemctl", "is-enabled", "systemd-timesyncd.service"], text=True, capture_output=True)
    isActive = subprocess.run(["systemctl", "is-active", "systemd-timesyncd.service"], text=True, capture_output=True)

    if isEnabled.stdout.strip() == "enabled":
        print("systemd-timesyncd.service is enabled\n")
    else:
        print("Enabling systemd-timesyncd.service\n")
        subprocess.run(["systemctl", "unmask", "systemd-timesyncd.service"])

    if isActive.stdout.strip() == "active":
        print("systemd-timesyncd.service is active\n")
    else:
        print("Activating systemd-timesyncd.service\n")
        subprocess.run(["systemctl", "--now", "enable", "systemd-timesyncd.service"])

def AuthTSforsystemdtimesyncd():
    ntpTS = "time.nist.gov"
    ntpFB = "time-a-g.nist.gov time-b-g.nist.gov time-d-g.nist.gov"
    findTS = "NTP="
    findFB = "FallbackNTP="
    confFile = ""
    timeDir = "/etc/systemd/timesyncd.conf.d"
    timeDropin = "/etc/systemd/timesyncd.conf.d/50-timesyncd.conf"

    for root,dirs,files in os.walk("/etc/systemd/"):
        for file in files:
            if file.endswith(".conf"):
                filepath = os.path.join(root,file)
                try:
                    for line in open(filepath,"r").readlines():
                        if findTS in line or findFB in line:
                            confFile = filepath
                            break
                except:
                    continue
    print(confFile)
    with open(confFile,"r") as timeFile:
        timeLines = timeFile.readlines()

    for i in range(len(timeLines)):
        if findTS in timeLines[i]:
            if ntpTS in timeLines[i]:
                print("NTP time server is set")
                break
            else:
                print("Setting NTP time Server")
                timeLines[i] = f"NTP=time.nist.gov\n"
                break
    for i in range(len(timeLines)):
        if findFB in timeLines[i]:
            if ntpFB in timeLines[i]:
                print("fallback  NTP servers are set ")
                break
            else:
                print("Setting NTP fallback Servers")
                timeLines[i] = f"FallbackNTP=time-a-g.nist.gov time-b-g.nist.gov time-d-g.nist.gov\n"
                break
    with open(confFile, "w") as timeFile:
        timeFile.writelines(timeLines)
    flag=0
    if os.path.isdir(timeDir):
        for file in os.listdir(timeDir):
            filepath = os.path.join(timeDir,file)
            for line in open(filepath, "r").readlines():
                if ntpTS in line:
                    print(f"time server set at in drop-in file  {filepath}")
                    flag+=1
                if ntpFB in line:
                    print(f"Fallback time sever server set in drop-in file {filepath}")
                    flag+=1
                if flag==2:
                    break
            if flag==2:
                break
    else:
        os.makedirs(timeDir)
        print("creating/updating drop-in files for NTP time servers and fallback server")
        with open(timeDropin,"w") as timeFile:
            timeFile.write(f"[Time]\n{findTS+ntpTS}\n{findFB+ntpFB}")
    os.system("systemctl try-reload-or-restart systemd-timesyncd")

#function to remove unessesarry packages
def removePackages():
    def uninstallservices( toUninstall,Sname):
        print(f"Checking {Sname}...")
        cmd = f"dpkg-query -W -f='${{binary:Package}}\t${{Status}}\t${{db:Status-Status}}\n' {toUninstall}"
        isinstalled = subprocess.run(cmd,shell=True,text=True,capture_output=True)
        install_status =[]
        for line in isinstalled.stdout.splitlines():
            install_status.append(line.split("\t")[1].split()[2].lower())
            print(f"{Sname} is installed, removing {Sname}...")
            uninstalled= subprocess.run(["apt","purge",f"{toUninstall}","-y"],stdout=subprocess.DEVNULL)
            if uninstalled.returncode==0:
                print(f"{Sname} is removed form system")
                print("-"*64)
                return
            else:
                print(f"{Sname} was not removed ")
                print("-"*64)
                return
        else:
            print(f"{Sname} is not installed")
            print("-"*64)
            return


    def removeXserver():
        cmdX = "dpkg-query -W -f='${binary:Package}\\t${Status}\\t${db:Status-Status}\\n' xserver-xorg*"
        Xinstalled = subprocess.run(cmdX, shell=True, text=True, capture_output=True)
        install_status = []
        for line in Xinstalled.stdout.splitlines():
            install_status.append(line.split("\t")[1].split()[2])
        if "installed" in install_status:
            print(" Removing xserver-xorg packages" )
            Xuninstall = subprocess.run(["apt", "purge", "xserver-xorg*", "-y"],stdout=subprocess.DEVNULL)
            if Xuninstall.returncode==0:
                print("Xserver-xorg packages are removed")
                print("-"*64)
            else:
                print("Xserver-xorg packages are removed")
                print("-"*64)

        else:
            print("xserver-xorg packages are not installed")
            print("-"*64)

    def removeAvahi():
        cmdavahi = "dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' avahi-daemon"
        avahiinstalled = subprocess.run(cmdavahi,shell=True, text=True, capture_output=True)
        install_status = []
        for line in avahiinstalled.stdout.splitlines():
            install_status.append(line.split("\t")[1].split()[2])
        if "installed" in install_status:
            print("avahi-daemon is installed, removing it...")
            
            subprocess.run(["systemctl","stop","avahi-daaemon.service", "-y"],stdout=subprocess.DEVNULL)
            subprocess.run(["systemctl","stop","avahi-daemon.socket","-y"],stdout=subprocess.DEVNULL)
            subprocess.run(["apt","purge","avahi-daemon","-y"],stdout=subprocess.DEVNULL)
        else:
            print("Avahi package is not installed")


    removeXserver()
    removeAvahi()
    uninstallservices("cups","CUPS")
    uninstallservices("isc-dhcp-server","DHCP")
    uninstallservices("sldap","LDAP")
    uninstallservices("nfs-kernel-server","NFS")
    uninstallservices("bind9","DNS")
    uninstallservices("vsftpd","FTP")
    uninstallservices("apache2", "HTTP server")
    uninstallservices("dovecot-imapd", "IMAP")
    uninstallservices("dovecot-pop3d", "POP3")
    uninstallservices("samba","Server Message Block(SMB) daemon")
    uninstallservices("squid","HTTP Proxy Server")
    uninstallservices("snmp", "Simple Network Management Protocol (SNMP)")
    uninstallservices("nis", "Network Information System (NIS)")
    uninstallservices("rsync","rsync")
    uninstallservices("rsh-client","RSH packages")
    uninstallservices("talk","Talk")
    uninstallservices("telnet","Telnet")
    uninstallservices("ldap-utils","LDAP clients")
    uninstallservices("rpcbind","Remote Procedure Call (RPC)")

def localonlyMTA():
    if os.path.isfile("/etc/postfix/main.conf"):
        with open("/etc/postfix.main.conf","r") as postfixFile:
                lines = postfixFile.readlines()
        for i in range(len(lines)):
            if "inet_interfaces = " in lines[i]:
                if "inet_interfaces = loopback-only" in lines[i]:
                    print("postfix MTA is not listining on any non-loopback addresses")
                    break
                else:
                    lines[i] = f"inet_interfaces = loopback-only\n"
                    break
        with open("/etc/postfix.main.conf", "w") as file:
            file.writelines(lines)
    else:
        print("Postfix MTA is not enabled")

def disableWirelessinterfaces():
    wirelessResult = subprocess.run(["nmcli", "radio", "all"],text=True,capture_output=True)
    wirePattern = r'\s+\S+\s+disabled\s+\S+\s+disabled\s+'
    match  = re.search(wirePattern,wirelessResult.stdout)
    if not match:
        print("Wireless interfaces are not disabled, disabling them...")
        wirelessresult = subprocess.run(["nmcli","radio","all","off"],capture_output=True,text=True)
        if wirelessresult.returncode==0:
            print("disabled!")
        else:
            print("Wireless interfaces could not be disabled, do it manually!")
    else:
        print("Wireless interfaces are disabled!")

def ipv6isEnabled():
    def check_grub_config():
        """Checks if Grub configuration disables IPv6."""
        grub_file = next(
            (f for f in os.listdir('/boot') if f in ['grubenv', 'grub.conf', 'grub.cfg']), None)
        if grub_file:
            with open(os.path.join('/boot', grub_file), 'r') as f:
                for line in f:
                    if re.search(r"^\s*(kernelopts=|linux|kernel)", line):
                        if re.search(r"ipv6\.disable=1", line):
                            return f"IPv6 Disabled in \"/boot/{grub_file}\""
        return True


    def check_sysctl_config():
        """Checks if sysctl configuration disables IPv6."""
        search_dirs = [
            "/run/sysctl.d", "/etc/sysctl.d",
            "/usr/local/lib/sysctl.d", "/usr/lib/sysctl.d",
            "/lib/sysctl.d", "/etc/",
        ]
        disabled_all = disabled_default = False
    
        for dir in search_dirs:
            try:
                for file in os.listdir(dir):
                    if file.endswith(".conf"):
                        with open(os.path.join(dir, file), 'r') as f:
                            for line in f:
                                if line.startswith("#"):
                                    continue
                                if re.match(r"^\s*net\.ipv6\.conf\.all\.disable_ipv6\s*=\s*1\s*$", line):
                                    disabled_all = True
                                if re.match(r"^\s*net\.ipv6\.conf\.default\.disable_ipv6\s*=\s*1\s*$", line):
                                    disabled_default = True
            except FileNotFoundError:
                continue
        if disabled_all and disabled_default:
            output_all = check_output(["sysctl", "net.ipv6.conf.all.disable_ipv6"]).decode()
            output_default = check_output(["sysctl", "net.ipv6.conf.default.disable_ipv6"]).decode()
            if re.search(r"^\s*net\.ipv6\.conf\.all\.disable_ipv6\s*=\s*1\s*$", output_all) \
                and re.search(r"^\s*net\.ipv6\.conf\.default\.disable_ipv6\s*=\s*1\s*$", output_default):
                return "ipv6 disabled in sysctl config"
        return True
    
    message_grub = check_grub_config()
    message_sysctl = check_sysctl_config()

    if message_grub != True:
        print(f"\nIPv6 Disabled: {message_grub}")
        return False
    elif message_sysctl != True:
        print(f"\n{message_sysctl}")
        return False
    else:
        print("\nIPv6 is enabled on the system")
        return True

def settingnetworkParameters():
    filePath = "/etc/default/ufw"
    searchLoc = ["/run/sysctl.d/","/etc/sysctl.d/", 
    "/usr/local/lib/sysctl.d/","/usr/lib/sysctl.d/","/lib/sysctl.d/" 
    "/etc/sysctl.conf"]

    if os.path.isfile(filePath):
        with open(filePath, "r") as ufwFile:
            lines = ufwFile.readlines()    
        with open(filePath, "w") as ufwFile:
            for line in lines:
                if line.strip().startswith("IPT_SYSCTL="):
                    searchLoc.append(line.split('=', 1)[1].strip())
                    ufwFile.write("#" + line)
                else:
                    ufwFile.write(line)

    def KernelparaFun(paraName, paraValue,newkernelFile):
        print("Checking for correct Network parameter set in Files")
        for loc in searchLoc:
            if os.path.isfile(loc):
                with open(loc,"r") as kernelFile:
                    kernelLines = kernelFile.readlines()
                for i in range(len(kernelLines)):
                    if kernelLines[i].strip().startswith(paraName):
                        value = kernelLines[i].split("=")[1].strip()
                        if value != paraValue:
                            print(f"\t-Commenting out {paraName} in {loc}")
                            kernelLines[i] = f"#{kernelLines[i]}\n"
                        else:
                            print(f'{paraName} set correctly in {loc}')
                    else:
                        if kernelLines[i].strip().startswith(f"#{paraName}") or kernelLines[i].strip().startswith(f"# {paraName}"):
                            print(f"\t-{paraName} already commented out in {loc}")
                with open(loc,"w") as kernelFile:
                    kernelFile.writelines(kernelLines)
            else:
                if os.path.isdir(loc):
                    for paraFile in os.listdir(loc):
                        if paraFile.endswith(".conf"):
                            paraPath = os.path.join(loc,paraFile)
                            with open(paraPath,"r") as kernelFile:
                                kernelLines = kernelFile.readlines()
                            for i in range(len(kernelLines)):
                                if kernelLines[i].strip().startswith(paraName):
                                    value = kernelLines[i].split("=")[1].strip()
                                    if value != paraValue:
                                        print(f"\t-Commenting out {paraName} in {paraPath}")
                                        kernelLines[i] = f"#{kernelLines[i]}\n"
                                    else:
                                        print(f'\t-{paraName} set correctly in {paraPath}')
                                else:
                                    if kernelLines[i].strip().startswith(f"#{paraName}") or kernelLines[i].strip().startswith(f"# {paraName}"):
                                        print(f"\t-{paraName} already commented out in {paraPath}")
                            with open(paraPath,"w") as kernelFile:
                                kernelFile.writelines(kernelLines)
        print("Done")
        print("Checking for correct network parameter in kernel parameter files")
        pattern = r"^\s*" + re.escape(paraName) + r"\s*=\s*" + re.escape(paraValue) + r"\b\s*(#.*)?$"
        found_match = False
        for loc in searchLoc:
            if os.path.isfile(loc):
                with open(loc, 'r') as f:
                    for line in f:
                        if re.search(pattern, line):
                            found_match = True
                            print(f"\t-{paraName} is set to {paraValue} in {loc}")
                            break
            else:
                if os.path.isdir(loc):
                    for file in os.listdir(loc):
                        if file.endswith(".conf"):
                            fpath = os.path.join(loc,file)
                            with open(fpath,"r") as fl:
                                for line in fl:
                                    if re.search(pattern,line):
                                        found_match = True
                                        print(f"\t-{paraName} is set to {paraValue} in {fpath}")
                                        break

        if not found_match:
            print(f"\t\n - Setting \"{paraName}\" to \"{paraValue}\" in \"{newkernelFile}\"")
            with open(newkernelFile, 'a') as f:
                f.write(f"{paraName} = {paraValue}\n")
        print("\t-Done!")
        print("Checking for active kernel parameters")

        sysctl_output = subprocess.run(["sysctl", paraName], capture_output=True, text=True).stdout
        paraOutput = sysctl_output.split("=")[1].strip()
        if paraOutput == paraValue:
            print(f"\t-{paraName} is set to {paraValue} is active kernel parameters")
        else:
            print(f"\t-Updating {paraName} to {paraValue} in active kernel parameters!")
            subprocess.run(["sysctl", "-w", f"{paraName}={paraValue}"])
            subprocess.run(["sysctl", "-w", f"{paraName.split('.')[0]}.{paraName.split('.')[1]}.route.flush=1"])
        print("\t-Done!")
        print("-"*64)



    paralist = ["net.ipv4.conf.all.send_redirects=0","net.ipv4.conf.default.send_redirects=0", "net.ipv4.ip_forward=0","net.ipv6.conf.all.forwarding=0",
                "net.ipv4.conf.all.accept_source_route=0","net.ipv4.conf.default.accept_source_route=0","net.ipv6.conf.all.accept_source_route=0",
                "net.ipv6.conf.default.accept_source_route=0","net.ipv4.conf.all.accept_redirects=0","net.ipv4.conf.default.accept_redirects=0",
                "net.ipv6.conf.all.accept_redirects=0","net.ipv6.conf.default.accept_redirects=0","net.ipv4.conf.default.secure_redirects=0",
                "net.ipv4.conf.all.secure_redirects=0","net.ipv4.conf.all.log_martians=1","net.ipv4.conf.default.log_martians=1",
                "net.ipv4.icmp_echo_ignore_broadcasts=1","net.ipv4.conf.all.rp_filter=1","net.ipv4.icmp_ignore_bogus_error_responses=1",
                "net.ipv4.conf.default.rp_filter=1","net.ipv4.tcp_syncookies=1","net.ipv6.conf.all.accept_ra=0","net.ipv6.conf.default.accept_ra=0",
                ]
    isnabled = ipv6isEnabled()
    
    for para in paralist:
        pname,pvalue = para.split("=",1)
        if pname.split(".")[1].strip() == "ipv6":
            if isnabled == True:
                kFile = "/etc/sysctl.d/60-netipv6_sysctl.conf"
                KernelparaFun(pname,pvalue,kFile)
            else: 
                print(f"ipv6 is not enabled do {pname} is name not applicable")
        else:
            kFile = "/etc/sysctl.d/60-netipv4_sysctl.conf"
            KernelparaFun(pname,pvalue,kFile)

def disableNetworkmodule():
    moduleList = ["dccp", "sctp", "rds", "ticp"]
    ifloaded = subprocess.run(["lsmod"], capture_output=True, text=True).stdout.split("\n")
    ifloaded = [mle for mle in ifloaded if mle.strip()]
    for modName in moduleList:
        modCheck = subprocess.run(['modprobe', '-n', '-v', modName], capture_output=True, text=True)

        if not any(re.search(r'^\s*install \/bin/(true|false)', line) for line in modCheck.stdout.split('\n')):
            print(f"- setting module: \"{modName}\" to be not loadable")
            with open(f"/etc/modprobe.d/{modName}.conf", "w") as conFile:
                conFile.write(f"install {modName} /bin/false\n")
        else:
            print(f"Module: {modName} is set to be not loadable")
        
        moduleFound = False
        for name in ifloaded:
            if modName == name.split()[0]:
                moduleFound = True
                print(f"Unloading module: {modName}")
                removed = subprocess.run(["modprobe", "-r", modName], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                if removed.returncode == 0:
                    print("Done!")
                else:
                    print(f"Unable to remove {modName}, try removing manually")
        if not moduleFound:
            print(f"Module: {modName} not loaded, not removed")
        
        dir = "/etc/modprobe.d/"
        isModuleBlacklisted = False
        for modFile in os.listdir(dir):
            with open(os.path.join(dir, modFile), "r") as f:
                for line in f:
                    if re.search(r'^\s*blacklist\s+' + re.escape(modName) + r'\b', line):
                        isModuleBlacklisted = True
                        print(f"{modName} is deny listed in {os.path.join(dir, modFile)}")
                        break
                        
                if isModuleBlacklisted:
                    break
        if not isModuleBlacklisted:
            print(f"Deny listing module: {modName}")
            with open(f"/etc/modprobe.d/{modName}.conf", "a") as confFile:
                confFile.write(f"blacklist {modName}\n")


def ufwConfiguration():
    print("Checking 'ufw' configuration")
    cmd = f"dpkg-query -W -f='${{binary:Package}}\t${{Status}}\t${{db:Status-Status}}\n' ufw"
    isinstalled = subprocess.run(cmd,shell=True,text=True,capture_output=True)
    install_status =[]
    for line in isinstalled.stdout.splitlines():
        install_status.append(line.split("\t")[1].split()[2].lower())
    if "installed" in install_status:
        print("\t-ufw is installed in the system!")
    else:
        print("\t-ufw is not installed, installing...")
        subprocess.run(["sudo","apt","install","ufw","-y"],stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
        print("Done!")
    ifiptblpersist = subprocess.run(["dpkg-query","-s","iptables-persistent"],capture_output=True,text=True)
    if ifiptblpersist.returncode==0:
        print("\t-iptables-persistent is installed in the system , removing it!")
        removed =subprocess.run(["apt","purge","iptables-persistent"],capture_output=True,text=True)
        if removed.returncode==0:
            print("\t-iptables-persistent have been removed!")
        else:
            print("\t-iptables-persistent not removed, need to be done manually!")
    else:
        print("\t-iptables-persistent not found, so not removed!")

    ufwenable = subprocess.run(["systemctl","is-enabled","ufw.service"],capture_output=True,text=True)
    ufwactive = subprocess.run(["systemctl","is-active","ufw"],capture_output=True,text=True)
    ufwstatus = subprocess.run(["ufw","status"],capture_output=True,text=True)
    ufwstatus = ufwstatus.stdout.split("\n")
    if ufwenable.stdout.strip()=="enabled" and ufwactive.stdout.strip()=="active" and ufwstatus[0].split(":")[1].strip()=="active":
        print("\t-ufw is enabled and active in the system!" )
    else:
        print("\t-ufw is not enabled, enabling it for the system...")
        subprocess.run(["systemctl","unmask","ufw.service"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(["systemctl","--now","enable","ufw.service"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(["ufw" ,"allow" ,"proto" ,"tcp" ,"from" ,"any" ,"to" ,"any","port" ,"22"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ufw","--force","enable"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        print("\tDone!")

            
    ufwstatus = subprocess.run(["ufw","status","verbose"],capture_output=True,text=True)
    loopPattern = [r'\s+Anywhere\s+on\s+lo\s+ALLOW\sIN\s+Anywhere\s+',r'\s+Anywhere\s+DENY\sIN\s+127.0.0.0/8\s+', r'\s+Anywhere\s+\(v6\)\s+on\s+lo\s+ALLOW\sIN\s+Anywhere\s+\(v6\)'
        ,r'\s+Anywhere\s+DENY\sIN\s+::1\s+',r'\s+Anywhere\s+ALLOW\sOUT\s+Anywhere\s+on\slo\s+',r'\s+Anywhere\s\(v6\)\s+ALLOW\sOUT\s+Anywhere\s\(v6\)\son\slo\s+']
    outPattern = [r'\s+Anywhere\s+ALLOW\sOUT\s+Anywhere\s+on\sall\s+',r'\s+Anywhere\s\(v6\)\s+ALLOW\sOUT\s+Anywhere\s\(v6\)\son\sall\s+']

    ufwloopflag = True
    ufwoutflag = True
    for pattern in loopPattern:
        match = re.search(pattern,ufwstatus.stdout)
        if not match:
            ufwloopflag = False
    if ufwloopflag:
        print("\t-ufw loopback traffic is configured")
    else:
        print("\t-configuring ufw loopback traffic...")
        subprocess.run(["ufw","allow","in","on","lo"],stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
        subprocess.run(["ufw","allow","out","on","lo"],stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
        subprocess.run(["ufw","deny","in","from","127.0.0.0/8"],stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
        subprocess.run(["ufw","deny","in","from","::1"],stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
        print("\tDone!")
    for pattern in outPattern:
        match = re.search(pattern,ufwstatus.stdout)
        if not match:
            ufwoutflag = False
    if ufwoutflag:
        print("\t-ufw outbound traffic is configured")
    else:
        print("\t-configuring ufw outbound traffic...")
        subprocess.run(["ufw","allow","out","on","all"],stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
        
        print("\tDone!")


    ufwOut = subprocess.run(["ufw","status","verbose"],capture_output=True,text=True)
    portOut = subprocess.run(["ss","-tuln"],capture_output=True,text=True)
    portOut = portOut.stdout.strip().split("\n")
    ports = set()
    for line in portOut:
        if not any(pat in line for pat in ["%lo:", "127.0.0.0:", "::1"]):
            if ":]" in line:
                ports.add(line.split("]:")[1].strip().split()[0])
            else:
                ports.add(line.split(":")[1].strip().split()[0])
    for port in ports.copy():
        if port == "Port":
            continue
        portpat = r'\s+'+re.escape(port)+r'/(tcp|udp)'
        match = re.search(portpat,ufwOut.stdout)
        if not match:
            print(f"\t-Port:{port} is missing a firewall rule")
        else:
            ports.remove(port)
    if "631" in ports:
        subprocess.run(["ufw","allow","631/tcp"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(["ufw","allow","out","631/tcp"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        print("\t-rule added for Port:631, for other ports the rules and configured as per requirements.")
    if "5353" in ports:
        subprocess.run(["ufw","allow","5353/udp"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(["ufw","allow","out","5353/udp"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        print("\t-rule added for Port:5353, for other ports the rules need to be configured as per requirements.")
    defPat = r'\s+Default:\s+deny\s+\(incoming\),\s+deny\s+\(outgoing\),\s+disabled\s+\(routed\)\s+'
    match = re.search(defPat,ufwOut.stdout)
    if match:
        print("\t-Default settings is set for ufw")
        print("\t-Adding rules to allow http\https connections")
        commands = [["ufw", "allow", "git"],["ufw", "allow", "in", "http"],["ufw", "allow", "out", "http"],["ufw", "allow", "in", "https"],
                    ["ufw", "allow", "out", "https"],["ufw", "allow", "out", "53"],["ufw", "logging", "on"]]
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Command {command} failed with return code {result.returncode}")
        print("\t-Done")
    else:
        print("\t-setting Default deny ufw for all connections")
        commands = [["ufw", "allow", "git"],["ufw", "allow", "in", "http"],["ufw", "allow", "out", "http"],["ufw", "allow", "in", "https"],
                    ["ufw", "allow", "out", "https"],["ufw", "allow", "out", "53"],["ufw", "logging", "on"],["ufw", "default", "deny", "incoming"],
                    ["ufw", "default", "deny", "routed"], ["ufw","default","deny","outgoing"]]
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Command {command} failed with return code {result.returncode}")
        print("\tDone!")


def auditConfiguration():
    print("Checking audit related configuration in the system...")
    auditCmd = "dpkg-query -W -f='${binary:Package}\\t${Status}\\t${db:Status-Status}\\n' auditd audispd-plugins"
    auditinstalled = subprocess.run(auditCmd, shell=True,capture_output=True,text=True)
    if auditinstalled.returncode==0:
        print("\t-auditd is installed on system")
        print("\t-audispd-plugins is installed on system")
    else:
        print("\t-auditd is not installed on system, installing...")
        subprocess.run(["apt", "install","auditd","-y"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        print("\t-audispd-plugins is not installed on system, installing...")
        subprocess.run(["apt", "install","audispd-plugins","-y"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    auditEnabled = subprocess.run(["systemctl", "is-enabled","auditd"],capture_output=True,text=True)
    auditActive = subprocess.run(["systemctl", "is-active","auditd"],capture_output=True,text=True)

    if auditEnabled.stdout.strip()=="enabled" and auditActive.stdout.strip()=="active":
        print("\t-auditd daemon is active and enabled in the system")
        
    else:
        print("\t-auditd daemon is not active or disabled in the system, enabling...")
        subprocess.run(["systemctl","--now","enable","auditd"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    cmdPrior = "find /boot -type f -name 'grub.cfg' -exec grep -Ph -- '^\h*linux' {} + | grep -v 'audit=1'"
    auditPrior = subprocess.run(cmdPrior, capture_output=True, text=True, shell=True)
    auditPath = "/etc/default/grub"
    auditFlag = False
    auditPattern = r'^GRUB_CMDLINE_LINUX=.*?\baudit=1\b.*$'
    auditOption = "audit=1"
    with open(auditPath, "r") as auditFile:
        auditLines = auditFile.readlines()
    for i in range(len(auditLines)):
        if auditLines[i].startswith("GRUB_CMDLINE_LINUX="):
            match = re.match(auditPattern,auditLines[i])
            if match:
                print(match.group())
                auditFlag=True
                break
    if auditPrior.returncode==0 and auditFlag:
        print("\t-Process started before starting auditd daemon are included in audit process")
    else:
        print("\t-configuring to audit process started before activating auditd daemon")
        pattern = r'GRUB_CMDLINE_LINUX="([^"]*)"'
        for i, line in enumerate(auditLines):
            match = re.match(pattern, line)
            if match:
                current_options = match.group(1)
                new_line = f'GRUB_CMDLINE_LINUX="{auditOption} {current_options}"\n'
                auditLines[i] = new_line
                break
        with open(auditPath, 'w') as auditFile:
            auditFile.writelines(auditLines)
        subprocess.run(["update-grub"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    cmdBacklog = "find /boot -type f -name 'grub.cfg' -exec grep -Ph -- '^\h*linux' {} + | grep -Pv 'audit_backlog_limit=\d+\b'"
    auditbacklog = subprocess.run(cmdBacklog,capture_output=True,text=True,shell=True)
    backlogPath = "/etc/default/grub"
    backlogFlag = False
    backlogPattern = r'^GRUB_CMDLINE_LINUX=.*?\baudit_backlog_limit=8192\b.*$'
    backlogOption = "audit_backlog_limit=8192"
    with open(backlogPath, "r") as backlogFile:
        backlogLines = backlogFile.readlines()
    for i in range(len(backlogLines)):
        if backlogLines[i].startswith("GRUB_CMDLINE_LINUX="):
            match = re.match(backlogPattern,backlogLines[i])
            if match:
                print(match.group())
                backlogFlag=True
                break
    if auditbacklog.returncode==0 and backlogFlag:
        print("\t-back log limit for audit events is set")
    else:
        print("\t-Configuring back log limit for audit events...")
        pattern = r'GRUB_CMDLINE_LINUX="([^"]*)"'
        for i, line in enumerate(backlogLines):
            match = re.match(pattern, line)
            if match:
                current_options = match.group(1)
                new_line = f'GRUB_CMDLINE_LINUX="{backlogOption} {current_options}"\n'
                backlogLines[i] = new_line
                break
        with open(backlogPath, 'w') as backlogFile:
            backlogFile.writelines(backlogLines)
        
        subprocess.run(["update-grub"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    logPath = "/etc/audit/auditd.conf"
    sizePattern = r"^\s*max_log_file\s*=\s*\d+\b"
    actionPattern = r'^\s*max_log_file_action\s*=\s*keep_logs\b'
    sizeFlag = False
    actionFlag =False
    with open(logPath,"r") as logFile:
        logLines = logFile.readlines()
    for i in range(len(logLines)):
        if logLines[i].startswith("max_log_file ="):
            sizeMatch = re.match(sizePattern,logLines[i])
            if sizeMatch:
                if 8 >= int(logLines[i].split("=")[1].strip()) :
                    print("\t-Storage size for audit log is set")
                continue
            else:
                print("\t-Setting storage size for audit log files...")
                logLines[i] ="max_log_file = 8\n"
                sizeFlag = True
                continue
        if logLines[i].startswith("max_log_file_action ="):
            actionMatch = re.match(actionPattern,logLines[i])
            if actionMatch:
                print("\t-System configured to not delte audit logs automatically")
                continue
            else:
                print("\t-Configuring audit logs to not be deleted automatically")
                logLines[i] = "max_log_file_action = keep_logs\n"
                actionFlag  = True
                continue
    if sizeFlag or actionFlag:
        with open(logPath,"w") as logFile:
            logFile.writelines(logLines)


    with open(logPath,"r") as auditconfFile:
        auditconfLines = auditconfFile.readlines()
    spaceAction = subprocess.run(["grep","-w","space_left_action","/etc/audit/auditd.conf"],capture_output=True,text=True)
    adminspaceAction = subprocess.run(["grep","-w","admin_space_left_action","/etc/audit/auditd.conf"],capture_output=True,text=True)
    spaceMail = subprocess.run(["grep","-w","action_mail_acct","/etc/audit/auditd.conf"],capture_output=True,text=True)
    spaceAction = spaceAction.stdout.split("=")
    spaceMail = spaceMail.stdout.split("=")
    adminspaceAction = adminspaceAction.stdout.split("=")
    if spaceAction[1].strip().lower() =='email' and (adminspaceAction[1].strip().lower()=="halt" or adminspaceAction[1].strip().lower()=="single") and spaceMail[1].strip().lower()=="root":
        print("\t-System configured to be disabled when audit logs are full")
    else:
        print("\t-Configuring system to be disbaled when audit logs are full...")
        if spaceAction[1].strip().lower() !='email':
            for i in range(len(auditconfLines)):
                if auditconfLines[i].startswith("space_left_action"):
                    auditconfLines[i] = "space_left_action = email\n"
        if adminspaceAction[1].strip().lower()!="halt" or adminspaceAction[1].strip().lower()!="single":
            for i in range(len(auditconfLines)):
                if auditconfLines[i].startswith("admin_space_left_action"):
                    auditconfLines[i] = "admin_space_left_action = halt\n"
        if spaceMail[1].strip().lower()!="root" :
            for i in range(len(auditconfLines)):
                if auditconfLines[i].startswith("action_mail_account"):
                    auditconfLines[i] = "action_mail_account = root\n"
        with open(logPath,"w") as auditconfFile:
            auditconfFile.writelines(auditconfLines)

def auditruleConfiguration():

    def findDiskrules(pattern,path):
        derivedRules = []
        for root,_,files in os.walk(path):
            for file in files:
                if file.endswith(".rules"):
                    filePath = os.path.join(root,file)
                    with open(filePath,"r") as f:
                        for line in f:
                            if pattern.search(line):
                                derivedRules.append(line)
        return derivedRules

    def findRunningRules(pattern):
        runRules = subprocess.run(["auditctl", "-l"], capture_output=True, text=True)
        rules_found = []
        for line in runRules.stdout.splitlines():
            if re.search(pattern,line):
                rules_found.append(line)
        return rules_found
        
    rulePath = "/etc/audit/rules.d/"
    #<----------------------------Sudoer rule----------------------------->
    print("Checking for logging of change in sudoer scope...")
    sudoerRulePath = "/etc/audit/rules.d/50-scope.rules"
    sudoerRule = ["-w /etc/sudoers -p wa -k scope","-w /etc/sudoers.d -p wa -k scope"]
    sudoerPattern = re.compile(r'^ *-w.*?/etc/sudoers.*? +-p *wa.*?( key= *[!-~]* *$|-k *[!-~]* *$)')
    sudoerDRfound = findDiskrules(sudoerPattern,rulePath)
    sudoerRRfound = findRunningRules(sudoerPattern)
    if len(sudoerRule)!=len(sudoerDRfound) or len(sudoerRule)!=len(sudoerRRfound):
        print("\t-Rule for monitoring Scope chages for sudoer is not added, adding")
        if os.path.isfile(sudoerRulePath):
            with open(sudoerRulePath,"a") as rFile :
                rFile.writelines(f"{rule}\n" for rule in sudoerRule)
        else:
            with open(sudoerRulePath,"w") as rFile :
                rFile.writelines(f"{rule}\n" for rule in sudoerRule)
        ruleupdate = subprocess.run(["augenrules","--load"],capture_output=True,text=True)
        if ruleupdate.returncode==0:
            print("\t-Rules added successfully")
        else:
            print("\t-Error in updating the rules , need to be checked manually")
    else:
        print("\t-System configured to monitor change in scope of Sudoer!")
    #<--------------------------------Other User activity Rule------------------------->
    print("Checking for logging of other user activities...")
    otherUsrRulePath = "/etc/audit/rules.d/50-user_emulation.rules"
    otherUsrRule = ["-a always,exit -F arch=b64 -C euid!=uid -F auid!=unset -S execve -k user_emulation","-a always,exit -F arch=b32 -C euid!=uid -F auid!=unset -S execve -k user_emulation"]
    otherUsrPattern =  re.compile(
        r'^\s*-a\s+always,exit'            
        r'(?:\s+-F\s+arch=b[2346]{2})'     
        r'(?:\s+-F\s+auid!=(?:unset|-1|4294967295))?'
        r'(?:\s+-C\s+euid!=uid|\s+-C\s+uid!=euid)?'  
        r'.*?'                                    
        r'(\s+-S\s+execve)'                      
        r'.*?'           
        r'(\s+(?:key=|-k)\s*[!-~]+)$',
        re.IGNORECASE
    )
    otherUsrDRfound = findDiskrules(otherUsrPattern,rulePath)
    otherUsrRRfound = findRunningRules(otherUsrPattern)
    if len(otherUsrRule)!=len(otherUsrDRfound) or len(otherUsrRule)!=len(otherUsrRRfound):
        print("\t-Rule logging other user activities are not added, adding...")
        if os.path.isfile(otherUsrRulePath):
            with open(otherUsrRulePath,"a") as rFile :
                rFile.writelines(f"{rule}\n" for rule in otherUsrRule)
        else:
            with open(otherUsrRulePath,"w") as rFile :
                rFile.writelines(f"{rule}\n" for rule in otherUsrRule)

        ruleupdate = subprocess.run(["augenrules","--load"],capture_output=True,text=True)
        if ruleupdate.returncode==0:
            print("\t-Rules added successfully")
        else:
            print("\t-Error in updating the rules , need to be checked manually")
    else:
        print("\t-System configured to monitor activities of other user!")
    #<------------Sudo log file modifiction------------------------------------------->
    print("Checking for logging activated for changes to date and time information...")
    timeDateRulePath = "/etc/audit/rules.d/50-time-change.rules"
    timeDateRule = ["-a always,exit -F arch=b64 -S adjtimex,settimeofday,clock_settime -k time-change",
                    "-a always,exit -F arch=b32 -S adjtimex,settimeofday,clock_settime -k time-change" ,
                    "-w /etc/localtime -p wa -k time-change"]
    timeDatePattern1 = re.compile(r'^ *-a *always,exit.*-F *arch=b[2346]{2}.*-S.*?(adjtimex|settimeofday|clock_settime).*?(key= *[!-~]* *$|-k *[!-~]* *$)')
    timeDatePattern2 = re.compile(r'^ *-w.*?/etc/localtime.*-p *wa.*?(key= *[!-~]* *$|-k *[!-~]* *$)')

    timeDateDRfound1 = findDiskrules(timeDatePattern1,rulePath)
    timeDateRRfound1 = findRunningRules(timeDatePattern1)
    timeDateDRfound2 = findDiskrules(timeDatePattern2,rulePath)
    timeDateRRfound2 = findRunningRules(timeDatePattern2)
    timeDateDRfound = timeDateDRfound1+timeDateDRfound2
    timeDateRRfound = timeDateRRfound1 + timeDateRRfound2
    if len(timeDateRule)!=len(timeDateDRfound) or len(timeDateRule)!=len(timeDateRRfound):
        print("\t-Rule for monitoring changes in Date and Time information, adding...")
        if os.path.isfile(timeDateRulePath):
            with open(timeDateRulePath,"a") as rFile :
                rFile.writelines(f"{rule}\n" for rule in timeDateRule)
        else:
            with open(timeDateRulePath,"w") as rFile :
                rFile.writelines(f"{rule}\n" for rule in timeDateRule)

        ruleupdate = subprocess.run(["augenrules","--load"],capture_output=True,text=True)
        if ruleupdate.returncode==0:
            print("\t-Rules added successfully")
        else:
            print("\t-Error in updating the rules , need to be checked manually")
    else:
        print("\t-System configured to monitor change Date and Time information!")


print("-"*64)
disable_filesystem_loading()
print("-"*64)
disable_autofs()
print("-"*64)
installingAIDE()
print("-"*64)
schedulingAideChecks()
print("-"*64)
bootloaderPassword()
print("-"*64)
bootconfigPermission()
print("-"*64)
setTerminalvalue()
print("-"*64)
prelinkRmBinaryrestore()
print("-"*64)
disableAutomaticErrorReporting()
print("-"*64)
coreDumpRestriction()
print("-"*64)
configureApparmor()
print("-"*64)
cmdLineBanners()
print("-"*64)
loginBannerMsg()
print("-"*64)
disableLoginUserList()
print("-"*64)
screenLockIdle()
print("-"*64)
screenLockFile()
print("-"*64)
disableAutoMounting()
print("-"*64)
mountLockFile()
print("-"*64)
systemdTimesyncdEnabled()
print("-"*64)
AuthTSforsystemdtimesyncd()
print("-"*64)
removePackages()
print("-"*64)
localonlyMTA()
print("-"*64)
disableWirelessinterfaces()
print("-"*64)
settingnetworkParameters()
print("-"*64)
disableNetworkmodule()
print("-"*64)
ufwConfiguration()
print("-"*64)
auditConfiguration()
print("-"*64)
auditruleConfiguration()
