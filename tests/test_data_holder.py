"""data_holder._global: settings plumbing and get_rel_path (maps absolute paths to Data-relative paths)."""
import os

import pytest


def _settings(g, **kw):
    g._settings = kw
    g.cwd = os.getcwd()
    g.update_from_settings()


class TestUpdateFromSettings:
    def test_defaults(self, g, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _settings(g)
        assert g.output_folder_name == "ESLifier Output"
        assert g.mod_manager_mode == 0
        assert g.update_header is True
        assert g.generate_cell_master is True
        assert g.persistent_ids is True
        assert g.free_non_existent is False
        assert g.hash_output is True
        assert g.all_patcher_experimental is False
        assert g.mo2_profile == "Default"

    def test_values_are_read(self, g, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _settings(g, update_header=False, generate_cell_master=False, persistent_ids=False,
                  free_non_existent=True, mod_manager_mode=2, mo2_profile="Mine")
        assert g.update_header is False
        assert g.generate_cell_master is False
        assert g.persistent_ids is False
        assert g.free_non_existent is True
        assert g.mod_manager_mode == 2
        assert g.mo2_profile == "Mine"

    def test_output_path_is_joined_and_lengths_cached(self, g, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        out = str(tmp_path / "out")
        _settings(g, output_folder_path=out, output_folder_name="My Output")
        expected = os.path.normpath(os.path.join(out, "My Output"))
        assert g.output_folder_joined_path == expected
        assert g.output_folder_joined_path_lower == expected.lower()
        assert g.output_folder_joined_path_len == len(expected)

    def test_skyrim_path_only_taken_from_settings_in_manual_mode(self, g, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _settings(g, mod_manager_mode=0, game_folder_path="/skyrim/Data")
        assert g.game_folder_path == "/skyrim/Data"
        g.game_folder_path = "/from/vortex"
        _settings(g, mod_manager_mode=1, game_folder_path="/skyrim/Data")
        assert g.game_folder_path == "/from/vortex"

    def test_folders_grabbed_reset(self, g, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        g.folders_grabbed = True
        _settings(g)
        assert g.folders_grabbed is False

    def test_update_vortex_vars(self, g):
        g.mod_staging_folder = "/Staging/Folder"
        g.game_folder_path = "/Skyrim/Data"
        g.update_vortex_vars()
        assert g.mod_staging_folder_lower == "/staging/folder"
        assert g.mod_staging_folder_len == len("/Staging/Folder")
        assert g.game_folder_path_lower == "/skyrim/data"
        assert g.folders_grabbed is True

    def test_update_mo2_vars(self, g):
        g.mo2_mods_folder = "/MO2/mods"
        g.mo2_overwrite_path = "/MO2/overwrite"
        g.update_mo2_vars()
        assert g.mo2_mods_folder_lower == "/mo2/mods"
        assert g.mo2_overwrite_path_len == len("/MO2/overwrite")
        assert g.folders_grabbed is True


class TestGetRelPath:
    @pytest.fixture
    def env(self, g, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self.root = str(tmp_path)
        return g

    def join(self, *p):
        return os.path.normpath(os.path.join(self.root, *p))

    def test_manual_mode(self, env):
        skyrim = self.join("Skyrim", "Data")
        _settings(env, mod_manager_mode=0, game_folder_path=skyrim,
                  output_folder_path=self.join("out"))
        assert env.get_rel_path(os.path.join(skyrim, "Meshes", "a.nif")) == os.path.join("Meshes", "a.nif")

    def test_manual_mode_is_case_insensitive(self, env):
        skyrim = self.join("Skyrim", "Data")
        _settings(env, mod_manager_mode=0, game_folder_path=skyrim,
                  output_folder_path=self.join("out"))
        weird = os.path.join(skyrim.upper(), "Meshes", "a.nif")
        assert env.get_rel_path(weird) == os.path.join("Meshes", "a.nif")

    def test_backslashes_are_normalised(self, env):
        skyrim = self.join("Skyrim", "Data")
        _settings(env, mod_manager_mode=0, game_folder_path=skyrim,
                  output_folder_path=self.join("out"))
        assert env.get_rel_path(skyrim + "\\Meshes\\a.nif") == os.path.join("Meshes", "a.nif")

    def test_mo2_mods_folder_strips_mod_name(self, env):
        mods, overwrite = self.join("MO2", "mods"), self.join("MO2", "overwrite")
        _settings(env, mod_manager_mode=2, output_folder_path=self.join("out"))
        env.mo2_mods_folder, env.mo2_overwrite_path = mods, overwrite
        env.update_mo2_vars()
        assert env.get_rel_path(os.path.join(mods, "Cool Mod", "Meshes", "a.nif")) == os.path.join("Meshes", "a.nif")

    def test_mo2_overwrite(self, env):
        mods, overwrite = self.join("MO2", "mods"), self.join("MO2", "overwrite")
        _settings(env, mod_manager_mode=2, output_folder_path=self.join("out"))
        env.mo2_mods_folder, env.mo2_overwrite_path = mods, overwrite
        env.update_mo2_vars()
        assert env.get_rel_path(os.path.join(overwrite, "SKSE", "x.ini")) == os.path.join("SKSE", "x.ini")

    def test_mo2_mod_root_file_without_subfolder(self, env):
        mods, overwrite = self.join("MO2", "mods"), self.join("MO2", "overwrite")
        _settings(env, mod_manager_mode=2, output_folder_path=self.join("out"))
        env.mo2_mods_folder, env.mo2_overwrite_path = mods, overwrite
        env.update_mo2_vars()
        assert env.get_rel_path(os.path.join(mods, "Cool Mod")) == "Cool Mod"

    def test_vortex_mod_staging(self, env):
        staging = self.join("Vortex", "skyrimse")
        _settings(env, mod_manager_mode=1, output_folder_path=self.join("out"))
        env.game_folder_path = self.join("Skyrim", "Data")
        env.mod_staging_folder = staging
        env.update_vortex_vars()
        assert env.get_rel_path(os.path.join(staging, "ModX", "Meshes", "a.nif")) == os.path.join("Meshes", "a.nif")

    def test_vortex_skyrim_data_folder(self, env):
        staging = self.join("Vortex", "skyrimse")
        skyrim = self.join("Skyrim", "Data")
        _settings(env, mod_manager_mode=1, output_folder_path=self.join("out"))
        env.game_folder_path = skyrim
        env.mod_staging_folder = staging
        env.update_vortex_vars()
        assert env.get_rel_path(os.path.join(skyrim, "x.esp")) == "x.esp"

    def test_output_folder_files(self, env):
        skyrim = self.join("Skyrim", "Data")
        _settings(env, mod_manager_mode=0, game_folder_path=skyrim,
                  output_folder_path=self.join("out"), output_folder_name="Out")
        assert env.get_rel_path(os.path.join(self.join("out", "Out"), "meshes", "a.nif")) == os.path.join("meshes", "a.nif")

    def test_bsa_extracted(self, env):
        _settings(env, mod_manager_mode=0, game_folder_path=self.join("Skyrim", "Data"),
                  output_folder_path=self.join("out"))
        f = os.path.join(env.cwd, "bsa_extracted", "meshes", "a.nif")
        assert env.get_rel_path(f) == os.path.join("meshes", "a.nif")

    def test_bsa_extracted_temp(self, env):
        _settings(env, mod_manager_mode=0, game_folder_path=self.join("Skyrim", "Data"),
                  output_folder_path=self.join("out"))
        f = os.path.join(env.cwd, "bsa_extracted_temp", "meshes", "a.nif")
        assert env.get_rel_path(f) == os.path.join("meshes", "a.nif")

    def test_unknown_path_raises(self, env):
        _settings(env, mod_manager_mode=0, game_folder_path=self.join("Skyrim", "Data"),
                  output_folder_path=self.join("out"))
        with pytest.raises(RuntimeError):
            env.get_rel_path(os.path.join(self.root, "somewhere", "else.esp"))
