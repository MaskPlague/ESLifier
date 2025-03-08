# ESLifier
ESLifier allows users to scan their Skyrim Special Edition directory for plugins that can either be flagged as ESL or compacted to fit ESL conditions. The user can then flag or compact the relevant plugins.
If the user compacts a plugin then ESLifier will also patch and rename all files that have that mod as a master (plugins and files that directly reference a form id present in the compacted plugin). The user can also
scan for files and plugins that are added after compacting so that they can also be patched to fit the new form ids of the compacted master.
  
# For Users
## External Requirements
ESLifier relies on [BSA Browser](https://www.nexusmods.com/skyrimspecialedition/mods/1756) to extract scripts, facegen, and voice files from BSA files.

## User Manual
Notes:
- If you use MO2 do **NOT** add ESLifier.exe as an executable. Launching ESLifier through MO2 significantly slows down the file scanning process. Instead enable MO2 mode in the settings of ESLifier.
- Almost every element in the program has a tooltip that is activated by hovering over it.
- ESLifier may cause issues in existing save games as is the nature of compacting form ids. I am currently looking into how difficult it would be to patch an existing save file.

On the first launch or when the paths are not set, you will be redirected to the settings page. Set all available paths to the required folders and files. You will not be able to exit the settings page until they are set. The settings available are by default in the recommended configuration that should ensure the fewest issues when compacting or ESL flagging. You may want to disable _Show plugins with new CELL records_ if you think you may often install mods that will patch your existing mods with CELLs (the Patch New Page will warn you if you do install mods that do so later).

The first page, _Main_, is where one can select plugins to patch or compact. Select the _Scan Mod Files_ button and wait for the scan to complete. Then the left and right lists will populate. The plugins in the left list are ready to be ESL flagged with almost no worries. The plugins in the right list are one of the main features of ESLifier, these are able to be compacted via the program and all files and plugins that rely on the compacted plugins will have any form IDs in them patched to reflect the form ID changes. You can check off each plugin you want to flag/compact. You can right click for various functions including adding a mod to the blacklist. Pushing Space Bar with multiple mods highlighted will toggle their checkboxes.

The second page, _Patch New Plugins/Files_, is another main feature of ESLifier. It allows you to scan for any new files and plugins that rely on a compacted plugin and are not already patched. This means you can install mods that rely on a compacted mod and not worry about the new mods not working properly. For example you can install a Spell Perk Item Distributor ini file for a previous form ID compacted armor mod, open ESLifier, patch the new ini file, and it will function normally in game. Select the _Find Unpatched Files_ button and wait for the scan to complete. If there are any new files that depend on a previously compacted mod then the mod will appear in the left list and you can select the mod to show a list of unpatched files in the right list.

The third page, _Settings_, mostly controls what is displayed in the _Main_ page.
- _Allow Form IDs below 0x000800 + Update plugin headers to 1.71_ affects the scanning, flagging, and compacting functions of ESLifier. It is on by default and requires [Backported Extended ESL Support](https://www.nexusmods.com/skyrimspecialedition/mods/106441) if your Skyrim version is below 1.6.1130+. For scanning, it will only find and display plugins in the ESLifyable and Compactable lists that fit in the 1.71 range unless disabled, then it will only show ones that fit in the older 1.70 range. For flagging, it will update the plugin header to 1.71 if enabled. For compacting, it will update the plugin header to 1.71 and compact the form ids to fit in the 1.71 range if enabled.
- _Scan ESM Plugins_ will determine whether or not .esm and ESM flagged plugins are scanned at all. Changing this setting requires a new scan to display the changes. I added this setting as I could not determine from online research if ESL flagging ESMs had any benefits/detriments.
- _Show Plugins with new CELL records_ affects the scanning and display of both lists. It is on by default. If enabled, it will scan for and display mods that have new CELL records. If a new CELL record is defined in an ESL flagged plugin and then edited by another plugin then it can break the new CELL. This setting is used in combination with the setting _Hide plugins with new CELL records that are overwriten_.
- _Show plugins with BSA files_ will show plugins that have .bsa files that may contain files that need patching. It is off by default. If enabled, it will display the BSA flag in _Main_'s Compact list. Hovering over the flag of each plugin will display what kinds of files ESLifier detected may be present in the .bsa that need extracting so that the program can scan and patch them. This program does not extract .bsas automatically and will require the user to do it manually. Compacting a plugin with the BSA flag will likely lead to various issues if you have not extracted the relevant files.
- _Hide plugins with new CELL records that are overwriten_ hides plugins that have new CELLs that are also edited/overwitten by a dependent plugin that has it as a master. It is on by default. This should probably be left on as if the setting is disabled then you will see plugins that may have their new CELLs broken by ESL flagging them.
- _Show plugins that are in SKSE dlls_ will display plugins that have their name present in SKSE dlls. This is off by default and should probably be left off. If a plugin has its name in a dll then it is likely that its form IDs are hard-coded in a FormLookup() call which will fail if the form IDs are changed via compacting.

# Documentation
## How to Build
Fork this project and install python 3.13 then, _PyQt6_, _Regex_, and _pyinstaller_ with pip.
Open the console in the _ESLifier_ folder and run the command:
```
pyinstaller "src/eslifier_app.py" --onefile -n "ESLifier" --noconsole --icon "src/images/ESLifier.ico"
```
## Files that are patched by ESLifier
- .ini:
  - Keyword Item Distributor
  - Base Object Swapper
  - Spell Perk Item Distributor
  - Seasons of Skyrim
  - Payload Interpreter
  - ENB Lights For Effect Shaders
  - Description Framwork
  - SkyPatcher
  - DtryKeyUtil
  - Poise Breaker
  - Valhalla Combat
  - AutoBody
  - Various States of Undress
- config.json:
  - Open Animation Replacer (and user.json)
  - MCM Helper
- _conditions.txt: Dynamic Animation Replacer
- _srd.: Sound Record Distributor
- .toml:
  - Dynamic Animation Casting
  - Precision
  - Loki Poise
  - True Directional Movment
- .psc: Source Scripts
- .json:
  - Dynamic Key Activation Framework NG
  - Smart Harvest Auto NG AutoLoot
  - PapyrusUtil's StorageDataUtil
  - Custom Skills Framework
  - Dynamic String Distributor
  - Dynamic Armor Variants
  - Inventory Injector
  - Immersive Equipment Display
  - Light Placer
  - Player Equipment Manager
  - Skyrim Unbound
  - Creature Framework
  - CoMAP
  - OBody NG
- .jslot: Racemenu Presets
- facegeom's .nif: Texture paths in face mesh files
- voice, facetint, facegeom: The names of these files are patched
- .seq: SEQ files
- .pex: Compiled script files
  
    
