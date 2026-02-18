import struct

class form_processor():
    
    def get_offsets_from_array(offset, field_size, struct_size=4):
        start = offset + 6
        return list(range(start, start + field_size, struct_size))

    def get_alt_texture_offsets(offset, form):
        offsets = []
        alternate_texture_count = struct.unpack("<I", form[offset+6:offset+10])[0]
        offset += 10
        for _ in range(alternate_texture_count):
            alt_tex_size = struct.unpack("<I", form[offset:offset+4])[0]
            offsets.append(offset+alt_tex_size+4)
            offset += 12 + alt_tex_size 
        return offsets
    
    def get_field_and_size(offset, form):
        field = form[offset:offset+4]
        if field != b'XXXX':
            field_size = struct.unpack("<H", form[offset+4:offset+6])[0]
            return field, field_size, offset
        else:
            offset += 6
            field_size = struct.unpack("<I", form[offset:offset+4])[0]
            offset += 4
            field = form[offset:offset+4]
            return field, field_size, offset
        
    def patch_form_data(data_list, forms, form_id_replacements, master_byte, form_ids, update_masters, updated_master_index):
        if not update_masters:
            for i, form, offsets in forms:
                for offset in offsets:
                    if form[offset+3:offset+4] >= master_byte:
                        to_id = form_id_replacements.get(bytes(form[offset:offset+3]))
                        if to_id is not None:
                            form[offset:offset+3] = to_id[:3]
                data_list[i] = bytes(form)
        else:
            if updated_master_index == -1:
                updated_master_byte = (int.from_bytes(master_byte) + 1).to_bytes()
            else:
                updated_master_byte = master_byte
            for i, form, offsets in forms:
                for offset in offsets:
                    if form[offset+3:offset+4] >= master_byte:
                        updated = False
                        to_id = form_id_replacements.get(bytes(form[offset:offset+3]))
                        if to_id is not None:
                            if len(to_id) == 4:
                                form[offset:offset+4] = to_id
                                updated = True
                            else:
                                form[offset:offset+4] = to_id + updated_master_byte
                                updated = True
                        if not updated and bytes(form[offset:offset+4]) in form_ids:
                            form[offset:offset+4] = form[offset:offset+3] + updated_master_byte
                data_list[i] = bytes(form)
        return data_list
    
    def patch_form_data_dependent(data_list, forms, form_id_replacements, master_index_byte, master_byte, form_ids, update_masters, updated_master_index):
        if not update_masters:
            for i, form, offsets in forms:
                for offset in offsets:
                    if form[offset+3:offset+4] == master_index_byte:
                        to_id = form_id_replacements.get(bytes(form[offset:offset+3]))
                        if to_id is not None:
                            form[offset:offset+3] = to_id[:3]
                data_list[i] = bytes(form)
        else:
            if updated_master_index == -1:
                updated_master_byte = (int.from_bytes(master_byte) + 1).to_bytes()
            else:
                updated_master_byte = master_byte
            for i, form, offsets in forms:
                for offset in offsets:
                    form_master_byte = form[offset+3:offset+4]
                    is_being_patched = form_master_byte == master_index_byte
                    is_being_updated = form_master_byte >= master_byte
                    if is_being_patched or is_being_updated:
                        updated = False if is_being_updated else True
                        to_id = form_id_replacements.get(bytes(form[offset:offset+3]))
                        if to_id is not None:
                            if len(to_id) == 4 and is_being_patched:    # Update Cell masters
                                form[offset:offset+4] = to_id
                                updated = True
                            elif is_being_updated and is_being_patched: # Update master byte and patch form id
                                form[offset:offset+4] = to_id + updated_master_byte
                                updated = True
                            elif is_being_updated:                      # Update master byte only
                                form[offset+3:offset+4] = updated_master_byte
                                updated = True
                            else:                                       # Patch compacted master form id
                                form[offset:offset+3] = to_id
                                updated = True
                        if not updated and bytes(form[offset:offset+4]) in form_ids:
                            form[offset:offset+4] = form[offset:offset+3] + updated_master_byte
                data_list[i] = bytes(form)
        return data_list
    
    def save_all_form_data(data_list):
        saved_forms = []

        default_handler = lambda i, form: [i, bytearray(form), [12]]

        # Records with default handler
        default_records = {
            b'AACT', b'ASTP', b'CLAS', b'CLFM', b'CSTY', b'DEBR',
            b'EYES', b'GMST', b'GRAS', b'IMAD', b'IMGS', b'KYWD',
            b'LCRT', b'LGTM', b'MATO', b'MOVT', b'REVB', b'SOPM',
            b'SPGD', b'TXST', b'VTYP', b'WOOP', b'VOLI', b'LENS'
        }
        # Records with shared handler
        placed_records = {
            b'PHZD', b'PGRE', b'PMIS', b'PARW', b'PBAR', b'PCON', b'PFLA', b'BEAM'
        }
        
        record_handlers = {
            b'REFR': form_processor.save_refr_data,
            b'ACHR': form_processor.save_achr_data,
            b'ACTI': form_processor.save_acti_data,
            b'ADDN': form_processor.save_addn_data,
            b'ALCH': form_processor.save_alch_data,
            b'AMMO': form_processor.save_ammo_data,
            b'ANIO': form_processor.save_anio_data,
            b'APPA': form_processor.save_appa_data,
            b'ARMA': form_processor.save_arma_data,
            b'ARMO': form_processor.save_armo_data,
            b'ARTO': form_processor.save_arto_data,
            b'ASPC': form_processor.save_aspc_data,
            b'AVIF': form_processor.save_avif_data,
            b'BOOK': form_processor.save_book_data,
            b'BPTD': form_processor.save_bptd_data,
            b'CAMS': form_processor.save_cams_data,
            b'CELL': form_processor.save_cell_data,
            b'CLMT': form_processor.save_clmt_data,
            b'COBJ': form_processor.save_cobj_data,
            b'COLL': form_processor.save_coll_data,
            b'CONT': form_processor.save_cont_data,
            b'CPTH': form_processor.save_cpth_data,
            b'DIAL': form_processor.save_dial_data,
            b'DLBR': form_processor.save_dlbr_data,
            b'DLVW': form_processor.save_dlvw_data,
            b'DOBJ': form_processor.save_dobj_data,
            b'DOOR': form_processor.save_door_data,
            b'DUAL': form_processor.save_dual_data,
            b'ECZN': form_processor.save_eczn_data,
            b'EFSH': form_processor.save_efsh_data,
            b'ENCH': form_processor.save_ench_data,
            b'EQUP': form_processor.save_equp_data,
            b'EXPL': form_processor.save_expl_data,
            b'FACT': form_processor.save_fact_data,
            b'FLOR': form_processor.save_flor_data,
            b'FLST': form_processor.save_flst_data,
            b'FSTP': form_processor.save_fstp_data,
            b'FSTS': form_processor.save_fsts_data,
            b'FURN': form_processor.save_furn_data,
            b'GLOB': form_processor.save_glob_data,
            b'GRUP': form_processor.save_grup_data,
            b'HAZD': form_processor.save_hazd_data,
            b'HDPT': form_processor.save_hdpt_data,
            b'IDLE': form_processor.save_idle_data,
            b'IDLM': form_processor.save_idlm_data,
            b'INFO': form_processor.save_info_data,
            b'INGR': form_processor.save_ingr_data,
            b'IPCT': form_processor.save_ipct_data,
            b'IPDS': form_processor.save_ipds_data,
            b'KEYM': form_processor.save_keym_data,
            b'LAND': form_processor.save_land_data,
            b'LCTN': form_processor.save_lctn_data,
            b'LIGH': form_processor.save_ligh_data,
            b'LSCR': form_processor.save_lscr_data,
            b'LTEX': form_processor.save_ltex_data,
            b'LVLI': form_processor.save_lvli_data,
            b'LVLN': form_processor.save_lvln_data,
            b'LVSP': form_processor.save_lvsp_data,
            b'MATT': form_processor.save_matt_data,
            b'MESG': form_processor.save_mesg_data,
            b'MGEF': form_processor.save_mgef_data,
            b'MISC': form_processor.save_misc_data,
            b'MSTT': form_processor.save_mstt_data,
            b'MUSC': form_processor.save_musc_data,
            b'MUST': form_processor.save_must_data,
            b'NAVI': form_processor.save_navi_data,
            b'NAVM': form_processor.save_navm_data,
            b'NOTE': form_processor.save_note_data,
            b'NPC_': form_processor.save_npc__data,
            b'OTFT': form_processor.save_otft_data,
            b'PACK': form_processor.save_pack_data,
            b'PERK': form_processor.save_perk_data,
            b'PROJ': form_processor.save_proj_data,
            b'QUST': form_processor.save_qust_data,
            b'RACE': form_processor.save_race_data,
            b'REGN': form_processor.save_regn_data,
            b'RELA': form_processor.save_rela_data,
            b'RFCT': form_processor.save_rfct_data,
            b'SCEN': form_processor.save_scen_data,
            b'SCRL': form_processor.save_scrl_data,
            b'SHOU': form_processor.save_shou_data,
            b'SLGM': form_processor.save_slgm_data,
            b'SMBN': form_processor.save_smbn_data,
            b'SMEN': form_processor.save_smen_data,
            b'SMQN': form_processor.save_smqn_data,
            b'SNCT': form_processor.save_snct_data,
            b'SNDR': form_processor.save_sndr_data,
            b'SOUN': form_processor.save_soun_data,
            b'SPEL': form_processor.save_spel_data,
            b'STAT': form_processor.save_stat_data,
            b'TACT': form_processor.save_tact_data,
            b'TES4': form_processor.save_tes4_data,
            b'TREE': form_processor.save_tree_data,
            b'WATR': form_processor.save_watr_data,
            b'WEAP': form_processor.save_weap_data,
            b'WRLD': form_processor.save_wrld_data,
            b'WTHR': form_processor.save_wthr_data,
        }
        
        for i, form in enumerate(data_list):
            record_type = form[:4]
            if record_type in placed_records:
                handler = form_processor.save_placed_data
            else:
                handler = record_handlers.get(record_type, default_handler if record_type in default_records else None)

            if handler:
                saved_forms.append(handler(i, form))
            else:
                print(f'Missing form processing for record type: {record_type}')

        return saved_forms
    
    def save_achr_data(i, form):
        achr_fields = [b'NAME', b'XEZN', b'INAM', b'XMRC', b'XAPR', b'XLRT', b'XHOR', b'XOWN', b'XESP', b'XLCN', b'XLRL', b'XEMI', b'XMBR', b'TNAM']
        special_achr_fields = [b'PDTO', b'VMAD', b'XLKR']

        achr_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in achr_fields and field_size >= 4:
                achr_offsets.append(offset + 6)
            elif field in special_achr_fields:
                if field == b'PDTO':
                    if form[offset+6:offset+7] == b'\x00':
                        achr_offsets.append(offset + 10)
                elif field == b'VMAD':
                    achr_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'XLKR':
                    achr_offsets.append(offset + 6)
                    achr_offsets.append(offset + 10)
            offset += field_size + 6
        return [i, bytearray(form), achr_offsets]
    
    def save_acti_data(i, form):
        acti_fields = [b'SNAM', b'VNAM', b'WNAM', b'KNAM']
        special_acti_fields = [b'KWDA', b'MODS', b'VMAD', b'DSTD', b'DMDS']

        acti_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in acti_fields and field_size >= 4:
                acti_offsets.append(offset + 6)
            elif field in special_acti_fields:
                if field == b'KWDA':
                    acti_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'DSTD':
                    acti_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    acti_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    acti_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'MODS':
                    acti_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'VMAD':
                    acti_offsets.extend(form_processor.vmad_reader(form, offset))

            offset += field_size + 6

        return [i, bytearray(form), acti_offsets]

    def save_addn_data(i, form):
        addn_fields = [b'SNAM']
        special_addn_fields = [b'MODS']

        addn_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in addn_fields and field_size >= 4:
                addn_offsets.append(offset + 6)
            elif field in special_addn_fields:
                if field == b'MODS':
                    addn_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), addn_offsets]

    def save_alch_data(i, form):
        alch_fields = [b'YNAM', b'ZNAM', b'EFID', b'ETYP']
        special_alch_fields = [b'KWDA', b'ENIT', b'MODS', b'CTDA', b'DSTD', b'DMDS']

        alch_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in alch_fields and field_size >= 4:
                alch_offsets.append(offset + 6)
            elif field in special_alch_fields:
                if field == b'KWDA':
                    alch_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'MODS':
                    alch_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'ENIT':
                    alch_offsets.append(offset + 14) #Addiction     6 + 8
                    alch_offsets.append(offset + 22) #UseSound SNDR 6 + 16
                elif field == b'CTDA':
                    alch_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'DSTD':
                    alch_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    alch_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    alch_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), alch_offsets]

    def save_ammo_data(i, form):
        ammo_fields = [b'YNAM', b'ZNAM', b'DATA']
        special_ammo_fields = [b'KWDA', b'MODS', b'DSTD', b'DMDS']

        ammo_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in ammo_fields and field_size >= 4:
                ammo_offsets.append(offset + 6)
            elif field in special_ammo_fields:
                if field == b'KWDA':
                    ammo_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'MODS':
                    ammo_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    ammo_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    ammo_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    ammo_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), ammo_offsets]

    def save_anio_data(i, form):
        special_anio_fields = [b'MODS']

        anio_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_anio_fields:
                if field == b'MODS':
                    anio_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), anio_offsets]

    def save_appa_data(i, form):
        appa_fields = [b'YNAM', b'ZNAM']
        special_appa_fields = [b'DSTD', b'DMDS', b'VMAD', b'MODS']

        appa_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in appa_fields and field_size >= 4:
                appa_offsets.append(offset + 6)
            elif field in special_appa_fields:
                if field == b'DSTD':
                    appa_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    appa_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    appa_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'VMAD':
                    appa_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'MODS':
                    appa_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), appa_offsets]

    def save_arma_data(i, form):
        arma_fields = [b'RNAM', b'NAM0', b'NAM1', b'NAM2', b'NAM3', b'MODL', b'SNDD', b'ONAM']
        special_arma_fields = [b'MO2S', b'MO3S', b'MO4S', b'MO5S']

        arma_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in arma_fields and field_size >= 4:
                arma_offsets.append(offset + 6)
            elif field in special_arma_fields:
                if field in (b'MO2S', b'MO3S', b'MO4S', b'MO5S'):
                    arma_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), arma_offsets]
    
    def save_armo_data(i, form):
        armo_fields = [b'EITM', b'YNAM', b'ZNAM', b'ETYP', b'BIDS', b'BAMT', b'RNAM', b'MODL', b'TNAM']
        special_armo_fields = [b'KWDA', b'VMAD', b'MODS', b'MO2S', b'MO4S', b'DSTD', b'DMDS']

        armo_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in armo_fields and field_size >= 4:
                armo_offsets.append(offset + 6)
            elif field in special_armo_fields:
                if field == b'KWDA':
                    armo_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'VMAD':
                    armo_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field in (b'MODS', b'MO2S', b'MO4S'):
                    armo_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    armo_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    armo_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    armo_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), armo_offsets]

    def save_arto_data(i, form):
        special_arto_fields = [b'MODS']

        arto_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_arto_fields:
                if field == b'MODS':
                    arto_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), arto_offsets]

    def save_aspc_data(i, form):
        aspc_fields = [b'SNAM', b'RDAT', b'BNAM']

        aspc_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in aspc_fields and field_size >= 4:
                aspc_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), aspc_offsets]

    def save_avif_data(i, form):
        avif_fields = [b'PNAM', b'SNAM']

        avif_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in avif_fields and field_size >= 4:
                avif_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), avif_offsets]

    def save_book_data(i, form):
        book_fields = [b'YNAM', b'ZNAM', b'INAM']
        special_book_fields = [b'VMAD', b'MODS', b'DSTD', b'DMDS', b'KWDA', b'DATA']

        book_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in book_fields and field_size >= 4:
                book_offsets.append(offset + 6)
            elif field in special_book_fields:
                if field == b'KWDA':
                    book_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'VMAD':
                    book_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'MODS':
                    book_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    book_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    book_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    book_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DATA':
                    book_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), book_offsets]

    def save_bptd_data(i, form):
        bptd_fields = [b'RAGA'] # Might not be necessary
        special_bptd_fields = [b'MODS', b'BPND']

        bptd_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in bptd_fields and field_size >= 4:
                bptd_offsets.append(offset + 6)
            elif field in special_bptd_fields:
                if field == b'MODS':
                    bptd_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'BPND':
                    in_field_offset = offset + 6
                    bptd_offsets.append(in_field_offset+ 12) # DEBR
                    bptd_offsets.append(in_field_offset+ 16) # EXPL
                    bptd_offsets.append(in_field_offset+ 32) # DEBR
                    bptd_offsets.append(in_field_offset+ 36) # EXPL
                    bptd_offsets.append(in_field_offset+ 68) # Severable IPDS
                    bptd_offsets.append(in_field_offset+ 72) # Explodable IPDS
            offset += field_size + 6

        return [i, bytearray(form), bptd_offsets]

    def save_cams_data(i, form):
        cams_fields = [b'MNAM']
        special_cams_fields = [b'MODS']

        cams_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in cams_fields and field_size >= 4:
                cams_offsets.append(offset + 6)
            elif field in special_cams_fields:
                if field == b'MODS':
                    cams_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), cams_offsets]

    def save_cell_data(i, form):
        cell_fields = [b'LTMP', b'XLCN', b'XCWT', b'XOWN', b'XILL', b'XCCM', b'XCAS', b'XEZN', b'XCMO', b'XCIM']
        special_cell_fields = [b'XCLR']

        cell_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in cell_fields and field_size >= 4:
                cell_offsets.append(offset + 6)
            elif field in special_cell_fields:
                if field == b'XCLR':
                    cell_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6

        return [i, bytearray(form), cell_offsets]

    def save_clmt_data(i, form):
        special_clmt_fields = [b'WLST', b'MODS']

        clmt_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_clmt_fields:
                if field == b'WLST':
                    array_size = field_size // 12
                    in_field_offset = offset + 6
                    for _ in range(array_size):
                        clmt_offsets.append(in_field_offset)
                        clmt_offsets.append(in_field_offset + 8)
                        in_field_offset += 12
                elif field == b'MODS':
                    clmt_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), clmt_offsets]

    def save_cobj_data(i, form):
        cobj_fields = [b'CNAM', b'BNAM', b'CNTO']
        special_cobj_fields = [b'COED', b'CTDA']

        cobj_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in cobj_fields and field_size >= 4:
                cobj_offsets.append(offset + 6)
            elif field in special_cobj_fields:
                if field == b'COED':
                    cobj_offsets.append(offset + 6)
                    cobj_offsets.append(offset + 10)
                elif field == b'CTDA':
                    cobj_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), cobj_offsets]

    def save_coll_data(i, form):
        special_coll_fields = [b'CNAM']

        coll_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_coll_fields:
                if field == b'CNAM':
                    intv_offset = form.find(b'INTV', 24)
                    if intv_offset != -1:
                        intv = struct.unpack("<I", form[intv_offset+6:intv_offset+10])[0]
                        in_field_offset = offset + 6
                        for _ in range(intv):
                            coll_offsets.append(in_field_offset)
                            in_field_offset += 4
            offset += field_size + 6

        return [i, bytearray(form), coll_offsets]
    
    def save_cont_data(i, form):
        cont_fields = [b'SNAM', b'QNAM', b'CNTO']
        special_cont_fields = [b'MODS', b'VMAD', b'COED', b'DSTD', b'DMDS']

        cont_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in cont_fields and field_size >= 4:
                cont_offsets.append(offset + 6)
            elif field in special_cont_fields:
                if field == b'MODS':
                    cont_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'VMAD':
                    cont_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'COED':
                    cont_offsets.append(offset + 6)
                    cont_offsets.append(offset + 10)
                elif field == b'DSTD':
                    cont_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    cont_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    cont_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), cont_offsets]

    def save_cpth_data(i, form):
        cpth_fields = [b'SNAM']
        special_cpth_fields = [b'ANAM', b'CTDA']

        cpth_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in cpth_fields and field_size >= 4:
                cpth_offsets.append(offset + 6)
            elif field in special_cpth_fields:
                if field == b'ANAM':
                    cpth_offsets.append(offset + 6)
                    cpth_offsets.append(offset + 10)
                elif field == b'CTDA':
                    cpth_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), cpth_offsets]

    def save_dial_data(i, form):
        dial_fields = [b'QNAM', b'BNAM']

        dial_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in dial_fields and field_size >= 4:
                dial_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), dial_offsets]
    
    def save_dlbr_data(i, form):
        dlbr_fields = [b'QNAM', b'SNAM']

        dlbr_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in dlbr_fields and field_size >= 4:
                dlbr_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), dlbr_offsets]
    
    def save_dlvw_data(i, form):
        dlvw_fields = [b'QNAM', b'BNAM', b'TNAM']

        dlvw_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in dlvw_fields and field_size >= 4:
                dlvw_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), dlvw_offsets]

    def save_dobj_data(i, form): 
        special_dobj_fields = [b'DNAM']

        dobj_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_dobj_fields:
                if field == b'DNAM':
                    array_size = field_size // 8
                    in_field_offset = offset + 6
                    for _ in range(array_size):
                        dobj_offsets.append(in_field_offset + 4)
                        in_field_offset += 8
                        
            offset += field_size + 6

        return [i, bytearray(form), dobj_offsets]

    def save_door_data(i, form): 
        door_fields = [b'SNAM', b'ANAM', b'BNAM', b'TNAM']
        special_door_fields = [b'VMAD', b'MODS', b'DSTD', b'DMDS']

        door_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in door_fields and field_size >= 4:
                door_offsets.append(offset + 6)
            elif field in special_door_fields:
                if field == b'MODS':
                    door_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'VMAD':
                    door_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DSTD':
                    door_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    door_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    door_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), door_offsets]

    def save_dual_data(i, form): 
        special_dual_fields = [b'DATA']

        dual_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_dual_fields:
                if b'DATA':
                    in_field_offset = offset + 6
                    dual_offsets.append(in_field_offset)    # PROJ
                    dual_offsets.append(in_field_offset+ 4) # EXPL
                    dual_offsets.append(in_field_offset+ 8) # EFSH
                    dual_offsets.append(in_field_offset+ 12)# ARTO
                    dual_offsets.append(in_field_offset+ 16)# IPDS
            offset += field_size + 6

        return [i, bytearray(form), dual_offsets]

    def save_eczn_data(i, form): 
        special_eczn_fields = [b'DATA']

        eczn_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_eczn_fields:
                if field == b'DATA':
                    eczn_offsets.append(offset + 6)
                    eczn_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), eczn_offsets]

    def save_efsh_data(i, form): 
        special_efsh_fields = [b'DATA']

        efsh_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_efsh_fields:
                if field == b'DATA':
                    efsh_offsets.append(offset + 250) # 244 + 6 Addon Models
                    efsh_offsets.append(offset + 314) # 308 + 6 Ambient Sound
            offset += field_size + 6

        return [i, bytearray(form), efsh_offsets]

    def save_ench_data(i, form):
        ench_fields = [b'EFID']
        special_ench_fields = [b'ENIT', b'CTDA']

        ench_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in ench_fields and field_size >= 4:
                ench_offsets.append(offset + 6)
            elif field in special_ench_fields:
                if field == b'CTDA':
                    ench_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'ENIT':
                    if field_size == 36:
                        ench_offsets.append(offset + 34) #Base Enchantment (28 + 6)
                        ench_offsets.append(offset + 38) #Worn Restrictions FLST (32 + 6)
                    elif field_size == 32:
                        ench_offsets.append(offset + 34) #Base Enchantment (28 + 6)
            offset += field_size + 6

        return [i, bytearray(form), ench_offsets]

    def save_equp_data(i, form): 
        special_equp_fields = [b'PNAM']

        equp_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_equp_fields:
                if field == b'PNAM':
                    equp_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6

        return [i, bytearray(form), equp_offsets]

    def save_expl_data(i, form): 
        expl_fields = [b'EITM', b'MNAM']
        special_FORM_fields = [b'DATA', b'MODS']

        expl_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in expl_fields and field_size >= 4:
                expl_offsets.append(offset + 6)
            elif field in special_FORM_fields:
                if field == b'DATA':                        #DATA description not present in uesp wiki
                    in_data_offset = offset + 6
                    expl_offsets.append(in_data_offset)     # LIGH
                    expl_offsets.append(in_data_offset+ 4)  # SNDR 1
                    expl_offsets.append(in_data_offset+ 8)  # SNDR 2
                    expl_offsets.append(in_data_offset+ 12) # IPDS
                    expl_offsets.append(in_data_offset+ 16) # WEAP
                    expl_offsets.append(in_data_offset+ 20) # PROJ
                elif field == b'MODS':
                    expl_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), expl_offsets]

    def save_fact_data(i, form): 
        fact_fields = [b'XNAM', b'JAIL', b'WAIT', b'STOL', b'PLCN', b'CRGR', b'JOUT', b'VEND', b'VENC']
        special_fact_fields = [b'PLVD', b'CTDA']

        fact_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in fact_fields and field_size >= 4:
                fact_offsets.append(offset + 6)
            elif field in special_fact_fields:
                if field == b'PLVD':
                    fact_offsets.append(offset + 10)
                elif field == b'CTDA':
                    fact_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), fact_offsets]

    def save_flor_data(i, form): 
        flor_fields = [b'PFIG', b'SNAM']
        special_flor_fields = [b'KWDA', b'VMAD', b'MODS', b'DSTD', b'DMDS']

        flor_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in flor_fields and field_size >= 4:
                flor_offsets.append(offset + 6)
            elif field in special_flor_fields:
                if field == b'KWDA':
                    flor_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'VMAD':
                    flor_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'MODS':
                    flor_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    flor_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    flor_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    flor_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), flor_offsets]

    def save_flst_data(i, form): 
        flst_fields = [b'LNAM']

        flst_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in flst_fields and field_size >= 4:
                flst_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), flst_offsets]

    def save_fstp_data(i, form): 
        fstp_fields = [b'DATA']

        fstp_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in fstp_fields and field_size >= 4:
                fstp_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), fstp_offsets]

    def save_fsts_data(i, form): 
        special_fsts_fields = [b'DATA']

        fsts_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_fsts_fields:
                if field == b'DATA':
                    fsts_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6

        return [i, bytearray(form), fsts_offsets]

    def save_furn_data(i, form): 
        furn_fields = [b'KNAM', b'NAM1', b'FNMK']
        special_furn_fields = [b'VMAD', b'MODS', b'KWDA', b'DSTD', b'DMDS']

        furn_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in furn_fields and field_size >= 4:
                furn_offsets.append(offset + 6)
            elif field in special_furn_fields:
                if field == b'KWDA':
                    furn_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'VMAD':
                    furn_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'MODS':
                    furn_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    furn_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    furn_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    furn_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), furn_offsets]

    def save_glob_data(i, form): 
        special_glob_fields = [b'VMAD'] #probably not necessary

        glob_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_glob_fields:
                if field == b'VMAD':
                    glob_offsets.extend(form_processor.vmad_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), glob_offsets]

    def save_grup_data(i, form): 
        grup_type = struct.unpack("<I", form[12:16])[0]
        if grup_type in (1, 6, 7, 8, 9):
            grup_offsets = [8]
        else:
            grup_offsets = []
        return [i, bytearray(form), grup_offsets]

    def save_hazd_data(i, form): 
        hazd_fields = [b'MNAM']
        special_hazd_fields = [b'DATA', b'MODS']

        hazd_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in hazd_fields and field_size >= 4:
                hazd_offsets.append(offset + 6)
            elif field in special_hazd_fields:
                if field == b'DATA':
                    in_field_offset = offset + 6
                    hazd_offsets.append(in_field_offset+ 24) #Spell
                    hazd_offsets.append(in_field_offset+ 28) #Light
                    hazd_offsets.append(in_field_offset+ 32) #Impact Data Set
                    hazd_offsets.append(in_field_offset+ 36) #Sound
                elif field == b'MODS':
                    hazd_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), hazd_offsets]

    def save_hdpt_data(i, form): 
        hdpt_fields = [b'HNAM', b'TNAM', b'RNAM', b'CNAM']
        special_hdpt_fields = [b'MODS']

        hdpt_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in hdpt_fields and field_size >= 4:
                hdpt_offsets.append(offset + 6)
            elif field in special_hdpt_fields:
                if field == b'MODS':
                    hdpt_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), hdpt_offsets]
    
    def save_idle_data(i, form): 
        special_idle_fields = [b'CTDA', b'ANAM']

        idle_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_idle_fields:
                if field == b'CTDA':
                    idle_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'ANAM':
                    idle_offsets.append(offset + 6)
                    idle_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), idle_offsets]

    def save_idlm_data(i, form): 
        special_idlm_fields = [b'IDLA', b'MODS']

        idlm_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_idlm_fields:
                if field == b'IDLA':
                    idlm_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'MODS':
                    idlm_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), idlm_offsets]

    def save_info_data(i, form): 
        info_fields = [b'PNAM', b'TCLT', b'DNAM', b'SNAM', b'LNAM', b'ANAM', b'TWAT', b'ONAM', b'TPIC']
        special_info_fields = [b'VMAD', b'TRDT', b'CTDA']

        info_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in info_fields and field_size >= 4:
                info_offsets.append(offset + 6)
            elif field in special_info_fields:
                if field == b'VMAD':
                    info_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'TRDT':
                    info_offsets.append(offset + 22) #response.SoundFile (16 + 6)
                elif field == b'CTDA':
                    info_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), info_offsets]

    def save_ingr_data(i, form): 
        ingr_fields = [b'YNAM', b'ZNAM', b'EFID', b'ETYP']
        special_ingr_fields = [b'VMAD', b'KWDA', b'CTDA', b'MODS', b'DSTD', b'DMDS']

        ingr_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in ingr_fields and field_size >= 4:
                ingr_offsets.append(offset + 6)
            elif field in special_ingr_fields:
                if field == b'VMAD':
                    ingr_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'KWDA':
                    ingr_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'CTDA':
                    ingr_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'MODS':
                    ingr_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    ingr_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    ingr_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    ingr_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), ingr_offsets]

    def save_ipct_data(i, form): 
        ipct_fields = [b'DNAM', b'ENAM', b'SNAM', b'NAM1', b'NAM2']
        special_ipct_fields = [b'MODS']

        ipct_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in ipct_fields and field_size >= 4:
                ipct_offsets.append(offset + 6)
            elif field in special_ipct_fields:
                if field == b'MODS':
                    ipct_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), ipct_offsets]

    def save_ipds_data(i, form): 
        special_ipds_fields = [b'PNAM']

        ipds_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_ipds_fields:
                if field == b'PNAM':
                    ipds_offsets.append(offset + 6)
                    ipds_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), ipds_offsets]

    def save_keym_data(i, form): 
        keym_fields = [b'YNAM', b'ZNAM']
        special_keym_fields = [b'VMAD', b'KWDA', b'MODS', b'DSTD', b'DMDS']

        keym_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in keym_fields and field_size >= 4:
                keym_offsets.append(offset + 6)
            elif field in special_keym_fields:
                if field == b'VMAD':
                    keym_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'KWDA':
                    keym_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'MODS':
                    keym_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    keym_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    keym_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    keym_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), keym_offsets]

    def save_land_data(i, form): 
        land_fields = [b'ATXT', b'BTXT']

        land_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in land_fields and field_size >= 4:
                land_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), land_offsets]

    def save_lctn_data(i, form):
        lctn_fields = [b'ACEC', b'LCEC', b'PNAM', b'NAM1', b'FNAM', b'MNAM', b'NAM0']
        special_lctn_fields = [b'ACPR', b'LCPR', b'RCPR', b'ACUN', b'LCUN', b'ACSR', b'LCSR', b'ACEP', b'LCEP', b'ACID', b'LCID', b'KWDA']

        lctn_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in lctn_fields and field_size >= 4:
                lctn_offsets.append(offset + 6)
            elif field in special_lctn_fields:
                if field in (b'ACPR', b'LCPR', b'ACEP', b'LCEP'):
                    struct_count = field_size // 12
                    in_field_offset = offset + 6
                    for _ in range(struct_count):
                        lctn_offsets.append(in_field_offset)
                        lctn_offsets.append(in_field_offset+ 4)
                        in_field_offset += 12
                elif field in (b'RCPR', b'ACID', b'LCID'):
                    lctn_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field in (b'ACUN', b'LCUN'):
                    struct_count = field_size // 12
                    in_field_offset = offset + 6
                    for _ in range(struct_count):
                        lctn_offsets.append(in_field_offset)
                        lctn_offsets.append(in_field_offset+ 4)
                        lctn_offsets.append(in_field_offset+ 8)
                        in_field_offset += 12
                elif field in (b'ACSR', b'LCSR'):
                    struct_count = field_size // 16
                    in_field_offset = offset + 6
                    for _ in range(struct_count):
                        lctn_offsets.append(in_field_offset)
                        lctn_offsets.append(in_field_offset+ 4)
                        lctn_offsets.append(in_field_offset+ 8)
                        in_field_offset += 16
                elif field == b'KWDA':
                    lctn_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6

        return [i, bytearray(form), lctn_offsets]

    def save_ligh_data(i, form): 
        ligh_fields = [b'SNAM', b'LNAM']
        special_ligh_fields = [b'VMAD', b'DSTD', b'DMDS', b'MODS']

        ligh_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in ligh_fields and field_size >= 4:
                ligh_offsets.append(offset + 6)
            elif field in special_ligh_fields:
                if field == b'VMAD':
                    ligh_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DSTD':
                    ligh_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    ligh_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    ligh_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'MODS':
                    ligh_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), ligh_offsets]

    def save_lscr_data(i, form): 
        lscr_fields = [b'NNAM']
        special_lscr_fields = [b'CTDA']

        lscr_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in lscr_fields and field_size >= 4:
                lscr_offsets.append(offset + 6)
            elif field in special_lscr_fields:
                if field == b'CTDA':
                    lscr_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), lscr_offsets]

    def save_ltex_data(i, form): 
        ltex_fields = [b'TNAM', b'MNAM', b'GNAM']

        ltex_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in ltex_fields and field_size >= 4:
                ltex_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), ltex_offsets]
    
    def save_lvli_data(i, form): 
        lvli_fields = [b'LVLG']
        special_lvli_fields = [b'LVLO', b'COED']

        lvli_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in lvli_fields and field_size >= 4:
                lvli_offsets.append(offset + 6)
            elif field in special_lvli_fields:
                if field == b'LVLO':
                    lvli_offsets.append(offset+ 10)
                elif field == b'COED':
                    lvli_offsets.append(offset+ 6)
                    lvli_offsets.append(offset+ 10)
            offset += field_size + 6

        return [i, bytearray(form), lvli_offsets]

    def save_lvln_data(i, form): 
        lvln_fields = [b'LVLG']
        special_lvln_fields = [b'MODS', b'LVLO', b'COED']

        lvln_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in lvln_fields and field_size >= 4:
                lvln_offsets.append(offset + 6)
            elif field in special_lvln_fields:
                if field == b'COED':
                    lvln_offsets.append(offset+ 6)
                    lvln_offsets.append(offset+ 10)
                elif field == b'MODS':
                    lvln_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'LVLO':
                    lvln_offsets.append(offset+ 10)
            offset += field_size + 6

        return [i, bytearray(form), lvln_offsets]

    def save_lvsp_data(i, form):
        special_lvsp_fields = [b'LVLO']

        lvsp_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_lvsp_fields:
                if field == b'LVLO':
                    lvsp_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), lvsp_offsets]

    def save_matt_data(i, form): 
        matt_fields = [b'HNAM', b'PNAM']

        matt_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in matt_fields and field_size >= 4:
                matt_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), matt_offsets]

    def save_mesg_data(i, form): 
        mesg_fields = [b'QNAM', b'INAM']
        special_mesg_fields = [b'CTDA']

        mesg_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in mesg_fields and field_size >= 4:
                mesg_offsets.append(offset + 6)
            elif field in special_mesg_fields:
                if field == b'CTDA':
                    mesg_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), mesg_offsets]

    def save_mgef_data(i, form):
        mgef_fields = [b'MDOB', b'ESCE']
        special_mgef_fields = [b'KWDA', b'SNDD', b'CTDA', b'VMAD', b'DATA']

        mgef_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in mgef_fields and field_size >= 4:
                mgef_offsets.append(offset + 6)
            elif field in special_mgef_fields:
                if field == b'KWDA':
                    mgef_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'SNDD':
                    list_size = field_size // 8
                    in_field_offset = offset + 6
                    for _ in range(list_size):
                        mgef_offsets.append(in_field_offset+4)
                        in_field_offset += 8
                elif field == b'CTDA':
                    mgef_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'VMAD':
                    mgef_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DATA':
                    data_offset = offset + 6 #start of DATA's data
                    mgef_offsets.append(data_offset + 8)    # 08:RelatedID
                    mgef_offsets.append(data_offset + 24)   # 18:LightID
                    mgef_offsets.append(data_offset + 32)   # 20:HitShader
                    mgef_offsets.append(data_offset + 36)   # 24:EnchantShader
                    mgef_offsets.append(data_offset + 72)   # 48:ProjectileID
                    mgef_offsets.append(data_offset + 76)   # 4C:ExplosionID
                    mgef_offsets.append(data_offset + 92)   # 5C:CastingArtID
                    mgef_offsets.append(data_offset + 96)   # 60:HitEffectArtID
                    mgef_offsets.append(data_offset + 100)  # 64:ImpactDataID
                    mgef_offsets.append(data_offset + 108)  # 6C:DualCastID
                    mgef_offsets.append(data_offset + 116)  # 74:EnchantArtID
                    mgef_offsets.append(data_offset + 120)  # Hit Visuals?
                    mgef_offsets.append(data_offset + 124)  # Enchant Visuals?
                    mgef_offsets.append(data_offset + 128)  # 80:EquipAbility
                    mgef_offsets.append(data_offset + 132)  # 84:ImageSpaceModID
                    mgef_offsets.append(data_offset + 136)  # 88:PerkID
            offset += field_size + 6

        return [i, bytearray(form), mgef_offsets]

    def save_misc_data(i, form): 
        misc_fields = [b'YNAM', b'ZNAM']
        special_misc_fields = [b'VMAD', b'MODS', b'DSTD', b'DMDS', b'KWDA']

        misc_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in misc_fields and field_size >= 4:
                misc_offsets.append(offset + 6)
            elif field in special_misc_fields:
                if field == b'KWDA':
                    misc_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'VMAD':
                    misc_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'MODS':
                    misc_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    misc_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    misc_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    misc_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), misc_offsets]

    def save_mstt_data(i, form): 
        mstt_fields = [b'SNAM']
        special_mstt_fields = [b'MODS', b'DSTD', b'DMDS']

        mstt_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in mstt_fields and field_size >= 4:
                mstt_offsets.append(offset + 6)
            elif field in special_mstt_fields:
                if field == b'MODS':
                    mstt_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    mstt_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    mstt_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    mstt_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), mstt_offsets]

    def save_musc_data(i, form): 
        special_musc_fields = [b'TNAM']

        musc_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_musc_fields:
                if field == b'TNAM':
                    musc_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6

        return [i, bytearray(form), musc_offsets]

    def save_must_data(i, form): 
        special_must_fields = [b'CTDA', b'SNAM']
        
        must_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_must_fields:
                if field == b'CTDA':
                    must_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'SNAM':
                    form_id_count = field_size // 4
                    in_field_offset = offset + 6
                    for _ in range(form_id_count):
                        if form[in_field_offset:in_field_offset+4] != b'\x00\x00\x00\x00':
                            must_offsets.append(in_field_offset)
                        in_field_offset += 4
            offset += field_size + 6

        return [i, bytearray(form), must_offsets]
    
    def save_navi_data(i, form): 
        special_navi_fields = [b'NVMI', b'NVPP', b'NVSI']

        navi_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_navi_fields:
                if field == b'NVSI':
                    navi_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'NVPP':
                    path_count = struct.unpack("<I", form[offset+6:offset+10])[0]
                    in_field_offset = offset + 10
                    #Path Table
                    for _ in range(path_count):
                        form_id_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                        in_field_offset += 4
                        for _ in range(form_id_count):
                            navi_offsets.append(in_field_offset)
                            in_field_offset += 4
                    node_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4
                    #Node Table
                    for _ in range(node_count):
                        navi_offsets.append(in_field_offset)
                        in_field_offset += 8
                elif field == b'NVMI':
                    in_field_offset = offset + 6
                    navi_offsets.append(in_field_offset)    # Navmesh
                    in_field_offset += 24                   # Merged to Count
                    merged_to_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4                    # start of Merged to
                    for _ in range(merged_to_count):
                        navi_offsets.append(in_field_offset)
                        in_field_offset += 4
                    perferred_merges_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4                    # start of Perferred Merges
                    for _ in range(perferred_merges_count):
                        navi_offsets.append(in_field_offset)
                        in_field_offset += 4
                    door_refr_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4                    # start of door structs
                    for _ in range(door_refr_count):
                        navi_offsets.append(in_field_offset+4)
                        in_field_offset += 8
                    navi_offsets.append(offset + 6 + field_size - 8) # World Space
                    navi_offsets.append(offset + 6 + field_size - 4) # Cell
            offset += field_size + 6

        return [i, bytearray(form), navi_offsets]

    def save_navm_data(i, form): 
        special_navm_fields = [b'NVNM', b'ONAM']

        navm_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_navm_fields:
                if field == b'NVNM':
                    in_field_offset = offset + 6 + 8
                    navm_offsets.append(in_field_offset)        # World Space
                    navm_offsets.append(in_field_offset + 4)    # Cell
                    in_field_offset += 8
                    num_vertices = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4
                    in_field_offset += 12 * num_vertices
                    num_tris = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4
                    in_field_offset += 16 * num_tris
                    ext_connections = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4
                    for _ in range(ext_connections):
                        navm_offsets.append(in_field_offset + 4)# Navmesh in Connections Struct
                        in_field_offset += 10
                    num_door_tris = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4
                    for _ in range(num_door_tris):
                        navm_offsets.append(in_field_offset + 6)# Door REFR
                        in_field_offset += 10
                elif field == b'ONAM':
                    navm_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6

        return [i, bytearray(form), navm_offsets]

    def save_note_data(i, form): 
        note_fields = [b'ONAM', b'YNAM', b'ZNAM', b'SNAM']
        special_note_fields = [b'TNAM', b'VMAD', b'MODS']

        note_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in note_fields and field_size >= 4:
                note_offsets.append(offset + 6)
            elif field in special_note_fields:
                if field == b'TNAM':
                    data_offset = form.find(b'DATA') + 6
                    if form[data_offset:data_offset+1] == b'\x03':
                        note_offsets.append(offset + 6)
                elif field == b'VMAD':
                    note_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'MODS':
                    note_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), note_offsets]

    def save_npc__data(i, form): 
        npc__fields = [b'INAM', b'VTCK', b'TPLT', b'RNAM', b'SPLO', b'WNAM', b'ANAM', b'ATKR', b'SPOR', b'OCOR', b'GWOR', b'ECOR', b'PKID', b'CNTO',
                       b'CNAM', b'PNAM', b'HCLF', b'ZNAM', b'GNAM', b'CSDI', b'CSCR', b'DOFT', b'SOFT', b'DPLT', b'CRIF', b'FTST', b'SNAM', b'PRKR']
        special_npc__fields = [b'VMAD', b'DSTD', b'DMDS', b'ATKD', b'COED', b'KWDA']

        npc__offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in npc__fields and field_size >= 4:
                npc__offsets.append(offset + 6)
            elif field in special_npc__fields:
                if field == b'KWDA':
                    npc__offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'VMAD':
                    npc__offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DSTD':
                    npc__offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    npc__offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    npc__offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'ATKD':
                    npc__offsets.append(offset + 8)     # Attack Spell
                    npc__offsets.append(offset + 32)    # Attack Type
                elif field == b'COED':
                    npc__offsets.append(offset + 6)
                    npc__offsets.append(offset + 10)

            offset += field_size + 6

        return [i, bytearray(form), npc__offsets]

    def save_otft_data(i, form): 
        special_otft_fields = [b'INAM']

        otft_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_otft_fields:
                if field == b'INAM':
                    otft_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6

        return [i, bytearray(form), otft_offsets]
    
    def save_pack_data(i, form): 
        pack_fields = [b'CNAM', b'QNAM', b'TPIC', b'INAM']
        special_pack_fields = [b'VMAD', b'CTDA', b'IDLA', b'PKCU', b'PDTO', b'PLDT', b'PTDA']

        pack_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in pack_fields and field_size >= 4:
                pack_offsets.append(offset + 6)
            elif field in special_pack_fields:
                if field == b'VMAD':
                    pack_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'CTDA':
                    pack_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'IDLA':
                    pack_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field in (b'PKCU', b'PDTO', b'PLDT', b'PTDA'):
                    pack_offsets.append(offset + 10)

            offset += field_size + 6

        return [i, bytearray(form), pack_offsets]

    def save_perk_data(i, form): 
        perk_fields = [b'NNAM']
        special_perk_fields = [b'VMAD', b'CTDA', b'DATA', b'EPFD']

        perk_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in perk_fields and field_size >= 4:
                perk_offsets.append(offset + 6)
            elif field in special_perk_fields:
                if field == b'VMAD':
                    perk_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'CTDA':
                    perk_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'DATA':
                    if field_size == 4 or field_size == 8:
                        perk_offsets.append(offset + 6)
                elif field == b'EPFD':
                    current_epft_offset = form.rfind(b'EPFT', 24, offset)
                    epft_type = form[current_epft_offset+6:current_epft_offset+7]
                    if epft_type in (b'\x03', b'\x04', b'\x05'):
                        perk_offsets.append(offset + 6)

            offset += field_size + 6

        return [i, bytearray(form), perk_offsets]

    def save_placed_data(i, form): 
        placed_fields = [b'NAME', b'XEZN', b'XOWN', b'XPWR', b'XAPR', b'XESP', b'XEMI', b'XMBR', b'XLRL', b'XLRT']
        special_placed_fields = [b'VMAD', b'XLKR']

        placed_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in placed_fields:
                placed_offsets.append(offset + 6)
            elif field in special_placed_fields:
                if field == b'VMAD':
                    placed_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'XLKR':
                    placed_offsets.append(offset + 6)
                    placed_offsets.append(offset + 10)
                
            offset += field_size + 6

        return [i, bytearray(form), placed_offsets]

    def save_proj_data(i, form): 
        special_proj_fields = [b'DSTD', b'DATA', b'DMDS', b'MODS']

        proj_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_proj_fields:
                if field == b'DSTD':
                    proj_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    proj_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DATA':
                    data_offset = offset + 6
                    proj_offsets.append(data_offset+ 16)    # Light
                    proj_offsets.append(data_offset+ 20)    # Muzzle Flash Light
                    proj_offsets.append(data_offset+ 36)    # Explosion Type
                    proj_offsets.append(data_offset+ 40)    # Sound Record
                    proj_offsets.append(data_offset+ 56)    # Countdown Sound
                    proj_offsets.append(data_offset+ 60)    # Disable Sound?
                    proj_offsets.append(data_offset+ 64)    # Default Weapon Source
                    proj_offsets.append(data_offset+ 84)    # Decal Data
                    proj_offsets.append(data_offset+ 88)    # Collision Layer
                elif field in (b'MODS', b'DMDS'):
                    proj_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), proj_offsets]

    def save_qust_data(i, form): 
        qust_fields = [b'QTGL', b'NAM0', b'ALCO', b'ALEQ', b'KNAM', b'ALRT', b'ALFL', b'ALFR', b'ALUA', b'CNTO', b'SPOR', b'OCOR', b'GWOR', b'ECOR', b'ALDN',
                        b'ALSP', b'ALFC', b'ALPC', b'VTCK', b'QSTA']
        special_qust_fields = [b'VMAD', b'CTDA', b'KWDA', b'COED']

        qust_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in qust_fields and field_size >= 4:
                qust_offsets.append(offset + 6)
            elif field in special_qust_fields:
                if field == b'VMAD':
                    qust_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'CTDA':
                    qust_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'KWDA':
                    qust_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'COED':
                    qust_offsets.append(offset+ 6)
                    qust_offsets.append(offset+ 10)
            offset += field_size + 6

        return [i, bytearray(form), qust_offsets]

    def save_race_data(i, form): 
        race_fields = [b'SPLO', b'WNAM', b'ATKR', b'GNAM', b'NAM4', b'NAM5', b'NAM7', b'ONAM', b'LNAM', b'MTYP', b'QNAM', b'UNES', b'WKMV', b'HEAD', b'RPRF', b'DFTF', b'ENAM',
                        b'RNMV', b'SWMV', b'FLMV', b'SNMV', b'SPMV', b'RPRM', b'AHCM', b'FTSM', b'DFTM', b'TIND', b'TINC', b'NAM8', b'RNAM', b'AHCF', b'FTSF', b'HNAM']
        special_race_fields = [b'KWDA', b'VTCK', b'DNAM', b'HCLF', b'ATKD', b'MODS']

        race_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in race_fields and field_size >= 4:
                race_offsets.append(offset + 6)
            elif field in special_race_fields:
                if field == b'KWDA':
                    race_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field in (b'VTCK', b'DNAM', b'HCLF'):
                    race_offsets.append(offset + 6)
                    race_offsets.append(offset + 10)
                elif field == b'ATKD':
                    race_offsets.append(offset+ 14)     # Attack Spell
                    race_offsets.append(offset+ 32)     # Attack Type
                elif field == b'MODS':
                    race_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), race_offsets]
    
    def save_refr_data(i, form):
        refr_fields = [b'NAME', b'LNAM', b'INAM', b'XLRM', b'XEMI', b'XLIB', b'XLRT', b'XOWN', b'XEZN', b'XMBR', b'XPWR', b'XATR', b'INAM', b'XLRL', b'XAPR', 
                       b'XTEL', b'XNDP', b'XESP', b'XLTW', b'XTNM', b'XCZC', b'XCZR', b'XSPC', b'XLCN']
        special_refr_fields = [b'PDTO', b'XLOC', b'XLKR', b'XPOD', b'VMAD', b'XORD']

        refr_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in refr_fields and field_size >= 4:
                refr_offsets.append(offset + 6)
            elif field in special_refr_fields:
                if field == b'PDTO' or field == b'XLOC':
                    refr_offsets.append(offset + 10)
                elif field == b'XLKR' or field == b'XPOD':
                    refr_offsets.append(offset + 6)
                    refr_offsets.append(offset + 10)
                elif field == b'VMAD':
                    refr_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'XORD':
                    refr_offsets.append(offset + 6)
                    refr_offsets.append(offset + 10)
                    refr_offsets.append(offset + 14)
                    refr_offsets.append(offset + 18)
            offset += field_size + 6

        return [i, bytearray(form), refr_offsets]

    def save_regn_data(i, form): 
        regn_fields = [b'WNAM', b'RDMO', b'RDGS', b'RDOT']
        special_regn_fields = [b'RDSA', b'RDWT']

        regn_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in regn_fields and field_size >= 4:
                regn_offsets.append(offset + 6)
            elif field in special_regn_fields:
                if field == b'RDSA':
                    regn_offsets.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=12))
                elif field == b'RDWT':
                    struct_count = field_size // 12
                    in_field_offset = offset + 6
                    for _ in range(struct_count):
                        regn_offsets.append(in_field_offset)
                        regn_offsets.append(in_field_offset+8)
                        in_field_offset += 12
                
            offset += field_size + 6

        return [i, bytearray(form), regn_offsets]

    def save_rela_data(i, form): 
        special_rela_fields = [b'DATA']

        rela_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_rela_fields:
                if field == b'DATA':
                    data_offset = offset + 6
                    rela_offsets.append(data_offset)
                    rela_offsets.append(data_offset+ 4)
                    rela_offsets.append(data_offset+ 12)
            offset += field_size + 6

        return [i, bytearray(form), rela_offsets]

    def save_rfct_data(i, form): 
        special_rfct_fields = [b'DATA']

        rfct_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_rfct_fields:
                if field == b'DATA':
                    rfct_offsets.append(offset + 6)
                    rfct_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), rfct_offsets]
    
    def save_scen_data(i, form): 
        scen_fields = [b'PNAM', b'DATA']
        special_scen_fields = [b'VMAD', b'CTDA']

        scen_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in scen_fields and field_size >= 4:
                scen_offsets.append(offset + 6)
            elif field in special_scen_fields:
                if field == b'VMAD':
                    scen_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'CTDA':
                    scen_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), scen_offsets]

    def save_scrl_data(i, form): 
        scrl_fields = [b'MDOB', b'ETYP', b'YNAM', b'ZNAM', b'EFID']
        special_scrl_fields = [b'CTDA', b'KWDA', b'SPIT', b'DSTD', b'DMDS', b'MODS']

        scrl_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in scrl_fields and field_size >= 4:
                scrl_offsets.append(offset + 6)
            elif field in special_scrl_fields:
                if field == b'CTDA':
                    scrl_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'KWDA':
                    scrl_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'SPIT':
                    scrl_offsets.append(offset+38) #Half-cost Perk
                elif field == b'DSTD':
                    scrl_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    scrl_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    scrl_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == B'MODS':
                    scrl_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), scrl_offsets]

    def save_shou_data(i, form): 
        shou_fields = [b'MDOB']
        special_shou_fields = [b'SNAM']

        shou_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in shou_fields and field_size >= 4:
                shou_offsets.append(offset + 6)
            elif field in special_shou_fields:
                if field == b'SNAM':
                    shou_offsets.append(offset + 6)
                    shou_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), shou_offsets]

    def save_slgm_data(i, form): 
        slgm_fields = [b'NAM0', b'ZNAM', b'YNAM']
        special_slgm_fields = [b'KWDA', b'MODS', b'DSTD', b'DMDS']

        slgm_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in slgm_fields and field_size >= 4:
                slgm_offsets.append(offset + 6)
            elif field in special_slgm_fields:
                if field == b'KWDA':
                    slgm_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'MODS':
                    slgm_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    slgm_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    slgm_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    slgm_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), slgm_offsets]

    def save_smbn_data(i, form): 
        smbn_fields = [b'PNAM', b'SNAM']
        special_smbn_fields = [b'CTDA']

        smbn_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in smbn_fields and field_size >= 4:
                smbn_offsets.append(offset + 6)
            elif field in special_smbn_fields:
                if field == b'CTDA':
                    smbn_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), smbn_offsets]

    def save_smen_data(i, form): 
        smen_fields = [b'PNAM', b'SNAM']
        special_smen_fields = [b'CTDA']

        smen_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in smen_fields and field_size >= 4:
                smen_offsets.append(offset + 6)
            elif field in special_smen_fields:
                if field == b'CTDA':
                    smen_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), smen_offsets]

    def save_smqn_data(i, form): 
        smqn_fields = [b'PNAM', b'SNAM', b'NNAM']
        special_smqn_fields = [b'CTDA']

        smqn_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in smqn_fields and field_size >= 4:
                smqn_offsets.append(offset + 6)
            elif field in special_smqn_fields:
                if field == b'CTDA':
                    smqn_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), smqn_offsets]

    def save_snct_data(i, form): 
        snct_fields = [b'PNAM']

        snct_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in snct_fields and field_size >= 4:
                snct_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), snct_offsets]

    def save_sndr_data(i, form): 
        sndr_fields = [b'GNAM', b'SNAM', b'ONAM']
        special_sndr_fields = [b'CTDA']

        sndr_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in sndr_fields and field_size >= 4:
                sndr_offsets.append(offset + 6)
            elif field in special_sndr_fields:
                if field == b'CTDA':
                    sndr_offsets.extend(form_processor.ctda_reader(form, offset))
            offset += field_size + 6

        return [i, bytearray(form), sndr_offsets]

    def save_soun_data(i, form): 
        soun_fields = [b'SDSC']

        soun_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in soun_fields and field_size >= 4:
                soun_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), soun_offsets]

    def save_spel_data(i, form): 
        spel_fields = [b'MDOB', b'ETYP', b'EFID']
        special_spel_fields = [b'CTDA', b'SPIT', b'KWDA']

        spel_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in spel_fields and field_size >= 4:
                spel_offsets.append(offset + 6)
            elif field in special_spel_fields:
                if field == b'CTDA':
                    spel_offsets.extend(form_processor.ctda_reader(form, offset))
                elif field == b'SPIT':
                    spel_offsets.append(offset + 38)
                elif field == b'KWDA':
                    spel_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6

        return [i, bytearray(form), spel_offsets]

    def save_stat_data(i, form):
        special_stat_fields = [b'DNAM', b'MODS']

        stat_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_stat_fields:
                if field == b'DNAM':
                    stat_offsets.append(offset+10)
                elif field == b'MODS':
                    stat_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), stat_offsets]

    def save_tact_data(i, form): 
        tact_fields = [b'SNAM', b'VNAM']
        special_tact_fields = [b'VMAD', b'MODS', b'KWDA', b'DSTD', b'DMDS']

        tact_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in tact_fields and field_size >= 4:
                tact_offsets.append(offset + 6)
            elif field in special_tact_fields:
                if field == b'VMAD':
                    tact_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'MODS':
                    tact_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'KWDA':
                    tact_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'DSTD':
                    tact_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    tact_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    tact_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), tact_offsets]
    
    def save_tes4_data(i, form): 
        special_tes4_fields = [b'ONAM']

        tes4_offsets = []
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_tes4_fields:
                if field == b'ONAM':
                    tes4_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6

        return [i, bytearray(form), tes4_offsets]

    def save_tree_data(i, form):
        tree_fields = [b'PFIG', b'SNAM']
        special_tree_fields = [b'MODS']

        tree_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in tree_fields and field_size >= 4:
                tree_offsets.append(offset + 6)
            elif field in special_tree_fields:
                if field == b'MODS':
                    tree_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), tree_offsets]

    def save_watr_data(i, form): 
        watr_fields = [b'XNAM', b'SNAM', b'INAM', b'TNAM']

        watr_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in watr_fields and field_size >= 4:
                watr_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), watr_offsets]

    def save_weap_data(i, form): 
        weap_fields = [b'BAMT', b'BIDS', b'CNAM', b'EITM', b'ETYP', b'INAM', b'NAM7', b'NAM8', b'NAM9', b'SNAM', b'TNAM', b'UNAM', b'WNAM', b'XNAM', b'YNAM', b'ZNAM']
        special_weap_fields = [b'CRDT', b'KWDA' , b'MODS', b'MO3S', b'VMAD', b'DSTD', b'DMDS']

        weap_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in weap_fields and field_size >= 4:
                weap_offsets.append(offset + 6)
            elif field in special_weap_fields:
                if field == b'KWDA':
                    weap_offsets.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field in (b'MODS', b'MO3S'):
                    weap_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
                elif field == b'VMAD':
                    weap_offsets.extend(form_processor.vmad_reader(form, offset))
                elif field == b'CRDT':
                    if field_size == 16:    # LE
                        weap_offsets.append(offset+ 18) # Critical Spell Effect SPEL 6 + 12
                    elif field_size == 24:  # SSE
                        weap_offsets.append(offset+ 22) # Critical Spell Effect SPEL 6 + 16
                elif field == b'DSTD':
                    weap_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    weap_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    weap_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), weap_offsets]

    def save_wrld_data(i, form): 
        wrld_fields = [b'LTMP', b'XEZN', b'XLCN', b'CNAM', b'NAM2', b'NAM3', b'WNAM', b'PNAM', b'ZNAM']
        special_wrld_fields = [b'RNAM', b'MODS']

        wrld_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in wrld_fields and field_size >= 4:
                wrld_offsets.append(offset + 6)
            elif field in special_wrld_fields:
                if field == b'RNAM':
                    in_field_offset = offset + 10
                    pair_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4
                    for _ in range(pair_count):
                        wrld_offsets.append(in_field_offset)
                        in_field_offset += 8
                elif field == b'MODS':
                    wrld_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), wrld_offsets]

    def save_wthr_data(i, form): 
        wthr_fields = [b'MNAM', b'NNAM', b'TNAM', b'SNAM', b'GNAM']
        special_wthr_fields = [b'IMSP', b'HNAM', b'MODS']

        wthr_offsets = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in wthr_fields and field_size >= 4:
                wthr_offsets.append(offset + 6)
            elif field in special_wthr_fields:
                if field in (b'IMSP', b'HNAM'):
                    wthr_offsets.append(offset + 6)
                    wthr_offsets.append(offset + 10)
                    wthr_offsets.append(offset + 14)
                    wthr_offsets.append(offset + 18)
                elif field == b'MODS':
                    wthr_offsets.extend(form_processor.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), wthr_offsets]

    #Template for each type of form
    def save_FORM_data(i, form): 
        FORM_fields = [b'']
        special_FORM_fields = [b'']

        FORM_offsets = [12]
        offset = 24
        while offset < len(form):
            #field = form[offset:offset+4]
            #field_size = struct.unpack("<H", form[offset+4:offset+6])[0]
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in FORM_fields and field_size >= 4:
                FORM_offsets.append(offset + 6)
            elif field in special_FORM_fields:
                pass
            offset += field_size + 6

        return [i, bytearray(form), FORM_offsets]
                    
    def ctda_reader(form, offset):
        offsets = []
        offset += 6
        op_flag_byte = form[offset]
        flags = op_flag_byte & 0x1F  # Mask out the upper 3 bits, keeping only the lower 5 bits
        use_global_flag = (flags & 0x04) != 0
        offset += 4
        #If lower 5 bit 0x04 is set then use global and comparison value is a formid
        if use_global_flag: 
            offsets.append(offset)  # ComparisonValue
        offset += 4
        function_index = struct.unpack("<H", form[offset:offset+2])[0]
        offset += 4
        #GetEventData is 4672 - 4096 = 576
        if function_index == 576:
            offsets.append(offset+ 4)   # param3
        else:
            offsets.append(offset)      # param1
            offsets.append(offset+ 4)   # param2
        offset += 8
        offsets.append(offset+ 4)       # Function Reference
        return offsets

    def script_reader(form, offset, obj_format):
        offsets = []
        script_name_size = struct.unpack("<H", form[offset:offset+2])[0]
        #script_name = form[offset+2:offset+script_name_size+2]
        offset += script_name_size + 2
        property_count = struct.unpack("<H", form[offset+1:offset+3])[0]
        offset += 3
        for _ in range(property_count):
            property_name_size = struct.unpack("<H", form[offset:offset+2])[0]
            #property_name = form[offset+2: offset +property_name_size + 2]
            offset += property_name_size + 2
            property_type = int.from_bytes(form[offset:offset+1][::-1])
            offset += 2
            if property_type == 1:
                if obj_format == 1:
                    offsets.append(offset)
                elif obj_format == 2:
                    offsets.append(offset+4)
                offset += 8
            elif property_type == 2:
                string_size = struct.unpack("<H", form[offset:offset+2])[0]
                offset += string_size + 2
            elif property_type == 3:
                offset += 4
            elif property_type == 4:
                offset += 4
            elif property_type == 5:
                offset += 1
            elif property_type == 11:
                item_count = struct.unpack("<I", form[offset:offset+4])[0]
                offset += 4
                if obj_format == 1:
                    for _ in range(item_count):
                        offsets.append(offset)
                        offset += 8
                else:
                    for _ in range(item_count):
                        offsets.append(offset+4)
                        offset += 8
            elif property_type == 12:
                item_count = struct.unpack("<I", form[offset:offset+4])[0]
                offset += 4
                for _ in range(item_count):
                    string_size = struct.unpack("<H", form[offset:offset+2])[0]
                    offset += string_size + 2
            elif property_type == 13:
                item_count = struct.unpack("<I", form[offset:offset+4])[0]
                offset += 4
                offset += 4 * item_count
            elif property_type == 14:
                item_count = struct.unpack("<I", form[offset:offset+4])[0]
                offset += 4
                offset += 4 * item_count
            elif property_type == 15:
                item_count = struct.unpack("<I", form[offset:offset+4])[0]
                offset += 4
                offset += item_count
        return offsets, offset
    
    def vmad_reader(form, offset):
        offsets = []
        vmad_size = struct.unpack("<H", form[offset+4:offset+6])[0]
        vmad_end_offset = offset + 6 + vmad_size
        obj_format = struct.unpack("<H", form[offset+8:offset+10])[0]
        script_count = struct.unpack("<H", form[offset+10:offset+12])[0]
        offset += 12
        for _ in range(script_count):
            script_offsets, offset = form_processor.script_reader(form, offset, obj_format)
            offsets.extend(script_offsets)

        if form[:4] in (b'INFO', b'PACK', b'PERK', b'QUST', b'SCEN') and offset < vmad_end_offset:
            if form[:4] == b'QUST':
                offset += 1
                fragment_count = struct.unpack("<H", form[offset:offset+2])[0]
                offset += 2
                script_file_name_size = struct.unpack("<H", form[offset:offset+2])[0]
                #script_file_name = form[offset+2:offset+script_file_name_size+2]
                offset += 2 + script_file_name_size

                #Iterate through fragments
                for _ in range(fragment_count):
                    offset += 9
                    fragment_script_name_size = struct.unpack("<H", form[offset:offset+2])[0]
                    offset += fragment_script_name_size  + 2
                    fragment_function_name_size = struct.unpack("<H", form[offset:offset+2])[0]
                    offset += fragment_function_name_size + 2

                alias_count = struct.unpack("<H", form[offset:offset+2])[0]
                offset += 2
                #Iterate through aliases
                for _ in range(alias_count):
                    if obj_format == 1:
                        offsets.append(offset)
                    elif obj_format == 2:
                        offsets.append(offset+4)
                    offset += 12
                    alias_script_count = struct.unpack("<H", form[offset:offset+2])[0]
                    offset += 2
                    for _ in range(alias_script_count):
                        alias_script_offsets, offset = form_processor.script_reader(form, offset, obj_format)
                        offsets.extend(alias_script_offsets)
        
        return offsets