"""
Module to find timestamps in frame file names,
then use them to match frames across different streams
(lidar, cameras, etc.) which have produced frames at
different rates

Note:
  1. The AWS credentials need to have been set by the
    user/caller prior to using this module
  2. Matching frames based on closest available timestamps
    might still leave you with time offsets between the
    primary frame and the various secondary frames, meaning
    that any cross-sensor projections might not produce
    accurate results
"""


from typing import List, Dict
from pathlib import Path
import parse
import datetime
import dateutil.parser
from fsspec.spec import AbstractFileSystem # imported just for type hinting - is there a better way to do this while avoiding the import?


def parse_time(timestamp: str) -> datetime.datetime:
  """
  Takes a string timestamp and returns a datetime object

  Args:
    timestamp (str): The timestamp string to parse
  """

  try:
    try:
      # First try to parse the time as a Unix timestamp in UTC
      unix_time_float = float(timestamp)
      time = datetime.datetime.fromtimestamp(unix_time_float, tz=datetime.timezone.utc)
    except:
      # If that doesn't work, try default string parsing behaviour of dateutil.parser.parse
      time = dateutil.parser.parse(timestamp)
  except:
    # If no parsing attempt above is successful
    raise ValueError('Timestamp is either invalid or not in a format that nartools3d can currently parse')

  ## Older approach
  # try:
  #   # Default string parsing behaviour of dateutil.parser.parse
  #   time = dateutil.parser.parse(timestamp)
  # except dateutil.parser._parser.ParserError as parse_err:   # type: ignore
  #   # Now try to parse the time as a Unix timestamp in UTC
  #   unix_time_float = float(timestamp)
  #   time = datetime.datetime.fromtimestamp(unix_time_float)  # , tz=datetime.timezone.utc)
  # except:
  #   raise ValueError('Timestamp is either invalid or not in a format that nartools3d can currently parse')

  return time

def get_time_diff(timestamp_to: str, timestamp_from: str) -> datetime.timedelta:
  """
  Interprets two timestamps (trying to auto-guess timestamp format
  as well as possible) and returns their difference as a timedelta
  object

  Args:
    timestamp_to (str): The timestamp which is taken to be later
    timestamp_from (str): The timestamp which is taken to be earlier
  """

  time_to = parse_time(timestamp_to)
  time_from = parse_time(timestamp_from)
  time_diff = time_to - time_from

  return time_diff

def get_time_from_filename(filename: str, filename_mask: str, timestamp_key: str) -> datetime.datetime:
  """
  Parses the timestamp from a filename and returns the time
  a datetime object

  Args:
    filename (str): The name of the file from which to
      extract the timestamp
    filename_mask (str): A mask that captures the structure
      of `filename`
    timestamp_key (str): The key in the mask that
      represents the timestamp
  E.g. filename = 'frame_001-timestamp_12:34:56.0123.pcd', filename_mask = 'frame_{fnum}-timestamp_{ts}.pcd', timestamp_key = 'ts'
  """

  parsed = parse.parse(filename_mask, filename).named  # type: ignore
  timestamp = parsed[timestamp_key]
  time = parse_time(timestamp)

  return time


