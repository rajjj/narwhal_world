from nartools.file_manip import match_frames_across_streams as mfs
from pathlib import Path, PurePath
from fsspec.implementations.local import LocalFileSystem
import datetime
import pdb


def list_dir_files(fs, dirpath):
  """
  Lists the files in a dir (basenames only)
  """
  return [
    PurePath(file).name
    for file in fs.ls(dirpath)
  ]

def create_input_data(fs, cam1_raw_dir, cam2_raw_dir, lidar_raw_dir):
  """
  Creates the input directories and files for the test
  at a specified path in a given filesystem
  """

  cam1_raw_files = [
    'frame_1-timestamp_2.jpg',
    'frame_2-timestamp_4.jpg',
    'frame_3-timestamp_6.jpg',
    'frame_4-timestamp_8.jpg',
    'frame_5-timestamp_10.jpg',
    'frame_6-timestamp_12.jpg',
    'frame_7-timestamp_14.jpg',
    'frame_8-timestamp_16.jpg',
    'frame_9-timestamp_18.jpg',
    # intentionally leaving 'frame_10-timestamp_20.jpg' missing
    'frame_11-timestamp_22.jpg',
    'frame_12-timestamp_24.jpg',
    'frame_13-timestamp_26.jpg',
    'frame_14-timestamp_28.jpg',
    'frame_15-timestamp_29.jpg',
    'frame_16-timestamp_32.jpg',
  ]
  for file in cam1_raw_files:
    fs.touch(cam1_raw_dir / Path(file))

  cam2_raw_files = [
    'frame_1-timestamp_1.jpg',
    'frame_2-timestamp_2.jpg',
    'frame_3-timestamp_3.jpg',
    'frame_4-timestamp_4.jpg',
    'frame_5-timestamp_5.jpg',
    'frame_6-timestamp_6.jpg',
    'frame_7-timestamp_7.jpg',
    'frame_8-timestamp_8.jpg',
    'frame_9-timestamp_9.jpg',
    'frame_10-timestamp_10.jpg',
    'frame_11-timestamp_11.jpg',
    'frame_12-timestamp_12.jpg',
    'frame_13-timestamp_13.jpg',
    'frame_14-timestamp_14.jpg',
    'frame_15-timestamp_15.jpg',
    'frame_16-timestamp_16.jpg',
    'frame_17-timestamp_17.jpg',
    'frame_18-timestamp_18.jpg',
    'frame_19-timestamp_19.jpg',
    'frame_20-timestamp_20.jpg',
    'frame_21-timestamp_21.jpg',
    'frame_22-timestamp_22.jpg',
    'frame_23-timestamp_23.jpg',
    'frame_24-timestamp_24.jpg',
    'frame_25-timestamp_25.jpg',
    'frame_26-timestamp_26.jpg',
    'frame_27-timestamp_27.jpg',
    'frame_28-timestamp_28.jpg',
    'frame_29-timestamp_29.jpg',
    'frame_30-timestamp_30.jpg',
  ]
  for file in cam2_raw_files:
    fs.touch(cam2_raw_dir / Path(file))

  lidar_raw_files = [
    'frame_1-timestamp_10.pcd',
    'frame_2-timestamp_20.pcd',
    'frame_3-timestamp_30.pcd',
  ]
  for file in lidar_raw_files:
    fs.touch(lidar_raw_dir / Path(file))


