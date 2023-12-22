#!/usr/bin/env python

import subprocess
def disable_filesystem_loading(l_mname):
    # Setting Module to be Not Loadable
    install_line = f"install {l_mname} /bin/false\n"
    modprobe_conf_path = f"/etc/modprobe.d/{l_mname}.conf"

    try:
        with open(modprobe_conf_path, 'r') as f:
            if not any(install_line in line for line in f):
                with open(modprobe_conf_path, 'a') as f:
                    print(f" - setting module: \"{l_mname}\" to be not loadable")
                    f.write(install_line)
    except FileNotFoundError:
        with open(modprobe_conf_path, 'w') as f:
            print(f" - setting module: \"{l_mname}\" to be not loadable")
            f.write(install_line)

    # Unloading the Module
    if subprocess.Popen(["lsmod", "|", "grep", l_mname], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).returncode == 0:
        print(f" - unloading module \"{l_mname}\"")
        subprocess.run(["modprobe", "-r", l_mname])

    # Deny Listing the Module
    blacklist_line = f"blacklist-{l_mname}\n"

    try:
        with open("/etc/modprobe.d/*", 'r') as f:
            if not any(blacklist_line in line for line in f):
                with open(modprobe_conf_path, 'a') as f:
                    print(f" - deny listing \"{l_mname}\"")
                    f.write(blacklist_line)
    except FileNotFoundError:
        with open(modprobe_conf_path, 'w') as f:
            print(f" - deny listing \"{l_mname}\"")
            f.write(blacklist_line)

# the above function can be called for "cramfs", "squashfs" and "udf" for Ubuntu.