# NANDPART

Windows application to resize the Nintendo Switch USER partition when a larger system NAND is installed.

# Installation

pip3 install pyqt5 wmi

# NAND Upgrade Guide

1. Ensure you have your biskeys, if you do not, lookup a tutorial on how to get them.

2. Use Hekate to take a backup of boot0 and boot1.

3. Download memloader from https://switchtools.sshnuke.net/, copy everything inside of the "sample" directory to your SD root.

4. Reboot your switch and launch the memloader RCM payload (leave USB cable connected).

5. Use NxNandManager (https://github.com/eliboa/NxNandManager) to take a full nand backup to your PC.

6. Turn off your switch, disassemble it, and install the new upgraded NAND.

7. Boot into Hekate, and restore boot0 and boot1.  The first time you try it, it should fail, take note of the directory it is trying to restore the backups from, and move your boot0 and boot1 backups into that directory, then restore again.

8. Power off the switch, launch the memloader payload (leave USB cable connected).

9. Use win32diskimager to flash your 32GB NAND backup to your switch.

10. Use hacdiskmount to mount your user partition using your BIS keys (either use the backup image you took earlier which is faster, or mount the actual switch).

11. Copy all of the files from the user partition to a safe place on your PC, then unmount and close hacdiskmount.

12. Launch NANDPart, select your switch from the dropdown, verify the partitions look correct, then click "resize".

13. Launch hacdiskmount and mount your USER partition using your BIS keys and actual switch.

14. Bring up a windows command prompt with admin rights, and run "fat32format.exe X:"  where X: is the drive of your mounted user partition.

15. Copy all of your backed up user partition files back to the switch's newly created user partition.

16. Reboot into CFW and ensure everything is working correctly.