def test_mfs_localFs_primaryLowFreq(tmp_path):
  """
  Creates a copy of test input data in the local filesystem,
  and tests frame matching on it

  This test focuses on a situation where the primary stream
  has a lower frame rate than the secondary streams
  """

  # Initialising local filesystem and creating input files
  fs = LocalFileSystem(auto_mkdir=True)
  dir_cam1_raw = tmp_path / 'cam1-raw'
  dir_cam1_use = tmp_path / 'cam1-use'
  dir_cam2_raw = tmp_path / 'cam2-raw'
  dir_cam2_use = tmp_path / 'cam2-use'
  dir_lidar_raw = tmp_path / 'lidar-raw'
  dir_lidar_use = tmp_path / 'lidar-use'
  create_input_data(fs, dir_cam1_raw, dir_cam2_raw, dir_lidar_raw)

  # Invoking the mfs solution
  frame_matcher = mfs.MultiStreamFrameMatcher(
    fs,
    [
      {
        'input_dirpath': str(dir_lidar_raw),
        'output_dirpath': str(dir_lidar_use),
        'filename_mask': 'frame_{fnum}-timestamp_{ts}.pcd',
        'timestamp_key': 'ts'
      },
      {
        'input_dirpath': str(dir_cam1_raw),
        'output_dirpath': str(dir_cam1_use),
        'filename_mask': 'frame_{fnum}-timestamp_{ts}.jpg',
        'timestamp_key': 'ts'
      },
      {
        'input_dirpath': str(dir_cam2_raw),
        'output_dirpath': str(dir_cam2_use),
        'filename_mask': 'frame_{fnum}-timestamp_{ts}.jpg',
        'timestamp_key': 'ts'
      },
    ],
    str(dir_lidar_raw),
    'after'
  )
  frame_matcher.arrange_frames()

  # Inspecting the output files/tree
  ideal_cam1_use_files = [
    'frame_1-timestamp_10.pcd!frame_5-timestamp_10.jpg',
    'frame_2-timestamp_20.pcd!frame_11-timestamp_22.jpg',
    'frame_3-timestamp_30.pcd!frame_15-timestamp_29.jpg',
  ]
  ideal_cam2_use_files = [
    'frame_1-timestamp_10.pcd!frame_10-timestamp_10.jpg',
    'frame_2-timestamp_20.pcd!frame_20-timestamp_20.jpg',
    'frame_3-timestamp_30.pcd!frame_30-timestamp_30.jpg',
  ]
  ideal_lidar_use_files = [
    'frame_1-timestamp_10.pcd',
    'frame_2-timestamp_20.pcd',
    'frame_3-timestamp_30.pcd',
  ]
  cam1_use_files = list_dir_files(fs, dir_cam1_use)
  cam2_use_files = list_dir_files(fs, dir_cam2_use)
  lidar_use_files = list_dir_files(fs, dir_lidar_use)

  assert set(lidar_use_files) == set(ideal_lidar_use_files)
  assert set(cam1_use_files) == set(ideal_cam1_use_files)
  assert set(cam2_use_files) == set(ideal_cam2_use_files)


