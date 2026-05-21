from RTN import parse

from program.services.downloaders import _is_extras_file


def _parse(filename: str):
    return parse(filename)


def test_real_episode_is_not_extras():
    path = "The Office US S03/The Office US S03E02.mkv"
    assert _is_extras_file(_parse(path.split("/")[-1]), path) is False


def test_behind_the_scenes_folder_is_extras():
    # Parses to a plausible episode number; only the folder reveals it's an extra.
    path = "The Office US S03/Extras/Behind The Scenes E02.mkv"
    assert _is_extras_file(_parse(path.split("/")[-1]), path) is True


def test_featurettes_folder_is_extras():
    path = "The Office US COMPLETE/Featurettes/The Accountant Webisode 1.mkv"
    assert _is_extras_file(_parse(path.split("/")[-1]), path) is True


def test_deleted_scenes_flagged_by_rtn():
    path = "The Office US/Deleted Scenes/S03 Part 1.mkv"
    assert _is_extras_file(_parse(path.split("/")[-1]), path) is True


def test_show_titled_extras_is_not_filtered():
    # The show is literally named "Extras" — the first path segment is skipped
    # so its episodes are not mistaken for supplementary content.
    path = "Extras/Season 1/Extras S01E01.mkv"
    assert _is_extras_file(_parse(path.split("/")[-1]), path) is False


def test_no_path_falls_back_to_rtn():
    assert _is_extras_file(_parse("The Office US S03E01.mkv"), None) is False
    assert _is_extras_file(_parse("Sample-The Office US S01E01.mkv"), None) is True
