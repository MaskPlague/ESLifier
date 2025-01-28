# ESLifier
Purpose:
  ESLifier allows users to scan their Skyrim Special Edition directory for plugins that can either be flagged as ESL or compacted to fit ESL conditions. The user can then flag or compact the relevant plugins.
  If the user compacts a plugin then ESLifier will also patch and rename all files that have that mod as a master (plugins and files that directly reference a form id present in the compacted plugin). The user can also
  scan for files and plugins that are added after compacting so that they can also be patched to fit the new form ids of the compacted master.
  
# For Users
## User Manual
Notes:
- If you use MO2 then, add ESLifier.exe as an executable and launch it through MO2. If you want to keep ESLifier's data separate per instance then it will need to be either installed as a mod or have the exe in separate folders per instance.
- If you have put many of your mod files into BSAs then this program may be much less effective.
- Almost every element in the program has a tooltip that is activated by hovering over it.
- When the README says "select" it refers to directly clicking the text of the item, not clicking the check box.

On first launch, or when both paths are not set, you will be directed to the settings page. Here, set the _Skyrim Folder Path_ to the location of the folder that holds _SkyrimSE.exe_ and set _Output Folder Path_ to the folder
that the _ESLifier Output_ will be generated in, for example MO2's mods folder and Vortex's mod staging folder. The settings available are by default in the recommended configuration that should ensure the fewest issues when compacting
or ESL flagging. You may want to disable _Show plugins with new CELL records_ if you think you may often install mods that patch your existing mods with CELLs (the Patch New Page will warn you if you do install mods that do so).

The first page, _Main_, is where one can select plugins to patch or compact. Select the _Scan Mod Files_ button and wait for the scan to complete (2500+ plugins, 500+ GBs, 800k files takes a bit less then a minute for me). Then the left and right lists will populate. The plugins in the left list are ready to be ESL flagged with almost no worries. The plugins in the right list are one of the main features of ESLifier, these are able to be compacted via the program and all files adn plugins that rely on the compacted plugins will have any form ids in them patched to reflect the form id changes. You can check off each plugin you want to flag/compact. You can right click for various functions including adding a mod to the blacklist. Pushing Space Bar with multiple mods selected will toggle the check on them.

The second page, _Patch New Plugins/Files_, is another main feature of ESLifier. It allows you to scan for any new files and plugins that rely on a compacted plugin and are not already patched. This means you can install mods that rely on a compacted mod and not worry about the new mods not working properly. For example you can install a Spell Perk Item Distributor ini file for a previous form id compacted armor mod, open ESLifier, patch the new ini file, and it will function normally in game. Select the _Find Unpatched Files_ button and wait for the scan to complete. If there are any new files that depend on a previously compacted mod then the mod will appear in the left list and you can select the mod to show a list of unpatched files in the right list.

The third page, _Settings_, mostly controls what is displayed in the _Main_ page.
- _Allow Form IDs below 0x000800 + Update plugin headers to 1.71_ affects the scanning, flagging, and compacting functions of ESLifier . It is on by default and requires [Backported Extended ESL Support](https://www.nexusmods.com/skyrimspecialedition/mods/106441) if your Skyrim version is below 1.6.1130+. For scanning, it will only find and display plugins in the ESLifyable and Compactable lists that fit in the 1.71 range unless disabled, then it will only show ones that fit in the older 1.70 range. For flagging, it will update the plugin header to 1.71 if enabled. For compacting, it will update the plugin header to 1.71 and compact the form ids to fit in the 1.71 range if enabled.
- _Show Plugins with new CELL records_ affects the scanning and display of both lists. It is on by default. If enabled, it will scan for and display mods that have new CELL records. If a new CELL record is defined in an ESL flagged plugin and then edited by another plugin then it can break the new CELL. This setting is used in combination with the setting _Hide plugins with new CELL records that are overwriten_.
- _Show plugins with BSA files_ will show plugins that have .bsa files that may contain files that need patching. It is off by default. If enabled, it will display the BSA flag in _Main_'s Compact list. Hovering over the flag of each plugin will display what kinds of files ESLifier detected may be present in the .bsa that need extracting so that the program can scan and patch them. This program does not extract .bsas automatically and will require the user to do it manually. Compacting a plugin with the BSA flag will likely lead to various issues if you have not extracted the relevant files.
- _Hide plugins with new CELL records that are overwriten_ hides plugins that have new CELLs that are also edited/overwitten by a dependent plugin that has it as a master. It is on by default. This should probably be left on as if the setting is disabled then you will see plugins that may have their new CELLs broken by ESL flagging them.

# Documentation
## Files that are patched by ESLifier
- .esm/.esp/.esl: plugins that have the compacted plugin as master -Patched
- .ini: PO3's distributors, SkyPatcher, others -Patched
- config.json: OAR and MCM Helper -Patched
- \_conditions.txt: Dynamic Animation Replacer -Patched
- \_srd.: Sound Record Distributor -Patched
- .psc: Source Scripts -Patched (doesn't patch form ids that are passed as variables)
- .json (not config.json): -Patched, Dynamic Key Activation Framework NG and Smart Harvest Auto NG AutoLoot Should work for MNC and Dynamic String Distributor ::SHSE needs more work for multiline form id lists.
- facegeom\: -Renamed -Texture paths in face mesh files patched
- facetint\: -Renamed
- .seq: SEQ files -Patched
- .pex: integer form ids in compiled scripts -{atched
## Files
### ESLifier_Data/ Files
This folder and its contents are generated during program usage, the folder is generated in the same folder as the executable.
- bsa_dict.json: A dictionary whose keys are BSA names and the values are lists that hold all plugins that may rely on files present in the json. If index 0 is 'scripts\_\<BSA name without ext\>' then the BSA contains scripts which need to be extracted for scanning/patching.
- cell_changed.json: A list of plugins which are compactible but also have have at least one new CELL changed by a plugin that contains them as a master.
- dependency_dictionary.json: A dictionary whose keys are plugins and the values are lists of plugins who have the key as a master.
- ESLifier.log: A record of the in program log window.
- file_masters.json: A dictionary whose keys are plugins and the values are lists of files that will likely need to be patched/renamed if the key is compacted.
- plugin_list.json: A list of all plugin files present in the top level of the directory of Skyrim Special Edition.
- settings.json: Where ESLifier stores the user's settings.
### Source Files
TODO: description of python files
- blacklist.py
- cell_changed_scanner.py
- compact_form_ids.py
- dependency_getter.py
- eslifier_app.py
- list_compact.py
- list_compacted_unpatched.py
- list_eslify.py
- list_unpactehd_files.py
- log_stream.py
- main_page.py
- patch_new_page.py
- plugin_qualificaiton_checker.py
- QToggle.py
- scanner.py
- settigns_page.py
## Program Flow Explanation
TODO: Explanation of how the program works will go here eventually.
  
    