def test_mfs_localFs_primaryHighFreq(tmp_path):
  """
  Creates a copy of test input data in the local filesystem,
  and tests frame matching on it

  This test focuses on a situation where the primary stream
  has a higher frame rate than (at least 1 of) the
  secondary streams
  """

  # Initialising local filesystem and creating input files
  fs = LocalFileSystem(auto_mkdir=True)
  dir_cam1_raw = tmp_path / 'cam1-raw'
  dir_cam1_use = tmp_path / 'cam1-use'
  dir_cam2_raw = tmp_path / 'cam2-raw'
  dir_cam2_use = tmp_path / 'cam2-use'
  dir_lidar_raw = tmp_path / 'lidar-raw'
  dir_lidar_use = tmp_path / 'lidar-use'
  create_input_data(fs, dir_cam1_raw, dir_cam2_raw, dir_lidar_raw)

  # Invoking the mfs solution
  frame_matcher = mfs.MultiStreamFrameMatcher(
    fs,
    [
      {
        'input_dirpath': str(dir_lidar_raw),
        'output_dirpath': str(dir_lidar_use),
        'filename_mask': 'frame_{fnum}-timestamp_{ts}.pcd',
        'timestamp_key': 'ts'
      },
      {
        'input_dirpath': str(dir_cam1_raw),
        'output_dirpath': str(dir_cam1_use),
        'filename_mask': 'frame_{fnum}-timestamp_{ts}.jpg',
        'timestamp_key': 'ts'
      },
      {
        'input_dirpath': str(dir_cam2_raw),
        'output_dirpath': str(dir_cam2_use),
        'filename_mask': 'frame_{fnum}-timestamp_{ts}.jpg',
        'timestamp_key': 'ts'
      },
    ],
    str(dir_cam1_raw),
    'after'
  )
  # pdb.set_trace()
  frame_matcher.arrange_frames()

  # Inspecting the output files/tree
  ideal_cam1_use_files = [
    'frame_1-timestamp_2.jpg',
    'frame_2-timestamp_4.jpg',
    'frame_3-timestamp_6.jpg',
    'frame_4-timestamp_8.jpg',
    'frame_5-timestamp_10.jpg',
    'frame_6-timestamp_12.jpg',
    'frame_7-timestamp_14.jpg',
    'frame_8-timestamp_16.jpg',
    'frame_9-timestamp_18.jpg',
    'frame_11-timestamp_22.jpg',
    'frame_12-timestamp_24.jpg',
    'frame_13-timestamp_26.jpg',
    'frame_14-timestamp_28.jpg',
    'frame_15-timestamp_29.jpg',
    'frame_16-timestamp_32.jpg',
  ]
  ideal_cam2_use_files = [
    'frame_1-timestamp_2.jpg!frame_2-timestamp_2.jpg',
    'frame_2-timestamp_4.jpg!frame_4-timestamp_4.jpg',
    'frame_3-timestamp_6.jpg!frame_6-timestamp_6.jpg',
    'frame_4-timestamp_8.jpg!frame_8-timestamp_8.jpg',
    'frame_5-timestamp_10.jpg!frame_10-timestamp_10.jpg',
    'frame_6-timestamp_12.jpg!frame_12-timestamp_12.jpg',
    'frame_7-timestamp_14.jpg!frame_14-timestamp_14.jpg',
    'frame_8-timestamp_16.jpg!frame_16-timestamp_16.jpg',
    'frame_9-timestamp_18.jpg!frame_18-timestamp_18.jpg',
    'frame_11-timestamp_22.jpg!frame_22-timestamp_22.jpg',
    'frame_12-timestamp_24.jpg!frame_24-timestamp_24.jpg',
    'frame_13-timestamp_26.jpg!frame_26-timestamp_26.jpg',
    'frame_14-timestamp_28.jpg!frame_28-timestamp_28.jpg',
    'frame_15-timestamp_29.jpg!frame_29-timestamp_29.jpg',
    'frame_16-timestamp_32.jpg!frame_30-timestamp_30.jpg',
  ]
  ideal_lidar_use_files = [
    'frame_1-timestamp_2.jpg!frame_1-timestamp_10.pcd',
    'frame_2-timestamp_4.jpg!frame_1-timestamp_10.pcd',
    'frame_3-timestamp_6.jpg!frame_1-timestamp_10.pcd',
    'frame_4-timestamp_8.jpg!frame_1-timestamp_10.pcd',
    'frame_5-timestamp_10.jpg!frame_1-timestamp_10.pcd',
    'frame_6-timestamp_12.jpg!frame_1-timestamp_10.pcd',
    'frame_7-timestamp_14.jpg!frame_1-timestamp_10.pcd',
    'frame_8-timestamp_16.jpg!frame_2-timestamp_20.pcd',
    'frame_9-timestamp_18.jpg!frame_2-timestamp_20.pcd',
    'frame_11-timestamp_22.jpg!frame_2-timestamp_20.pcd',
    'frame_12-timestamp_24.jpg!frame_2-timestamp_20.pcd',
    'frame_13-timestamp_26.jpg!frame_3-timestamp_30.pcd',
    'frame_14-timestamp_28.jpg!frame_3-timestamp_30.pcd',
    'frame_15-timestamp_29.jpg!frame_3-timestamp_30.pcd',
    'frame_16-timestamp_32.jpg!frame_3-timestamp_30.pcd',
  ]
  cam1_use_files = list_dir_files(fs, dir_cam1_use)
  cam2_use_files = list_dir_files(fs, dir_cam2_use)
  lidar_use_files = list_dir_files(fs, dir_lidar_use)

  assert set(lidar_use_files) == set(ideal_lidar_use_files)
  assert set(cam1_use_files) == set(ideal_cam1_use_files)
  assert set(cam2_use_files) == set(ideal_cam2_use_files)


def test_filename_timeParsing():
  """
  Tests the timestamp parsing function used in mfs
  """

  # Unix timestamp in s
  tstamp_1 = '10'
  time_1 = mfs.parse_time(tstamp_1)
  assert time_1 == datetime.datetime(1970, 1, 1, 0, 0, 10, 0, datetime.timezone.utc)

  # Unix timestamp in s with microseconds included
  tstamp_2 = '1234567890.1234'
  time_2 = mfs.parse_time(tstamp_2)
  assert time_2 == datetime.datetime(2009, 2, 13, 23, 31, 30, 123400, tzinfo=datetime.timezone.utc)

  # ISO timestamp
  tstamp_3 = '2023-02-03T11:10:26+00:00'
  time_3 = mfs.parse_time(tstamp_3)
  assert time_3 == datetime.datetime(2023, 2, 3, 11, 10, 26, 0, tzinfo=datetime.timezone.utc)

  # ISO timestamp with different timezone
  tstamp_4 = '2023-02-03T11:10:26+05:30'
  time_4 = mfs.parse_time(tstamp_4)
  assert time_4 == datetime.datetime(2023, 2, 3, 5, 40, 26, 0, tzinfo=datetime.timezone.utc)