class MultiStreamFrameMatcher:
  """
  Matches frames across multiple streams (lidar frames,
  camera/video feeds, etc.) by timestamp.
  Considers a primary stream, and for each frame of that
  stream, selects frames from other streams that lie
  closest in time to the primary frame.
  """

  def __init__(self, fs: AbstractFileSystem, streams: List[Dict], main_stream_dirpath: str, tiebreaker_pref: str = 'after', sep: str = '!') -> None:
    """
    Constructor

    Args:
      fs (AbstractFileSystem): fsspec-compliant object representing the filesystem to use. This could, for example,
        be `fs` if you have an object narcon of `libnar.libnar.NarCon` with your S3 credentials loaded.
      streams: A list of dicts to capture metadata for
        all streams (structure described below).
      main_stream_dirpath (str): Path to the directory
        representing the primary stream (must be the same as
        the corresponding `input_dirpath` entry in `streams`)
      tiebreaker_pref (str): Tiebreaker preference to
        apply when there are two frames of a secondary
        stream that are equidistant from a primary frame.
        Should be 'after' or 'before'; defaults to 'after'.
      sep (str): The separator to use between the primary
        frame filename and the secondary frame filename.
        The output secondary frames will have their primary
        frame filenames and this separator prepended to their
        filenames to ensure uniqueness and consistency.
        Defaults to '!'.

    Expected structure of `streams`:
    [
      {
        'input_dirpath': 'sama-client-assets/361/testing-3d/task1/lidar_raw',
        'output_dirpath': 'sama-client-assets/361/testing-3d/task1/lidar_selected',
        'filename_mask': 'frame_{fnum}-timestamp_{ts}.pcd',
        'timestamp_key': 'ts'
      },
      ...
    ]
    ^ Here, `output_dirpath` is optional for the primary stream -
    an exact copy of all frames will be made into the output
    dir if specified, otherwise, no extra output dir will be
    created for the primary stream and the input dir may be used
    as-is for task creation
    """

    self.fs = fs
    self.streams = streams
    self.main_stream_dirpath = main_stream_dirpath
    self.tiebreaker_pref = tiebreaker_pref
    self.sep = sep

    self.__validate_instance_variables()
    self.__add_input_listings()
  
  def __validate_instance_variables(self) -> None:
    """
    Validates the current object's instance variables
    and raises errors if necessary
    """

    if self.tiebreaker_pref not in ['before', 'after']:
      raise ValueError(
        'The tiebreaker preference must be either "before"'
        ' (prefer earlier frames) or "after" (prefer later'
        ' frames)'
      )
    
    prim_stream_found = False
    reqd_sec_stream_keys = {'input_dirpath', 'output_dirpath', 'filename_mask', 'timestamp_key'}
    reqd_prim_stream_keys = {'input_dirpath', 'filename_mask', 'timestamp_key'}
    for stream in self.streams:
      keys = set(stream.keys())
      if keys in [reqd_prim_stream_keys, reqd_sec_stream_keys] and Path(self.main_stream_dirpath) == Path(stream['input_dirpath']):
        prim_stream_found = True
      elif keys != reqd_sec_stream_keys:
        raise ValueError('Not all stream dicts have the requisite keys')
    if not prim_stream_found:
      raise ValueError('Primary stream denoted by `main_stream_dirpath` not found in `streams`')

  def __add_input_listings(self) -> None:
    """
    Adds input dir frame listings (file names + parsed
    times) for each stream
    """

    for stream in self.streams:
      raw_filenames = [
        Path(filepath).name
        for filepath in self.fs.ls(stream['input_dirpath'])  # type: ignore
      ]
      stream['input_dir_ls'] = [
        {
          'filename': filename,
          'time': get_time_from_filename(filename, stream['filename_mask'], stream['timestamp_key'])
        }
        for filename in raw_filenames
      ]

  def get_closest_frame(self, time: datetime.datetime, stream: Dict) -> Dict:
    """
    Given a time, finds the closest frame in
    a stream.

    Args:
      time (datetime.datetime): The time to which to
        find the nearest frame.
      stream (Dict): The stream from which to pick the
        closest frame (filename + time)
    """

    # Dicts to track nearest frames from each direction
    # Structure:
    # {
    #   'filename': ...,
    #   'time': ...,
    # }
    nearest_prev = None # type: ignore
    nearest_next = None # type: ignore
    # Corresponding time differences
    # (these would be minimised in abs val)
    prev_diff_min = None # type: ignore
    next_diff_min = None # type: ignore

    zero_diff = datetime.timedelta(0)

    for frame in stream['input_dir_ls']:
      file_time = frame['time']
      time_diff = time - file_time

      if time_diff == zero_diff:
        # Perfect match!
        return frame
      elif time_diff < zero_diff:
        # Secondary frame comes after primary frame
        if nearest_next is None or time_diff > next_diff_min: # or abs(time_diff) < abs(next_diff_min):
          nearest_next = frame # type: Dict
          next_diff_min = time_diff # type: datetime.timedelta
      else: # time_diff > zero_diff
        # Secondary frame comes before primary frame
        if nearest_prev is None or time_diff < prev_diff_min: # or abs(time_diff) < abs(prev_diff_min):
          nearest_prev = frame # type: Dict
          prev_diff_min = time_diff # type: datetime.timedelta

    # Time offset may be useful in the future
    if nearest_next is not None:
      nearest_next['time_delta'] = next_diff_min
    if nearest_prev is not None:
      nearest_prev['time_delta'] = prev_diff_min

    # At most one of these should be None;
    # if so, we return the other as that's
    # the only available 'nearest' frame
    if nearest_prev is None:
      # ^ i.e., primary frame is earlier
      # than any available secondary frame
      return nearest_next
    if nearest_next is None:
      # ^ i.e., primary frame is later
      # than any available secondary frame
      return nearest_prev

    # Return whichever out of next and prev
    # is closer to the primary frame
    if abs(next_diff_min) < abs(prev_diff_min):
      return nearest_next
    elif abs(next_diff_min) > abs(prev_diff_min):
      return nearest_prev
    else: # equidistant, apply tiebreaker
      if self.tiebreaker_pref == 'before':
        return nearest_prev
      else:
        return nearest_next

  def arrange_frames(self) -> None:
    """
    Copies frames from the input directories into their
    corresponding output directories by matching the
    appropriate secondary frames to each primary frame
    based on timestamp
    """

    sec_streams = []
    prim_stream = dict()
    for stream in self.streams:
      if Path(stream['input_dirpath']) == Path(self.main_stream_dirpath):
        prim_stream = stream
      else:
        stream['output_dir_ls'] = []
        sec_streams.append(stream)

    if 'output_dirpath' in prim_stream.keys():
      for prim_frame in prim_stream['input_dir_ls']:
        prim_filename = prim_frame['filename']
        self.fs.cp( # type: ignore
          str(Path(prim_stream['input_dirpath']) / Path(prim_filename)),
          str(Path(prim_stream['output_dirpath']) / Path(prim_filename))
        )

    for prim_frame in prim_stream['input_dir_ls']:
      prim_filename = prim_frame['filename']
      prim_time = prim_frame['time']

      for stream in sec_streams:
        sec_frame = self.get_closest_frame(prim_time, stream)
        sec_frame['output_filename'] = prim_filename + self.sep + sec_frame['filename']
        stream['output_dir_ls'].append(sec_frame)

        self.fs.cp( # type: ignore
          str(Path(stream['input_dirpath']) / Path(sec_frame['filename'])),
          str(Path(stream['output_dirpath']) / Path(sec_frame['output_filename']))
        )
