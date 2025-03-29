# ESLifier
ESLifier allows users to scan their Skyrim Special Edition directory for plugins that can either be flagged as ESL or compacted to fit ESL conditions. The user can then flag or compact the relevant plugins.
If the user compacts a plugin, then ESLifier will also patch and rename all files that have that mod as a master (plugins and files that directly reference a Form ID present in the compacted plugin). The user can also
scan for files and plugins that are added after compacting so that they can also be patched to fit the new Form IDs of the compacted master.

Nexus Mods [ESLifier](https://www.nexusmods.com/skyrimspecialedition/mods/145168)

Nexus Mods [ESLifier MO2 Integration Plugin](https://www.nexusmods.com/skyrimspecialedition/mods/126298)
  
# For Users
## External Requirements
ESLifier relies on [BSA Browser](https://www.nexusmods.com/skyrimspecialedition/mods/1756) to extract scripts, facegen, and voice files from BSA files.

## User Manual
Notes:
- If you use MO2 do **NOT** add ESLifier.exe as an executable. Launching ESLifier through MO2 significantly slows down the file scanning process. Instead enable MO2 mode in the settings of ESLifier. Also, ESLifier can scan the Overwrite folder however, you will probably want to move everything in it to a mod instead, so that ESLifier's output can win any file conflicts and you won't keep the only copy of any configs generated in overwrite patched to ESLifier Output as your only copy.
- There is now a MO2 plugin that will notify users of when a plugin is ESLify-able and can allow users to edit the plugin blacklist.
- Almost every element in the program has a tooltip that is activated by hovering over it.
- ESLifier may cause issues in existing save games as is the nature of compacting Form IDs. I am currently looking into how difficult it would be to patch an existing save file.

On the first launch or when the paths are not set, you will be redirected to the settings page. Set all available paths to the required folders and files. You will not be able to exit the settings page until they are set. The settings available are by default in the recommended configuration that should ensure the fewest issues when compacting or ESL flagging. You may want to disable _Show plugins with new CELL records_ if you think you may often install mods that will patch your existing mods with CELLs (the Patch New Page will warn you if you do install mods that do so later).

After setting the paths you can now move to the Main Page where you can hit the scan button. The first scan, or any scan after selecting Reset BSA in the settings, will extract compiled scripts and SEQ files from BSAs to a new folder called _bsa_extracted_. Leave this folder alone as ESLifier uses it as a source of files to compact if necessary. After the scanning process completes you will see the left and right lists populate. In the left list are all mods that can be ESL flagged without compacting. There are various flags that may show next to the plugin names which have tool tips describing what they mean. The right list are all mods that can be compacted to fit ESL conditions. These mods are heavily filtered by the settings page and are mostly safe to compact. They also have various flags. Check off each plugin that you wish to ESL flag or compact and ESL flag and then select the buttons below.

After that simply install the ESLifier Output as a mod to your mod manager. MO2 users can either drag and drop the folder into the MO2 UI or generate it directly in the mods folder. Vortex users can zip the folder and then install it or generate the output to the mods staging folder. Simply let the ESLifier Output win any file conflicts. Do not move the contents of ESLifer Ouput to the source mods as you risk doing permanent damage to your mod list that way.

The patch new page uses the Compacted and Patched history to check for new files that need patching as said files refer to Form IDs in ESLifier compacted plugins. The left list is what mods you have compacted that either have a warning flag (explained in the flag's tooltips) or new files that need patching which can be done by checking them off and selecting the button below the list. The right list is simply a display of the new files that will be patched for each mod.


The settings page has several important buttons: Reset BSA, Edit Blacklist, and the Delete All button.

- The Delete All button is _very_ important. It will delete your compacted and patched history and the Form ID maps that ESLifier uses to patch new files. This button should be used whenever you change anything about your modlist and or delete the ESLifier Output. This will also allow you to right click and choose Check Previously Compacted which will check off all mods that were in the compacted history, allowing you to easily re-do your compacting. If you see green indicators instead of check boxes then you have either not installed the ESLifier output as a mod or you have deleted/cleared the ESLifer output but haven't clicked the Delete All button yet.

- The Reset BSA button will delete the aforementioned _bsa_extracted_ folder. This should be done whenever you delete a mod that has a BSA file or when you add a mod with a BSA that holds files that should be overwritten by an existing BSA (or just when you add a BSA in general if you don't want to get too detailed about it).

- The Edit Blacklist button allows you to edit the blacklist. Plugins in this list will not appear in the Main page lists. You can add mods to the blacklist via the right click context menu on the main page.


### More in Depth Page Descriptions:

The first page, _Main_, is where one can select plugins to patch or compact. Select the _Scan Mod Files_ button and wait for the scan to complete. Then the left and right lists will populate. The plugins in the left list are ready to be ESL flagged with almost no worries. The plugins in the right list are one of the main features of ESLifier, these are able to be compacted via the program and all files and plugins that rely on the compacted plugins will have any form IDs in them patched to reflect the form ID changes. You can check off each plugin you want to flag/compact. You can right click for various functions including adding a mod to the blacklist. Pushing Space Bar with multiple mods highlighted will toggle their checkboxes.

The second page, _Patch New Plugins/Files_, is another main feature of ESLifier. It allows you to scan for any new files and plugins that rely on a compacted plugin and are not already patched. This means you can install mods that rely on a compacted mod and not worry about the new mods not working properly as this page will allow you to patch them in a couple of clicks. For example you can install a Spell Perk Item Distributor ini file for a previous form ID compacted armor mod, open ESLifier, patch the new ini file, and it will function normally in game. Select the _Find Unpatched Files_ button and wait for the scan to complete. If there are any new files that depend on a previously compacted mod then the mod will appear in the left list and you can select the mod to show a list of unpatched files in the right list. Additionally two warnings can be displayed in the left list. A nNew Cell Changed warning, which means an installed mod is currently overwritting the new cell of the compacted mod possibly breaking the new cell, or a SKSE DLL warning, which means that there is a dll with the plugin name present that may have a broken FormLookup() call as they require hard-coded Form IDs.

The third page, _Settings_, mostly controls what is displayed in the _Main_ page.
- _Allow Form IDs below 0x000800 + Update plugin headers to 1.71_ affects the scanning, flagging, and compacting functions of ESLifier. It is on by default and requires [Backported Extended ESL Support](https://www.nexusmods.com/skyrimspecialedition/mods/106441) if your Skyrim version is below 1.6.1130+. For scanning, it will only find and display plugins in the ESLifyable and Compactable lists that fit in the 1.71 range unless disabled, then it will only show ones that fit in the older 1.70 range. For flagging, it will update the plugin header to 1.71 if enabled. For compacting, it will update the plugin header to 1.71 and compact the Form IDs to fit in the 1.71 range if enabled.
- _Scan ESM Plugins_ will determine whether or not .esm and ESM flagged plugins are scanned at all. Changing this setting requires a new scan to display the changes. I added this setting as I could not determine from online research if ESL flagging ESMs had any benefits/detriments.
- _Show Plugins with new CELL records_ affects the scanning and display of both lists. It is on by default. If enabled, it will scan for and display mods that have new CELL records. If a new CELL record is defined in an ESL flagged plugin and then edited by another plugin then it can break the new CELL. This setting is used in combination with the setting _Hide plugins with new CELL records that are overwriten_.
- _Show plugins with BSA files_ will show plugins that have .bsa files that may contain files that need patching. It is off by default. If enabled, it will display the BSA flag in _Main_'s Compact list. Hovering over the flag of each plugin will display what kinds of files ESLifier detected may be present in the .bsa that need extracting so that the program can scan and patch them. This program does not extract .bsas automatically and will require the user to do it manually. Compacting a plugin with the BSA flag will likely lead to various issues if you have not extracted the relevant files.
- _Hide plugins with new CELL records that are overwriten_ hides plugins that have new CELLs that are also edited/overwitten by a dependent plugin that has it as a master. It is on by default. This should probably be left on as if the setting is disabled then you will see plugins that may have their new CELLs broken by ESL flagging them.
- _Hide plugins with new interior CELL records_ hides plugins that have new interior CELLs as they can have issues with not reloading properly on save load if the player doesn't restart the game. This is off by default. The user should decide if they think these kinds of plugins are safe to ESL.
- _Hide plugins with new WRLD (worldspace) records_ hides plugins that have a new WRLD record as they lose landscape data when ESL flagged (the ground will disappear in the new worldspace).
- _Show plugins that are in SKSE dlls_ will display plugins that have their name present in SKSE dlls. This is off by default and should probably be left off. If a plugin has its name in a dll then it is likely that its form IDs are hard-coded in a FormLookup() call which will fail if the form IDs are changed via compacting.

Other important settings:
- _Reset Extracted BSA List and Delete Extracted Files_ This setting should be used when you remove a mod that has a BSA file or update a mod that has a BSA file.
- _Delete All Form ID Maps and Compacted/Patched History_ This setting deletes the Form ID Maps that ESLifier uses to patch new dependent plugins and files. It also deletes the Compacted/Patched History which ESLifier uses to track what mods it has compacted/patched. Use this when you update compacted mods. You'll also want to manually delete the ESLifier Output folder's contents. A list of previously compacted mods will be generated upon deleting your compacted/patched history and the right click context menu for the compactable list on the main page can use this to tick all previously compacted mods.

# Documentation
## How to Build
Fork this project and install python 3.13 then install these libraries via pip: _PyQt6_, _Regex_, _mmap_, _intervalTree_, and _pyinstaller_.
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
  - Description Framework
  - SkyPatcher
  - DtryKeyUtil
  - Poise Breaker
  - Valhalla Combat
  - AutoBody
  - Various States of Undress
  - Form List Manipulator
  - Leveled List Object Swapper
  - Item Property Manipulator
  - Music Type Distributor
  - Completionist
- .json:
  - Open Animation Replacer
  - MCM Helper
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
  - SL Configs
  - OStim Standalone
  - Race Compatibility SKSE
- .toml:
  - Dynamic Animation Casting
  - Precision
  - Loki Poise
  - True Directional Movment
- .psc: Source Scripts
- .pex: Compiled script files
- _conditions.txt: Dynamic Animation Replacer
- _srd.: Sound Record Distributor
- .jslot: Racemenu Presets
- facegeom's .nif: Texture paths in face mesh files
- voice, facetint, facegeom: The names of these files are patched
- .seq: SEQ files

  
    
