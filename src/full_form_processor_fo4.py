import struct
from log_stream import write_error

class form_processor():
    
    def get_offsets_from_array(offset: int, field_size: int, struct_size=4):
        start = offset + 6
        return list(range(start, start + field_size, struct_size))

    #TODO: REMOVE
    def printFIDs(offsets_list, form):
        print(str(form[:4]) + ':')
        for offset in offsets_list:
            if not offset == 12:
                print(form[offset:offset+4][::-1].hex())
    
    def get_dstd_offsets(offset) -> list[int]:
        # ExplosionID 6 + 4 + 4
        # DebrisID    6 + 4 + 4 + 4
        return [offset+14, offset+18]
    
    def get_snam_marker_offsets(field_size, offset):
        start = offset + 22 # Keyword 6 + 16 and struct size is 24
        return list(range(start, start + field_size, 24))

    def get_field_and_size(offset, form)-> tuple[bytes, int, int]:
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
            for i, form, offsets_list in forms:
                for offset in offsets_list:
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
            for i, form, offsets_list in forms:
                for offset in offsets_list:
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
            for i, form, offsets_list in forms:
                for offset in offsets_list:
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
            for i, form, offsets_list in forms:
                for offset in offsets_list:
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
            b'AECH',
            b'AMDL',
            b'AORU',
            b'ASTP',
            b'AVIF',
            b'CSTY',
            b'DEBR',
            b'EYES',
            b'GDRY',
            b'GMST',
            b'GLOB',
            b'IMAD',
            b'IMGS',
            b'LCRT',
            b'LENS',
            b'MOVT',
            b'MSWP',
            b'NOCM',
            b'REVB',
            b'SPGD',
            b'TRNS',
            b'TXST',
            b'VTYP'
        }
        # Records with shared handler
        placed_records = {
           b'PARW', b'PBAR', b'PBEA', b'PCON', b'PFLA', b'PGRE', b'PHZD', b'PMIS'
        }
        
        record_handlers = {
            b'AACT': form_processor.save_aact_data,
            b'ACHR': form_processor.save_achr_data,
            b'ACTI': form_processor.save_acti_data,
            b'ADDN': form_processor.save_addn_data,
            b'ALCH': form_processor.save_alch_data,
            b'AMMO': form_processor.save_ammo_data,
            b'ANIO': form_processor.save_anio_data,
            b'ARMA': form_processor.save_arma_data,
            b'ARMO': form_processor.save_armo_data,
            b'ARTO': form_processor.save_arto_data,
            b'ASPC': form_processor.save_aspc_data,
            b'BNDS': form_processor.save_bnds_data,
            b'BOOK': form_processor.save_book_data,
            b'CAMS': form_processor.save_cams_data,
            b'CELL': form_processor.save_cell_data,
            b'CLAS': form_processor.save_clas_data,
            b'CLFM': form_processor.save_clfm_data,
            b'CLMT': form_processor.save_clmt_data,
            b'CMPO': form_processor.save_cmpo_data,
            b'COBJ': form_processor.save_cobj_data,
            b'COLL': form_processor.save_coll_data,
            b'CONT': form_processor.save_cont_data,
            b'CPTH': form_processor.save_cpth_data,
            b'DFOB': form_processor.save_dfob_data,
            b'DIAL': form_processor.save_dial_data,
            b'DLBR': form_processor.save_dlbr_data,
            b'DLVW': form_processor.save_dlvw_data,
            b'DMGT': form_processor.save_dmgt_data,
            b'DOBJ': form_processor.save_dobj_data,
            b'DOOR': form_processor.save_door_data,
            b'DUAL': form_processor.save_dual_data,
            b'ECZN': form_processor.save_eczn_data,
            b'EFSH': form_processor.save_efsh_data,
            b'ENCH': form_processor.save_ench_data,
            b'EQUP': form_processor.save_equp_data,
            b'FACT': form_processor.save_fact_data,
            b'FLOR': form_processor.save_flor_data,
            b'FLST': form_processor.save_flst_data,
            b'FSTP': form_processor.save_fstp_data,
            b'FSTS': form_processor.save_fsts_data,
            b'FURN': form_processor.save_furn_data,
            b'GRAS': form_processor.save_gras_data,
            b'GRUP': form_processor.save_grup_data,
            b'HAZD': form_processor.save_hazd_data,
            b'HDPT': form_processor.save_hdpt_data,
            b'IDLE': form_processor.save_idle_data,
            b'IDLM': form_processor.save_idlm_data,
            b'INFO': form_processor.save_info_data,
            b'INGR': form_processor.save_ingr_data,
            b'INNR': form_processor.save_innr_data,
            b'IPCT': form_processor.save_ipct_data,
            b'IPDS': form_processor.save_ipds_data,
            b'KEYM': form_processor.save_keym_data,
            b'KSSM': form_processor.save_kssm_data,
            b'KYWD': form_processor.save_kywd_data,
            b'LAYR': form_processor.save_layr_data,
            b'LCTN': form_processor.save_lctn_data,
            b'LGTM': form_processor.save_lgtm_data,
            b'LIGH': form_processor.save_ligh_data,
            b'LSCR': form_processor.save_lscr_data,
            b'LTEX': form_processor.save_ltex_data,
            b'LVLI': form_processor.save_lvli_data,
            b'LVLN': form_processor.save_lvln_data,
            b'LVSP': form_processor.save_lvsp_data,
            b'MATO': form_processor.save_mato_data,
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
            b'OMOD': form_processor.save_omod_data,
            b'OTFT': form_processor.save_otft_data,
            b'OVIS': form_processor.save_ovis_data,
            b'PACK': form_processor.save_pack_data,
            b'PERK': form_processor.save_perk_data,
            b'PKIN': form_processor.save_pkin_data,
            b'PLYR': form_processor.save_plyr_data,
            b'PROJ': form_processor.save_proj_data,
            b'QUST': form_processor.save_qust_data,
            b'RACE': form_processor.save_race_data,
            b'REFR': form_processor.save_refr_data,
            b'REGN': form_processor.save_regn_data,
            b'RELA': form_processor.save_rela_data,
            b'RFCT': form_processor.save_rfct_data,
            b'RFGP': form_processor.save_rfgp_data,
            b'SCCO': form_processor.save_scco_data,
            b'SCEN': form_processor.save_scen_data,
            b'SCOL': form_processor.save_scol_data,
            b'SCSN': form_processor.save_scsn_data,
            b'SMBN': form_processor.save_smbn_data,
            b'SMEN': form_processor.save_smen_data,
            b'SMQN': form_processor.save_smqn_data,
            b'SNCT': form_processor.save_snct_data,
            b'SNDR': form_processor.save_sndr_data,
            b'SOPM': form_processor.save_sopm_data,
            b'SOUN': form_processor.save_soun_data,
            b'SPEL': form_processor.save_spel_data,
            b'STAG': form_processor.save_stag_data,
            b'STAT': form_processor.save_stat_data,
            b'TACT': form_processor.save_tact_data,
            b'TERM': form_processor.save_term_data,
            b'TES4': form_processor.save_tes4_data,
            b'TREE': form_processor.save_tree_data,
            b'WATR': form_processor.save_watr_data,
            b'WEAP': form_processor.save_weap_data,
            b'WRLD': form_processor.save_wrld_data,
            b'WTHR': form_processor.save_wthr_data,
            b'ZOOM': form_processor.save_zoom_data
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
                write_error(f'Missing form processing for record type: {record_type}')

        return saved_forms

    def save_aact_data(i, form):
        form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_achr_data(i, form):
        form_fields = {b'NAME', b'XATR', b'XEMI', b'XEZN', b'XLCN', b'XLRL', b'XLTW', b'XLYR', b'XMBR', b'XMSP', b'XRFG', b'XLRT', b'TNAM'
                       b'INAM', b'XPWR', b'XAPR', b'XPLK', b'XESP', b'XOWN'} #XPWR, XAPR, XPLK, XESP, XOWN start with FID only
        special_form_fields = {b'PDTO', b'VMAD', b'XLKR', b'XLOC'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'PDTO':
                    if form[offset+6:offset+7] == b'\x00':
                        offsets_list.append(offset + 10)
                elif field == b'XLOC':
                    offsets_list.append(offset + 10) # 6: Level, 10: Key
                elif field == b'XLKR':
                    offsets_list.append(offset + 6)
                    offsets_list.append(offset + 10)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_acti_data(i, form):
        form_fields = {b'PTRN', b'STCP', b'NTRM', b'FTYP', b'SNAM', b'VNAM', b'WNAM', b'KNAM', b'MODS', b'DMDS', b'RADR'}
        special_form_fields = {b'KWDA', b'PRPS', b'VMAD', b'DAMC', b'DSTD', b'CTDA', b'NVNM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field in (b'DAMC', b'PRPS'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                elif field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'NVNM':
                    offsets_list.extend(form_processor.nvnm_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_addn_data(i, form):
        form_fields = {b'LNAM', b'SNAM', b'MODS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_alch_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'YNAM', b'ETYP', b'CUSD', b'DESC', b'EFID'}
        special_form_fields = {b'KWDA', b'DAMC', b'DSTD', b'ENIT', b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'ENIT':
                    offsets_list.append(offset+14)  # Addiction 6 + 4 + 4
                    offsets_list.append(offset+22)  # Sound     6 + 4 + 4 + 4 + 4
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_ammo_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'YNAM', b'ZNAM', b'DNAM'}
        special_form_fields = {b'DAMC', b'DSTD', b'KWDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_anio_data(i, form):
        form_fields = {b'MODS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_arma_data(i, form):
        form_fields = {b'RNAM', b'MO2S', b'MO3S', b'MO4S', b'MO5S', b'NAM0', b'NAM1', b'NAM2', b'NAM3', b'MODL', b'SNDD', b'ONAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_armo_data(i, form):
        form_fields = {b'PTRN', b'EITM', b'MO2S', b'MO4S', b'DMDS', b'YNAM', b'ZNAM', b'ETYP', b'BIDS', b'BAMT', b'RNAM', b'INRD', b'MODL', b'TNAM'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'KWDA', b'DAMA', b'APPR', b'OBTS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field in (b'DAMC', b'DAMA'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA' or field == b'APPR':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'OBTS':
                    offsets_list.extend(form_processor.obts_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_arto_data(i, form):
        form_fields = {b'PTRN', b'MODS'}
        special_form_fields = {b'KWDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_aspc_data(i, form):
        form_fields = {b'SNAM', b'RDAT', b'BNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_bnds_data(i, form):
        form_fields = {b'TNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_book_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'YNAM', b'ZNAM', b'FIMD', b'INAM'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'KWDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                    
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_cams_data(i, form):
        form_fields = {b'MODS', b'MNAM'}
        special_form_fields = {b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_cell_data(i, form):
        form_fields = {b'RVIS', b'LTMP', b'XLCN', b'XCWT', b'XOWN', b'XILL', b'XILW', b'XCCM', b'XCAS', b'XEZN', b'XCMO', b'XCIM', b'XGDR'}
        special_form_fields = {b'XCLR', b'XPRI', b'XCRI'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'XCLR' or field == b'XPRI':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'XCRI':
                    inner_offset = offset + 6
                    mesh_count = struct.unpack("<I", form[inner_offset:inner_offset+4])[0]
                    inner_offset += 4
                    ref_count = struct.unpack("<I", form[inner_offset:inner_offset+4])[0]
                    inner_offset += 4
                    inner_offset += 4 * mesh_count
                    for _ in range(ref_count):
                        offsets_list.append(inner_offset)
                        inner_offset += 8
                else:
                    print(f"special field without method: {field}")
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_clas_data(i, form):
        special_form_fields = {b'PRPS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'PRPS':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_clfm_data(i, form):
        special_form_fields = {b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_clmt_data(i, form):
        form_fields = {b'MODS'}
        special_form_fields = {b'WLST'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'WLST':
                    wtyp_count = field_size // 12
                    inner_offset = offset + 6
                    for _ in range(wtyp_count):
                        offsets_list.append(inner_offset)       # Weather
                        offsets_list.append(inner_offset + 8)   # Global 4 + 4
                        inner_offset += 12

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_cmpo_data(i, form):
        form_fields = {b'CUSD', b'MNAM', b'GNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_cobj_data(i, form):
        form_fields = {b'YNAM', b'ZNAM', b'CNAM', b'BNAM', b'ANAM'}
        special_form_fields = {b'FVPA', b'CTDA', b'FNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'FVPA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                elif field == b'FNAM':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_coll_data(i, form):
        special_form_fields = {b'CNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'CNAM':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_cont_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'CNTO', b'COED', b'DMDS', b'FTYP', b'NTRM',b'SNAM', b'QNAM', b'TNAM', b'ONAM'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'KWDA', b'PRPS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field in (b'DAMC', b'PRPS'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_cpth_data(i, form):
        form_fields = {b'SNAM'}
        special_form_fields = {b'ANAM', b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'ANAM':
                    offsets_list.append(offset + 6)  # Parent    6
                    offsets_list.append(offset + 10) # Previous  6 + 4
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_dfob_data(i, form):
        form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
        
    def save_dial_data(i, form):
        form_fields = {b'BNAM', b'QNAM', b'KNAM'}
        special_form_fields = {b'INOM', b'INOA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_dlbr_data(i, form):
        form_fields = {b'QNAM', b'SNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_dlvw_data(i, form):
        form_fields = {b'QNAM', b'BNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_dmgt_data(i, form):
        special_form_fields = {b'DNAM'}
        form_version = struct.unpack("<H", form[20:22])[0]

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                #Before version 78 it was AVIF index which I can ignore
                if field == b'DNAM' and form_version >= 78:
                    dmgts_count = field_size // 8
                    inner_offset = offset + 6
                    for _ in range(dmgts_count):
                        offsets_list.append(inner_offset)   # Actor Value
                        offsets_list.append(inner_offset+4)  # Spell
                        inner_offset += 8

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_dobj_data(i, form):
        special_form_fields = {b'DNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'DNAM':
                    start = offset + 10
                    offsets_list.extend(range(start, start + field_size, 8))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_door_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'NTRM', b'SNAM', b'ANAM', b'BNAM', b'TNAM'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'KWDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA':
                   offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_dual_data(i, form):
        special_form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'DATA':
                    offsets_list.append(offset+6)   # Projectile        6
                    offsets_list.append(offset+10)  # Explosion         6 + 4
                    offsets_list.append(offset+14)  # Effect Shader     6 + 4 + 4
                    offsets_list.append(offset+18)  # Hit Effect Art    6 + 4 + 4 + 4
                    offsets_list.append(offset+22)  # Impact Data Set   6 + 4 + 4 + 4 + 4

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_eczn_data(i, form):
        special_form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'DATA':
                    offsets_list.append(offset+6)   # Owner     6
                    offsets_list.append(offset+10)  # Location  6 + 4

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_efsh_data(i, form):
        form_fields = {b'MODS'}
        special_form_fields = {b'DNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset+6)
            elif field in special_form_fields:
                if field == b'DNAM':
                    form_version = struct.unpack("<H", form[20:22])[0]
                    if form_version >= 106: # new format
                        offsets_list.append(offset + 114) # ambient sound   6 + (27 * 4 = 108)
                    else:                   # old format
                        offsets_list.append(offset + 247) # addon models    6 + (60 * 4 = 240, + 1)
                        offsets_list.append(offset + 311) # ambient sound   6 + (76*4 = 304, + 1)
                        
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_ench_data(i, form):
        form_fields = {b'EFID'}
        special_form_fields = {b'ENIT', b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'ENIT':
                    offsets_list.append(offset + 34)    # Base Enchantment  6 + (4*7 = 28)
                    offsets_list.append(offset + 38)    # Worn Restrictions 6 + (4*8 = 32)
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_equp_data(i, form):
        form_fields = {b'ANAM'}
        special_form_fields = {b'PNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'PNAM':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_expl_data(i, form):
        form_fields = {b'MODS', b'EITM', b'MNAM'}
        special_form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'DATA':
                    offsets_list.append(offset + 6)     # Light             6
                    offsets_list.append(offset + 10)    # Sound 1           6 + 4
                    offsets_list.append(offset + 14)    # Sound 2           6 + 4 + 4
                    offsets_list.append(offset + 18)    # Impact Data Set   6 + 4 + 4 + 4
                    offsets_list.append(offset + 22)    # Placed Object     6 + 4 + 4 + 4 + 4
                    offsets_list.append(offset + 26)    # Spawn Projectile  6 + 4 + 4 + 4 + 4 + 4

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_fact_data(i, form):
        form_fields = {b'XNAM', b'JAIL', b'WAIT', b'STOL', b'PLCN', b'CRGR', b'JOUT', b'VEND', b'VENC'}
        special_form_fields = {b'PLVD', b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'PLVD':
                    loc_type = struct.unpack("<I", form[offset+6:offset+10])[0]
                    if loc_type in (1, 4, 6):   # Cell, Object ID, Keyword
                        offsets_list.append(offset + 6 + 4) 
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_flor_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'PFIG', b'SNAM'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'KWDA', b'PRPS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field in (b'DAMC', b'PRPS'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_flst_data(i, form):
        form_fields = {b'LNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_fstp_data(i, form):
        form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_fsts_data(i, form):
        special_form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'DATA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_furn_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'CNTO', b'COED' b'NAM1'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'CTDA', b'SNAM', b'APPR', b'OBTS', b'NVNM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                elif field == b'SNAM':
                    offsets_list.extend(form_processor.get_snam_marker_offsets(field_size, offset))
                elif field == b'APPR':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'OBTS':
                    offsets_list.extend(form_processor.obts_reader(form, offset))
                elif field == b'NVNM':
                    offsets_list.extend(form_processor.nvnm_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_gras_data(i, form):
        form_fields = {b'MODS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_grup_data(i, form): 
        grup_type = struct.unpack("<I", form[12:16])[0]
        if grup_type in (1, 6, 7, 8, 9):
            offsets_list = [8]
        else:
            offsets_list = []
        return [i, bytearray(form), offsets_list]

    def save_hazd_data(i, form):
        form_fields = {b'MNAM', b'MODS'}
        special_form_fields = {b'DNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'DNAM':
                    offsets_list.append(offset + 30)    # Effect            6 + (4*6 = 24)
                    offsets_list.append(offset + 36)    # Light             6 + 24 + 4
                    offsets_list.append(offset + 38)    # Impact Data Set   6 + 24 + 4 + 4
                    offsets_list.append(offset + 42)    # Sound             6 + 24 + 4 + 4 + 4

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_hdpt_data(i, form):
        form_fields = {b'MODS', b'HNAM', b'TNAM', b'CNAM', b'RNAM'}
        special_form_fields = {b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_idle_data(i, form):
        special_form_fields = {b'ANAM', b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'ANAM':
                    offsets_list.append(offset+6)
                    offsets_list.append(offset+10)
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_idlm_data(i, form):
        form_fields = {b'MODS', b'PNAM', b'QNAM'}
        special_form_fields = {b'KWDA', b'IDLA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'KWDA' or field == b'IDLA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_info_data(i, form):
        form_fields = {b'TPIC', b'PNAM', b'DNAM', b'GNAM', b'SNAM', b'LNAM', b'SRAF' b'ANAM', b'TSCE', b'ONAM', b'MODQ'}
        special_form_fields = {b'VMAD', b'TRDA', b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'TRDA':
                    offsets_list.append(offset + 6)
                    offsets_list.append(offset + 11)
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_ingr_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'ETYP', b'YNAM', b'ZNAM', b'EFID'}
        special_form_fields = {b'VMAD', b'KWDA', b'DAMC', b'DSTD', b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_innr_data(i, form):
        special_form_fields = {b'KWDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_ipct_data(i, form):
        form_fields = {b'MODS', b'DNAM', b'ENAM', b'SNAM', b'NAM1', b'NAM3', b'NAM2'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_ipds_data(i, form):
        special_form_fields = {b'PNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'PNAM':
                    offsets_list.append(offset+6)
                    offsets_list.append(offset+10)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_keym_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'YNAM', b'ZNAM'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'KWDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_kssm_data(i, form):
        form_fields = {b'DNAM', b'ENAM', b'VNAM', b'KNAM'}
        special_form_fields = {b'RNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'RNAM':
                    offsets_list.append(offset+10)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_kywd_data(i, form):
        form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_layr_data(i, form):
        form_fields = {b'PNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_lctn_data(i, form):
        form_fields = {b'ACEC', b'LCEC', b'RCEC', b'PNAM', b'NAM1', b'FNAM', b'MNAM'}
        special_form_fields = {b'ACPR', b'LCPR', b'RCPR', b'ACUN', b'LCUN', b'RCUN', b'ACSR', b'LCSR', b'RCSR', b'ACID', b'LCID', b'ACEP', b'LCEP', b'KWDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field in (b'RCPR', b'RCUN', b'RCSR', b'ACID', b'LCID', b'KWDA'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field in (b'ACPR', b'LCPR', b'ACEP', b'LCEP'):
                    ref_count = field_size // 12
                    inner_offset = offset + 6
                    for _ in range(ref_count):
                        offsets_list.append(inner_offset)    # Ref          | Ref
                        offsets_list.append(inner_offset+4)  # World/Cell   | Enable Parent
                        inner_offset += 12
                elif field in (b'ACUN', b'LCUN'):
                    ref_count = field_size // 12
                    inner_offset = offset + 6
                    for _ in range(ref_count):
                        offsets_list.append(inner_offset)    # NPC
                        offsets_list.append(inner_offset+4)  # Actor Ref
                        offsets_list.append(inner_offset+8)  # Location
                        inner_offset += 12
                elif field in (b'ACSR', b'LCSR'):
                    ref_count = field_size // 16
                    inner_offset = offset + 6
                    for _ in range(ref_count):
                        offsets_list.append(inner_offset)    # Loc Ref Type
                        offsets_list.append(inner_offset+4)  # Ref
                        offsets_list.append(inner_offset+8)  # World/Cell
                        inner_offset += 16

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_lgtm_data(i, form):
        form_fields = {b'WGDR'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_ligh_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'SNAM', b'LNAM', b'WGDR'}
        special_form_fields = {b'VMAD', b'KWDA', b'DAMC', b'DSTD', b'PRPS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field in (b'DAMC', b'PRPS'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_lscr_data(i, form):
        form_fields = {b'NNAM', b'TNAM'}
        special_form_fields = {b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_ltex_data(i, form):
        form_fields = {b'GNAM', b'TNAM', b'MNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_lvli_data(i, form):
        form_fields = {b'LVLG', b'LVSG', b'COED'}
        special_form_fields = {b'LVLO', b'LLKC'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'LVLO':
                    offsets_list.append(offset + 10) # ObjectName 6 + 4
                elif field == b'LLKC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                    
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_lvln_data(i, form):
        form_fields = {b'LVLG', b'MODS', b'COED'}
        special_form_fields = {b'LVLO', b'LLKC'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'LVLO':
                    offsets_list.append(offset + 10) # ObjectName 6 + 4
                elif field == b'LLKC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_lvsp_data(i, form):
        special_form_fields = {b'LVLO'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'LVLO':
                    offsets_list.append(offset + 10) # ObjectName 6 + 4
                    
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_mato_data(i, form):
        form_fields = {b'MODS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_matt_data(i, form):
        form_fields = {b'PNAM', b'HNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_mesg_data(i, form):
        form_fields = {b'INAM', b'QNAM'}
        special_form_fields = {b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_mgef_data(i, form):
        form_fields = {b'ESCE'}
        special_form_fields = {b'VMAD', b'KWDA', b'DATA', b'SNDD', b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'DATA':
                    offsets_list.append(offset+14)      # Associated Item   6 + 4 + 4
                    offsets_list.append(offset+22)      # Resist Value      14 + 4 + 4
                    offsets_list.append(offset+30)      # Casting Light     22 + 4 + 4
                    offsets_list.append(offset+38)      # Hit Shader        30 + 4 + 4
                    offsets_list.append(offset+42)      # Enchant Shader    38 + 4
                    offsets_list.append(offset+74)      # Actor Value       42 + 4 + (4 * 7 = 28)
                    offsets_list.append(offset+78)      # Projectile        74 + 4
                    offsets_list.append(offset+82)      # Explosion         78 + 4
                    offsets_list.append(offset+94)      # Actor Value 2     82 + 4 + 4 + 4
                    offsets_list.append(offset+98)      # Casting Art       94 + 4
                    offsets_list.append(offset+102)     # Hit Effect Art    98 + 4
                    offsets_list.append(offset+106)     # Impact Data       102 + 4
                    offsets_list.append(offset+114)     # Dual Casting Art  106 + 4 + 4
                    offsets_list.append(offset+122)     # Enchant Art       114 + 4 + 4
                    offsets_list.append(offset+126)     # Hit Visuals       122 + 4
                    offsets_list.append(offset+130)     # Enchant Visuals   126 + 4
                    offsets_list.append(offset+134)     # Equip Ability     130 + 4
                    offsets_list.append(offset+138)     # Image Space Modi  134 + 4
                    offsets_list.append(offset+142)     # Perk to Apply     138 + 4
                elif field == b'SNDD':
                    ref_count = field_size // 8
                    inner_offset = offset + 6
                    for _ in range(ref_count):
                        offsets_list.append(inner_offset+4)    # Sound SNDR
                        inner_offset += 8
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_misc_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'YNAM', b'ZNAM', b'FIMD'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'KWDA', b'CVPA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field in (b'DAMC', b'CVPA'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_mstt_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'DMDS', b'SNAM'}
        special_form_fields = {b'VMAD', b'DAMC', b'DMDS', b'KWDA', b'PRPS'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field in (b'DAMC', b'PRPS'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DMDS':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_musc_data(i, form):
        special_form_fields = {b'TNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'TNAM':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_must_data(i, form):
        special_form_fields = {b'CTDA', b'SNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                elif field == b'SNAM':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_navi_data(i, form):
        special_form_fields = {b'NVMI', b'NVPP', b'NVSI'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'NVSI':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'NVPP':
                    path_count = struct.unpack("<I", form[offset+6:offset+10])[0]
                    in_field_offset = offset + 10
                    #Path Table
                    for _ in range(path_count):
                        form_id_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                        in_field_offset += 4
                        for _ in range(form_id_count):
                            offsets_list.append(in_field_offset)
                            in_field_offset += 4
                    node_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4
                    #Node Table
                    for _ in range(node_count):
                        offsets_list.append(in_field_offset)
                        in_field_offset += 8
                elif field == b'NVMI':
                    in_field_offset = offset + 6
                    offsets_list.append(in_field_offset)    # Navmesh
                    in_field_offset += 24                   # Merged to Count
                    merged_to_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4                    # start of Merged to
                    for _ in range(merged_to_count):
                        offsets_list.append(in_field_offset)
                        in_field_offset += 4
                    perferred_merges_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4                    # start of Perferred Merges
                    for _ in range(perferred_merges_count):
                        offsets_list.append(in_field_offset)
                        in_field_offset += 4
                    door_refr_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4                    # start of door structs
                    for _ in range(door_refr_count):
                        offsets_list.append(in_field_offset+4)
                        in_field_offset += 8
                    offsets_list.append(offset + 6 + field_size - 8) # World Space
                    offsets_list.append(offset + 6 + field_size - 4) # Cell

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_navm_data(i, form): 
        special_form_fields = {b'NVNM', b'ONAM', b'MNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'NVNM':
                    offsets_list.extend(form_processor.nvnm_reader(form, offset))
                elif field == b'ONAM':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'MNAM':
                    in_field_offset = offset + 6
                    end_of_field = offset + field_size + 6
                    while in_field_offset < end_of_field:
                        offsets_list.append(in_field_offset)    # Reference
                        in_field_offset += 4
                        num_tris = struct.unpack("<H", form[in_field_offset:in_field_offset+2])[0]
                        in_field_offset += (2 * num_tris) + 2

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_note_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'YNAM', b'ZNAM', b'SNAM'}
        special_form_fields = {b'VMAD'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_npc__data(i, form):
        form_fields = {b'PTRN', b'STCP', b'SNAM', b'INAM', b'VTCK', b'TPLT', b'LTPT', b'LTPC', b'RNAM', b'SPLO', b'DMDS', b'WNAM', b'ANAM', b'ATKR', 
                       b'ATKW', b'ATKS', b'SPOR', b'OCOR', b'GWOR', b'ECOR', b'FCPL', b'RCLR', b'PRKR', b'FTYP', b'NTRM', b'CNTO', b'COED', b'PKID', 
                       b'CNAM', b'PNAM', b'HCLF', b'BCLF', b'ZNAM', b'GNAM', b'CS2K', b'CS2D', b'CSCR', b'PFRN', b'DOFT', b'SOFT', b'DPLT', b'CRIF', 
                       b'FTST'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'ATKD', b'PRPS', b'KWDA', b'APPR', b'OBTS'}       

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field in (b'DAMC', b'PRPS'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'ATKD':
                    offsets_list.append(offset + 14)    # Attack Spell 6 + 4 + 4
                elif field in (b'KWDA', b'APPR'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'OBTS':
                    offsets_list.extend(form_processor.obts_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_omod_data(i, form):
        form_fields = {b'MODS', b'LNAM'}
        special_form_fields = {b'DATA', b'MNAM', b'FNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'DATA':
                    in_field_offset = offset + 6
                    include_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4
                    property_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 12
                    offsets_list.append(in_field_offset)    # Attach Point
                    in_field_offset += 4
                    kwd_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += 4
                    for _ in range(kwd_count):
                        offsets_list.append(in_field_offset)
                        in_field_offset += 4
                    item_count = struct.unpack("<I", form[in_field_offset:in_field_offset+4])[0]
                    in_field_offset += (8 * item_count) + 4
                    for _ in range(include_count):
                        offsets_list.append(in_field_offset)
                        in_field_offset += 7
                    for _ in range(property_count):
                        val_type = form[in_field_offset:in_field_offset+1]
                        in_field_offset += 12
                        if val_type in (b'\x06', b'\x04'):
                            offsets_list.append(in_field_offset)
                        in_field_offset += 12
                elif field in (b'MNAM', b'FNAM'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
            
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
     
    def save_otft_data(i, form):
        special_form_fields = {b'INAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'INAM':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_ovis_data(i, form):
        form_fields = {b'INDX'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_pack_data(i, form):
        form_fields = {b'CNAM', b'QNAM', b'TPIC', b'INAM'}
        special_form_fields = {b'VMAD', b'CTDA', b'IDLA', b'PKCU', b'PDTO', b'PLDT', b'PTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                elif field == b'IDLA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'PKCU':
                    offsets_list.append(offset+10)
                elif field == b'PDTO':
                    topic_type = struct.unpack("<I", form[offset+6:offset+10])[0]
                    if topic_type == 0:
                        offsets_list.append(offset+10)
                elif field == b'PLDT':
                    loc_type = struct.unpack("<I", form[offset+6:offset+10])[0]
                    if loc_type in (0,1,4,6):
                        offsets_list.append(offset+10)
                elif field == b'PTDA':
                    loc_type = struct.unpack("<I", form[offset+6:offset+10])[0]
                    if loc_type in (0,1,3,7):
                        offsets_list.append(offset+10)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_perk_data(i, form):
        form_fields = {b'SNAM', b'NNAM'}
        special_form_fields = {b'VMAD', b'CTDA', b'PRKE', b'DATA', b'EPFT', b'EPFD'}

        offsets_list = [12]
        offset = 24
        prke_type = -1
        epft_type = -1
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                elif field == b'PRKE':
                    prke_type = form[offset+6]
                elif field == b'DATA' and prke_type != -1:
                    if prke_type in (0,1):  # 0 is Quest ID, 1 is Ability ID, 2 is Entry Point Type
                        offsets_list.append(offset+6)
                    prke_type = -1
                elif field == b'EPFT':
                    epft_type = form[offset+6]
                elif field == b'EPFD' and epft_type != -1:
                    if epft_type in (3, 4, 5, 8): # 3 LVLI, 4 & 5 SPEL, 8 Actor Value + Float
                        offsets_list.append(offset+6)
                    epft_type = -1

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_pkin_data(i, form):
        form_fields = {b'CNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_placed_data(i, form): 
        form_fields = {b'NAME', b'XEZN', b'XPWR', b'XAPR', b'XASP', b'XLYR', b'XMSP', b'XRFG', b'XESP', b'XOWN', b'XEMI', b'XMBR', b'XLRL'}
        special_form_fields = {b'VMAD', b'XLKR', b'XLRT'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'XLKR':
                    offsets_list.append(offset + 6)
                    offsets_list.append(offset + 10)
                elif field == b'XLRT':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_plyr_data(i, form): # Theoretically never seen?
        form_fields = {b'PLYR'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_proj_data(i, form):
        form_fields = {b'MODS',  b'DMDS'}
        special_form_fields = {b'DAMC',b'DSTD', b'DNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'DNAM':
                    offsets_list.append(offset + 22)    # Light                 6 + 2 + 2 + 4 + 4 + 4
                    offsets_list.append(offset + 26)    # Muzzle Flash - Light  22 + 4
                    offsets_list.append(offset + 38)    # Explosion             26 + 12
                    offsets_list.append(offset + 42)    # Sound                 38 + 4
                    offsets_list.append(offset + 58)    # Sound - Countdown     42 + 16
                    offsets_list.append(offset + 62)    # Sound - Disasble      58 + 4
                    offsets_list.append(offset + 66)    # Default Weapon Sound  62 + 4
                    offsets_list.append(offset + 86)    # Decal Data            66 + 20
                    offsets_list.append(offset + 90)    # Collision Layer       86 + 4
                    offsets_list.append(offset + 95)    # VATS Projectile       90 + 4 + 1

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_qust_data(i, form):
        form_fields = {b'LNAM', b'XNAM', b'QTGL', b'NAM0', b'ALFR', b'ALUA', b'KNAM', b'ALRT', b'ALEQ', b'ALCO', b'CNTO', b'COED',
                       b'SPOR', b'OCOR', b'GWOR', b'ECOR', b'ALDN', b'ALFV', b'ALDI', b'ALSP', b'ALFC', b'ALPC', b'VTCK', b'ALFL', b'GNAM'}
        special_form_fields = {b'VMAD', b'CTDA', b'QSTA', b'KWDA', b'ALLA'}
        form_version = struct.unpack("<H", form[20:22])[0]

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                elif field == b'QSTA':
                    if form_version > 82: # Maybe >= instead of > ?
                        offsets_list.append(offset + 14) # 6 + 8
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'ALLA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_race_data(i, form):
        form_fields = {b'STCP', b'SPLO', b'WNAM', b'ATKR', b'ATKW', b'ATKS', b'MODS', b'GNAM', b'NAM4', b'NAM5', b'NAM7', b'CNAM', b'NAM2',
                       b'ONAM', b'LNAM', b'MTYP', b'QNAM', b'UNWP', b'WKMV', b'SMWV', b'FLMV', b'SNMV', b'HEAD', b'RPRM', b'AHCM', b'FTSM',
                       b'DFTM', b'MPPT', b'RPRF', b'AHCF', b'FTSF', b'DFTF', b'NAM8', b'RNAM', b'SRAC', b'SADD', b'SAKD', b'STKD', b'QSTI'}
        special_form_fields = {b'KWDA', b'PRPS', b'APPR', b'DATA', b'VTCK', b'HCLF', b'ATKD', b'RBPC', b'TTEC'}
        form_version = struct.unpack("<H", form[20:22])[0]

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field in (b'KWDA', b'APPR'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'PRPS':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DATA':
                    in_field_offset = offset + 124                  # 6 + (4 * 28 = 112) + 2 + (1 * 4 = 4)
                    if form_version >= 109:
                        in_field_offset += 24                       # Floats for male/female: thin+muscular+fat
                        if form_version >= 124:
                            in_field_offset += 4                    # Beard Biped Object integer
                    offsets_list.append(in_field_offset)            #           Sevarable - Explosion
                    offsets_list.append(in_field_offset + 4)        # 0 + 4     Severable - Derbis
                    offsets_list.append(in_field_offset + 8)        # 4 + 4     Severable - Impact DataSet
                    offsets_list.append(in_field_offset + 12)       # 8 + 4     Explodable - Explosion
                    offsets_list.append(in_field_offset + 16)       # 12 + 4    Explodable - Debris
                    offsets_list.append(in_field_offset + 20)       # 16 + 4    Explodable - Impact DataSet
                    if form_version >= 96:
                        in_field_offset += 30                       # 20 + 4 + 4 + 1 + 1
                        offsets_list.append(in_field_offset)        #           OnCripple - Explosion
                        offsets_list.append(in_field_offset + 4)    # 0 + 4     OnCripple - Derbis
                        offsets_list.append(in_field_offset + 8)    # 4 + 4     OnCripple - Impact DataSet   
                        in_field_offset += 12
                        if form_version >= 118:
                            offsets_list.append(in_field_offset)    #           Explodable - Subsegment Explosion
                elif field in (b'VTCK', b'HCLF'):
                    offsets_list.append(offset + 6)     # 6     Male voice/hair color
                    offsets_list.append(offset + 10)    # 6 + 4 Female voice/hair color
                elif field == b'ATKD':
                    offsets_list.append(offset + 14) # 6 + 4 + 4 Attack Spell
                elif field == b'RBPC':
                    if form_version >= 78:
                        offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'TTEC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=14))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_refr_data(i, form):
        form_fields = {b'NAME', b'LNAM', b'INAM', b'XLRM', b'XEMI', b'XLTW', b'XPWR', b'XTNM', b'XMBR', 
                       b'XASP', b'XLYR', b'XMSP', b'XRFG', b'XSPC', b'XAPR', b'XLIB', b'XLCN', b'XEZN', 
                       b'XNDP', b'XLRL', b'XOWN', b'XESP', b'INAM', b'XATR', b'XPLK', b'XCZR', b'XCZC'}
        special_form_fields = {b'VMAD', b'XPOD', b'XORD', b'XTEL', b'XLOC', b'XLRT', b'XLKR', b'PDTO', b'XWPN'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field in (b'XPOD', b'XORD', b'XLRT', b'XWPN'):  
                    # XPOD is ref 0: fid, fid; ref 1: fid, fid; ref 2: fid, fid; etc.: so technically fits as a FID array of size 4
                    # XORD is always an array of 4 FIDs of size 16
                    # XWPN is always an array of 3 FIDs of size 12
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'XTEL':
                    offsets_list.append(offset+6)   #           Door 
                    offsets_list.append(offset+34)  # 6 + 28    Transition Interior
                elif field == b'XLOC':
                    offsets_list.append(offset+10)  # 6 + 4     Key
                elif field == b'XLKR':
                    offsets_list.append(offset+6)   #           Keyword
                    offsets_list.append(offset+10)  # 6 + 4     Ref
                elif field == b'PDTO':  # maybe move to a func
                    if form[offset+6:offset+7] == b'\x00':
                        offsets_list.append(offset + 10)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_regn_data(i, form):
        form_fields = {b'WNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
  
    def save_rela_data(i, form):
        special_form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'DATA':
                    offsets_list.append(offset+6)   # 6                 Parent
                    offsets_list.append(offset+10)  # 6 + 4             Child
                    offsets_list.append(offset+18)  # 10 + 4 + 1+2+1    Association Type

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_rfct_data(i, form):
        special_form_fields = {b'DATA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'DATA':
                    offsets_list.append(offset+6)   # 6     Effect Art
                    offsets_list.append(offset+10)  # 6 + 4 Shader

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_rfgp_data(i, form):
        form_fields = {b'RNAM', b'PNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_scco_data(i, form):
        form_fields = {b'QNAM', b'SNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_scen_data(i, form):
        form_fields = {b'DATA', b'VENC', b'ONAM', b'PNAM', b'PTOP', b'NTOP', b'NETO', b'QTOP', b'PLVD', b'JOUT', b'DALC', b'NPOT', b'NNGT', b'NNUT', b'NQUT', b'NPOS', b'NNGS', b'NNUS', b'NQUS', b'TNAM', b'STSC', b'LCEP'}
        special_form_fields = {b'VMAD', b'CTDA', b'KWDA', b'ANAM', b'HTID'}

        anam_type = b''
        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'ANAM':
                    anam_type = form[offset+6:offset+8] if field_size == 2 else b''
                elif field == b'HTID':
                    if anam_type == b'\x06\x00' and field_size == 4:    # Action Radio(6) HTID is FID, Actions Dialog(0) and Start Scene(4) HTIDs are not FIDs
                        offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_scol_data(i, form): 
        form_fields = {b'PTRN', b'MODS', b'ONAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_scsn_data(i, form):
        form_fields = {b'CNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_smbn_data(i, form):
        form_fields = {b'PNAM', b'SNAM'}
        special_form_fields = {b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_smen_data(i, form):
        form_fields = {b'PNAM', b'SNAM'}
        special_form_fields = {b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_smqn_data(i, form):
        form_fields = {b'PNAM', b'SNAM', b'NNAM'}
        special_form_fields = {b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(offset, form))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_snct_data(i, form):
        form_fields = {b'PNAM', b'ONAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_sndr_data(i, form):
        form_fields = {b'GNAM', b'SNAM', b'ONAM', b'DNAM'}
        special_form_fields = {b'CTDA', b'CNAM', b'BNAM'}

        cnam_type = b''
        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))
                elif field == b'CNAM':
                    cnam_type = form[offset+6:offset+10]
                elif field == b'BNAM':
                    if cnam_type == b'\xe3\x7a\x15\xed':    # if AutoWeapon type
                        offsets_list.append(offset+6)       # Base Descriptor

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_sopm_data(i, form):
        form_fields = {b'ENAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_soun_data(i, form):
        form_fields = {b'SDSC'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_spel_data(i, form):
        form_fields = {b'ETYP', b'EFID'}
        special_form_fields = {b'KWDA', b'SPIT', b'CTDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'SPIT':
                    offsets_list.append(offset + 38)     # 6 + (4 * 8 = 32) Casting Perk
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_stag_data(i, form):
        form_fields = {b'TNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_stat_data(i, form):
        form_fields = {b'PTRN', b'FTYP', b'MODS'}
        special_form_fields = {b'VMAD', b'PRPS', b'DNAM', b'NVNM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'PRPS':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DNAM':
                    offsets_list.append(offset + 10)    # 6 + 4 Material
                elif field == b'NVNM':
                    offsets_list.extend(form_processor.nvnm_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]
    
    def save_tact_data(i, form):
        form_fields = {b'MODS', b'DMDS', b'SNAM', b'VNAM'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'KWDA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(form, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_term_data(i, form):
        form_fields = {b'PTRN', b'MODS', b'CNTO', b'TNAM'}
        special_form_fields = {b'VMAD', b'KWDA', b'PRPS', b'SNAM', b'CTDA'}
        form_version = struct.unpack("<H", form[20:22])[0]

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'KWDA':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'PRPS':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'SNAM':
                    if field_size == 4:
                        offsets_list.append(offset + 6)
                    else:
                        marker_size = 24 if form_version >= 125 else 20
                        marker_count = field_size // marker_size
                        in_field_offset = offset + 22 # 6 + 16
                        for _ in range(marker_count):
                            offsets_list.append(in_field_offset)
                            in_field_offset += marker_size
                elif field == b'CTDA':
                    offsets_list.extend(form_processor.ctda_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_tes4_data(i, form): 
        special_form_fields = {b'ONAM', b'TNAM'}

        offsets_list = []
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'ONAM':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'TNAM':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset+4, field_size-4))  # skip form type (first 4 bytes), the rest is an array of FIDs
            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_tree_data(i, form):
        form_fields = {b'MODS', b'PFIG', b'SNAM'}
        special_form_fields = {b'VMAD'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_watr_data(i, form):
        form_fields = {b'TNAM', b'SNAM', b'XNAM', b'YNAM', b'INAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_weap_data(i, form):
        form_fields = {b'PTRN', b'STCP', b'MODS', b'EITM', b'DMDS', b'ETYP', b'BIDS', b'BAMT', b'YNAM', 
                       b'ZNAM', b'INRD', b'NNAM', b'MO4S', b'INAM', b'LNAM', b'WAMD', b'WZMD', b'CNAM'}
        special_form_fields = {b'VMAD', b'DAMC', b'DSTD', b'KWDA', b'APPR', b'OBTS', b'DNAM', b'FNAM', b'CRDT', b'DAMA'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'VMAD':
                    offsets_list.extend(form_processor.vmad_reader(form, offset))
                elif field == b'DAMC':
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))
                elif field == b'DSTD':
                    offsets_list.extend(form_processor.get_dstd_offsets(offset))
                elif field in (b'KWDA', b'APPR'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'OBTS':
                    offsets_list.extend(form_processor.obts_reader(form, offset))
                elif field == b'DNAM':
                    offsets_list.append(offset + 6)     # 6         Ammo
                    offsets_list.append(offset + 46)    # 6 + 40    Skill
                    offsets_list.append(offset + 50)    # 46 + 4    Resist
                    offsets_list.append(offset + 79)    # 50 + 29   Sound - Attack
                    offsets_list.append(offset + 83)    # 79 + 4    Sound - Attack 2D
                    offsets_list.append(offset + 87)    # 83 + 4    Sound - Attack Loop
                    offsets_list.append(offset + 91)    # 87 + 4    Sound - Attack Fail
                    offsets_list.append(offset + 95)    # 91 + 4    Sound - Idle
                    offsets_list.append(offset + 99)    # 95 + 4    Sound - Equip Sound
                    offsets_list.append(offset + 103)   # 99 + 4    Sound - UnEquip Sound
                    offsets_list.append(offset + 107)   # 103 + 4   Sound - Fast Equip Sound
                elif field == b'FNAM':
                    offsets_list.append(offset + 35)    # 6 + 29    Override Projectile
                elif field == b'CRDT':
                    offsets_list.append(offset + 14)    # 6 + 8     Crit Effect
                elif field == b'DAMA':
                    # I don't think I need to check for version > 152? for CURV in Curve Table
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size, struct_size=8))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_wrld_data(i, form):
        form_fields = {b'LTMP', b'XEZN', b'XLCN', b'WNAM', b'CNAM', b'NAM2', b'NAM3', b'MODS', b'ZNAM'}
        special_form_fields = {b'RNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field == b'RNAM' and field_size > 8:
                    # 2 + 2 + 4;        2: X cord, 2: Y cord, 4: Reference Count?, remaining is array of references with 4 fid, 2 X, 2 Y; so struct 8
                    offsets_list.extend(form_processor.get_offsets_from_array(offset+8, field_size-8, struct_size=8))

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_wthr_data(i, form):
        form_fields = {b'MNAM', b'NNAM', b'SNAM', b'TNAM', b'MODS', b'GNAM'}
        special_form_fields = {b'IMSP', b'WGDR', b'UNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                if field in (b'IMSP', b'WGDR'):
                    offsets_list.extend(form_processor.get_offsets_from_array(offset, field_size))
                elif field == b'UNAM':
                    offsets_list.append(offset + 6)
                    offsets_list.append(offset + 14)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    def save_zoom_data(i, form):
        special_form_fields = {b'GNAM'}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in special_form_fields:
                if field == b'GNAM':
                    offsets_list.append(offset + 14)

            offset += field_size + 6
        return [i, bytearray(form), offsets_list]

    #Template for each type of form
    def save_FORM_data(i, form): 
        form_fields = {b''}
        special_form_fields = {b''}

        offsets_list = [12]
        offset = 24
        while offset < len(form):
            #field = form[offset:offset+4]
            #field_size = struct.unpack("<H", form[offset+4:offset+6])[0]
            field, field_size, offset = form_processor.get_field_and_size(offset, form)
            if field in form_fields and field_size >= 4:
                offsets_list.append(offset + 6)
            elif field in special_form_fields:
                pass
            offset += field_size + 6

        return [i, bytearray(form), offsets_list]
    
    def ctda_reader(form, offset):
        functions_with_param1_but_not_fid = {6, 8, 10, 11, 36, 70, 98, 181, 247, 289, 312, 325, 360, 368, 397, 407, 432, 437, 446, 447,
                                            473, 528, 566, 567, 570, 571, 572, 576, 596, 597, 598, 600, 601, 602, 604, 605, 608, 610,
                                            611, 612, 619, 620, 622, 626, 659, 660, 675, 684, 706, 744, 746, 747, 748, 776, 811}
        functions_with_param2_but_not_fid = {59, 98, 122, 131, 407, 550, 584, 595, 629, 639, 660, 744}
        #functions_with_param3_but_not_fid = {98} # No functions with FID parameter 3
        offsets_list = []
        offset += 6
        op_flag_byte = form[offset]
        flags = op_flag_byte & 0x1F  # Mask out the upper 3 bits, keeping only the lower 5 bits
        use_global_flag = (flags & 0x04) != 0
        offset += 4
        #If lower 5 bit 0x04 is set then use global and comparison value is a formid
        if use_global_flag: 
            offsets_list.append(offset)  # ComparisonValue
        offset += 4
        function_index = struct.unpack("<H", form[offset:offset+2])[0]
        offset += 4
        # If a function has a param and we know it isn't a non-fid then it is either a form id or garbage data that doesn't matter
        if function_index not in functions_with_param1_but_not_fid and form[offset:offset+4] != b'\x00\x00\x00\x00':
            offsets_list.append(offset)      # param1
        if function_index not in functions_with_param2_but_not_fid and form[offset+4:offset+8] != b'\x00\x00\x00\x00':
            offsets_list.append(offset+ 4)   # param2
        # No functions have param3 as a form ID.
        #if function_index not in functions_with_param2=3_but_not_fid and form[idk:idk] != b'\x00\x00\x00\x00':
        #    offsets_list.append(idk)   # param
        offset += 8
        if form[offset:offset+4] == b'\x02\x00\x00\x00':    # Run On: Reference
            offsets_list.append(offset+ 4)                  # Reference FID
        return offsets_list
    
    def property_reader(form, offset, obj_format):
        offsets_list = []
        property_name_size = struct.unpack("<H", form[offset:offset+2])[0]
        #property_name = form[offset+2: offset +property_name_size + 2]
        offset += property_name_size + 2
        property_type = int.from_bytes(form[offset:offset+1][::-1])
        offset += 2
        if property_type == 1:
            if obj_format == 1:
                offsets_list.append(offset)
            elif obj_format == 2:
                offsets_list.append(offset+4)
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
        elif property_type == 6:
            ...
        elif property_type == 7:
            inner_offset_list, offset = form_processor.script_reader(form, offset, obj_format)
            offsets_list.extend(inner_offset_list)
        elif property_type == 11:
            item_count = struct.unpack("<I", form[offset:offset+4])[0]
            offset += 4
            if obj_format == 1:
                for _ in range(item_count):
                    offsets_list.append(offset)
                    offset += 8
            else:
                for _ in range(item_count):
                    offsets_list.append(offset+4)
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
        elif property_type == 16:
            #Called array of variable but only holds a single element count int32
            offset += 4
        elif property_type == 17:
            struct_count = struct.unpack("<I", form[offset:offset+4])[0]
            offset += 4
            for _ in range(struct_count):
                item_count = struct.unpack("<I", form[offset:offset+4])[0]
                offset += 4
                for __ in range(item_count):
                    inner_offset_list, offset = form_processor.property_reader(form, offset, obj_format)
                    offsets_list.extend(inner_offset_list)

        return offsets_list, offset

    def script_reader(form, offset, obj_format):
        offsets_list = []
        script_name_size = struct.unpack("<H", form[offset:offset+2])[0]
        #script_name = form[offset+2:offset+script_name_size+2]
        offset += script_name_size + 2
        property_count = struct.unpack("<H", form[offset+1:offset+3])[0]
        offset += 3
        for _ in range(property_count):
            property_offsets_list, offset =form_processor.property_reader(form, offset, obj_format)
            offsets_list.extend(property_offsets_list)

        return offsets_list, offset
    
    def vmad_reader(form:bytes, offset:int) -> list[int]:
        offsets_list = []
        vmad_size = struct.unpack("<H", form[offset+4:offset+6])[0]
        vmad_end_offset = offset + 6 + vmad_size
        obj_format = struct.unpack("<H", form[offset+8:offset+10])[0]
        script_count = struct.unpack("<H", form[offset+10:offset+12])[0]
        offset += 12
        for _ in range(script_count):
            script_offsets, offset = form_processor.script_reader(form, offset, obj_format)
            offsets_list.extend(script_offsets)

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
                        offsets_list.append(offset)
                    elif obj_format == 2:
                        offsets_list.append(offset+4)
                    offset += 12
                    alias_script_count = struct.unpack("<H", form[offset:offset+2])[0]
                    offset += 2
                    for _ in range(alias_script_count):
                        alias_script_offsets, offset = form_processor.script_reader(form, offset, obj_format)
                        offsets_list.extend(alias_script_offsets)
            else:
                offset += 1
                script_offsets, offset = form_processor.script_reader(form, offset, obj_format)
                offsets_list.extend(script_offsets)

        return offsets_list
    
    def nvnm_reader(form: bytes, offset: int) -> list[int]:
        offsets_list = []
        if form[offset+14:offset+18] != b'\x00\x00\x00\x00':
            offsets_list.append(offset+14)   # Parent World 6 + 4 + 4
        else:
            offsets_list.append(offset+18)   # Parent Cell 6 + 4 + 4 + 4 + 4 
        offset += 22
        vert_count = struct.unpack("<I", form[offset:offset+4])[0]
        offset += 4
        offset += 12 * vert_count
        tri_count = struct.unpack("<I", form[offset:offset+4])[0]
        offset += 4
        offset += 21 * tri_count
        edge_count = struct.unpack("<I", form[offset:offset+4])[0]
        offset += 4
        for _ in range(edge_count):
            offsets_list.append(offset+4)    # Edge Links > Edge Link # > Navmesh
            offset += 11
        door_count = struct.unpack("<I", form[offset:offset+4])[0]
        offset += 4
        for _ in range(door_count):
            offsets_list.append(offset+6)    # Door Links > Door Link > Door Ref
            offset += 10
        return offsets_list
    
    def obts_reader(form, offset):
        offsets_list = []
        offset += 6
        include_count = struct.unpack("<I", form[offset:offset+4])[0]
        offset += 4
        property_count = struct.unpack("<I", form[offset:offset+4])[0]
        offset += 11
        kwd_count = form[offset:offset+1][0]
        offset += 1
        for _ in range(kwd_count):
            offsets_list.append(offset)
            offset += 4
        offset += 2
        for _ in range(include_count):
            offsets_list.append(offset)
            offset += 7
        for _ in range(property_count):
            val_type = form[offset:offset+1]
            offset += 12
            if val_type in (b'\x06', b'\x04'):
                offsets_list.append(offset)
            offset += 12
        return offsets_list

if __name__ == "__main__":
    def create_data_list(data: bytes) -> list:
        data_list = []
        offset = 0
        while offset < len(data):
            if data[offset:offset+4] == b'GRUP':
                data_list.append(data[offset:offset+24])
                offset += 24
            else:
                form_length = struct.unpack("<I", data[offset+4:offset+8])[0]
                offset_end = offset + 24 + form_length
                data_list.append(data[offset:offset_end])
                offset = offset_end
        return data_list   
    import os
    file = os.path.normpath(r"C:\Users\s34ke\AppData\Local\ModOrganizer\Fallout 4\overwrite\browse.esl")
    with open(file, 'rb') as f:
        data = f.read()

    data_list = create_data_list(data)
    form_processor.save_all_form_data(data_list)
