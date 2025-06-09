from nartools.file_manip import zero_pad_frame_nums as zpf
from pathlib import Path, PurePath
from fsspec.implementations.local import LocalFileSystem


def test_zpf_on_local_fs(tmp_path):
  """
  Creates a copy of test input data in the local filesystem,
  and tests zero padding of frame numbers on it
  """

  # Initialising local filesystem
  fs = LocalFileSystem(auto_mkdir=True)
  input_dir = tmp_path / Path('unpadded')
  output_dir = tmp_path / Path('padded')

  # Creating input files/tree
  input_files = ["lidar_1-frame_23.pcd", "lidar_1-frame_2.pcd", "lidar_1-frame_1023.pcd"]
  for file in input_files:
    fs.touch(str(input_dir / Path(file)))

  # Invoking the zpf solution
  fixer = zpf.FrameNamingFixer(
    fs,
    str(input_dir),
    str(output_dir),
    'lidar_{lnum}-frame_{fnum}.pcd', 'fnum', 4
  )
  fixer.generate_fixed_dir()

  # Inspecting the output files/tree
  ideal_files = ["lidar_1-frame_0023.pcd", "lidar_1-frame_0002.pcd", "lidar_1-frame_1023.pcd"]
  output_files = [PurePath(str(file)).name for file in fs.ls(str(output_dir))]
  assert set(output_files) == set(ideal_files)
