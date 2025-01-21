import re
import timeit

from dependency_getter import dependecy_getter as dep_getter


class qualification_checker():
    def scan(path, update_header, show_cells):
        start_time = timeit.default_timer()
        all_plugins = dep_getter.get_list_of_plugins(path)
        plugins = [plugin for plugin in all_plugins if not plugin.lower().endswith('.esl')]
        need_flag_list = []
        need_flag_cell_flag_list = []
        need_compacting_list = []
        need_compacting_cell_flag_list = []
        qualification_checker.max_record_number = 4096
        qualification_checker.show_cells = show_cells
        if update_header:
            qualification_checker.num_max_records = 4096
        else:
            qualification_checker.num_max_records = 2048

        print('\n')
        count = 0
        plugin_count = len(plugins)
        for plugin in plugins:
            count += 1
            percentage = (count / plugin_count) * 100
            print('\033[F\033[K-  Processed: ' + str(round(percentage, 1)) + '%' + '\n-  Plugins: ' + str(count) + '/' + str(plugin_count), end='\r')
            if not qualification_checker.already_esl(plugin):
                esl_allowed, need_compacting, new_cell = qualification_checker.file_reader(plugin)
                if esl_allowed:
                    if not need_compacting:
                        need_flag_list.append(plugin)
                        need_flag_cell_flag_list.append(new_cell)
                    else:
                        need_compacting_list.append(plugin)
                        need_compacting_cell_flag_list.append(new_cell)

        end_time = timeit.default_timer()
        time_taken = end_time - start_time
        print('-  Time taken: ' + str(round(time_taken,2)) + ' seconds')
        return need_flag_list, need_flag_cell_flag_list, need_compacting_list, need_compacting_cell_flag_list

    def file_reader(file):
        data_list = []
        new_cell = False
        need_compacting = False
        with open(file, 'rb') as f:
                data = f.read()
                data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................[\x2c|\x2b]\x00.\x00)|(?=GRUP....................)', data, flags=re.DOTALL) if x]
        masterCount = data_list[0].count(b'MAST')
        count = 0
        for form in data_list:
            if form[:4] != 'TES4' and len(form) > 24 and form[15] == masterCount:
                count += 1
                if count > qualification_checker.num_max_records:
                    return False, False, False
                if int.from_bytes(form[12:15][::-1]) > qualification_checker.max_record_number:
                    need_compacting = True
                if form[:4] == b'CELL':
                    if not qualification_checker.show_cells:
                        return False, False, True
                    new_cell = True
        return True, need_compacting, new_cell

    def already_esl(file):
        with open(file, 'rb') as f:
            f.seek(9)
            if f.read(1) == b'\x02':
                return True
            else:
                return False