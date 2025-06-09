"""
Module to find frame numbers in frame file names,
then pad them with leading zeros to ensure proper
sorting (SamaHub arranges lidar/video frames in an
ascending lexicographic order of their filenames)

Inputs:
  - S3 path for input dir as "{bucket}/{path_in_bucket}"
  - S3 path for output dir as "{bucket}/{path_in_bucket}"
  - A string mask to understand how to extract
    the frame number from the file name
  - A digit count to pad up to

Note: The AWS credentials need to have been set by the user/caller
prior to using this module

Usage example:
  >>> from libnar import libnar
  >>> narcon = libnar.NarCon()
  >>> from nartools3d.file_manip import zero_pad_frame_nums as zpf
  >>> fixer = zpf.FrameNamingFixer(
  ...   narcon.fs,
  ...   'sama-client-assets/361/testing/frame_num_padding_test/unpadded',
  ...   'sama-client-assets/361/testing/frame_num_padding_test/padded/',
  ...   'lidar_{lnum}-frame_{fnum}.pcd', 'fnum', 4
  ... )
  >>> fixer.generate_fixed_dir()

  This reads the input dir (files: "lidar_1-frame_23.pcd", "lidar_1-frame_2.pcd", "lidar_1-frame_1023.pcd")
  and produces a copy of it with the naming fixed as the output dir
  (files: "lidar_1-frame_0023.pcd", "lidar_1-frame_0002.pcd", "lidar_1-frame_1023.pcd")
"""


import parse
from pathlib import Path, PurePath
from fsspec.spec import AbstractFileSystem # imported just for type hinting - is there a better way to do this while avoiding the import?


def get_padded_filename(filename_mask: str, frame_num_key: str, raw_filename: str, digit_count: int) -> str:
  """
  This function generates an appropriately padded version of a filename

  Args:
    filename_mask (str): the mask to used to describe the structure the filename
    frame_num_key (str): the key in the mask used to refer to the frame number -- note that although the key is enclosed within braces in the mask, it must be specify without the braces here
    raw_filename (str): the name of the original file, that needs to be padded
    digit_count (int): the number of digits to pad the frame number up to (i.e., we add leading 0s to ensure that the padded frame number ultimately has this number of digits)

  E.g. mask: "lidar_1-frame_{frame_num}.pcd", key: "frame_num", raw: "lidar_1-frame_23.pcd", digit count: 4 => result: "lidar_1-frame_0023.pcd"
  """

  parsed = parse.parse(filename_mask, raw_filename).named # type: ignore
  frame_num_padded = parsed[frame_num_key].zfill(digit_count)
  parsed[frame_num_key] = frame_num_padded

  return filename_mask.format(**parsed)


class FrameNamingFixer:
  """
  Fixes the naming of the frame file names
  in a given directory representing a video
  or lidar scene by padding the frame number
  in all file names with leading zeros up
  to a specified number of digits
  """

  def __init__(self, fs: AbstractFileSystem, input_dirpath: str, output_dirpath: str, filename_mask: str, frame_num_key: str, frame_num_length: int):
    """
    Constructor

    Args:
      fs (AbstractFileSystem): fsspec-compliant object representing the filesystem to use. This could, for example,
        be `narcon.fs` if you have an object narcon of `libnar.libnar.NarCon` with your S3 credentials loaded.
      input_dirpath (str): The directory where the input files are located.
      output_dirpath (str): The directory where the output files should be saved.
      filename_mask (str): The mask describing the structure of the filename. For example, if the filename
        is "lidar_1-frame_23.pcd", then the mask could be "lidar_{lnum}-frame_{fnum}.pcd".
      frame_num_key (str): The key in the filename that indicates the frame number. In the above example, this would be "fnum".
      frame_num_length (int): The number of digits to pad the frame number up to
        (i.e., we add leading 0s to ensure that the padded frame number ultimately has this number of digits)
    """

    self.fs = fs
    self.input_dirpath = input_dirpath
    self.output_dirpath = output_dirpath
    self.filename_mask = filename_mask
    self.frame_num_key = frame_num_key
    self.frame_num_length = frame_num_length

  def generate_fixed_dir(self):
    """
    Generates the output directory
    and populates it with files
    from the input directory but with
    the frame numbers padded in the
    file names
    """

    for raw_filepath in self.fs.ls(self.input_dirpath):
      raw_filename = PurePath(raw_filepath).name
      fixed_filename = get_padded_filename(
        self.filename_mask,
        self.frame_num_key,
        raw_filename,
        self.frame_num_length
      )
      self.fs.cp(
        str(Path(self.input_dirpath) / Path(raw_filename)),
        str(Path(self.output_dirpath) / Path(fixed_filename))
      )
