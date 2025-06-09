"""
Module to convert a 2D raster mask into a list of polygons by extracting shapes according to colour

Usage:
  - Create an object of the `ImagePolygonizer` class with your desired configuration parameters (colour to label map, tolerance, etc.)
  - Call the object's `polygonize_image` method, with a PIL `Image` object as argument
  - The output will be a list of dicts capturing information about the polygons found in the image
  - Output structure:
      [
        {
          'shell': <shell coords>,
          'holes': [
            <hole 1 coords>,
            <hole 2 coords>,
            ...
          ],
          'label': <label according to colour>
        },
        ...
      ]
"""


from typing import List, Dict, Any, Union, Callable, Tuple
from PIL import Image, ImageOps
from shapely.geometry import Polygon
from skimage.measure import find_contours
import numpy as np
from copy import deepcopy


class AnnotatedPolygon:
  """
  This class describes annotated polygons found in the image with a shell (external boundary), holes (internal boundaries) and a label (what the polygon represents)
  """

  def __init__(self, label: str, shell: List[list], holes: List[List[list]] = []) -> None:
    self.label = label
    self.shell = shell
    self.holes = holes

  def as_dict(self) -> Dict[str, Union[str, List[list], List[List[list]]]]:
    """
    Returns the current object as a (JSON-serializable) Python dict
    """
    return {
      'label': deepcopy(self.label),
      'shell': deepcopy(self.shell),
      'holes': deepcopy(self.holes)
    }


def listize_polygon(poly: Polygon) -> List[list]:
  """
  Returns the exterior coords of a shapely polygon as a list of [x, y] pixel coordinates

  Args:
    poly (Polygon): A shapely polygon to get the coords of
  """

  return [
    list(point) for point in poly.exterior.coords[:-1]
  ]


def pack_polygon_shells_and_holes(poly_list: List[Polygon], label: str) -> List[AnnotatedPolygon]:
  """
  Packs a list of unorganised shapely polygons into a list of annotated polygons (defined as having a shell, some holes, and a label)

  The largest polygon is assumed to be a shell, and as we move inwards we alternate between holes and shells. In other words, polygons that lie within an even number of other polygons (0, 2, 4...) are shells and those that lie within an odd number of other polygons are holes.

  Each hole is associated with the smallest shell that contains it.

  Args:
    poly_list (List[Polygon]): A list of shapely Polygon objects
    label (str): The label to assign to the AnnotatedPolygon objects
  """

  poly_count = len(poly_list)

  # Separating out shells and holes
  groups = [] # type: List[Dict]
  # ^ List of all shells found in the input, started off as dicts similar to annotated polygon objects (but with actual shapely polygons rather than coord lists)
  holes = [] # type: List[List[list]]
  # ^ List of all holes found in the input (not yet grouped)
  for i in range(poly_count):
    # Checking whether this polygon is a shell or a hole
    is_shell = True
    for j in range(poly_count):
      if i != j and poly_list[j].contains(poly_list[i]):
        is_shell = not is_shell

    if is_shell:
      groups.append(
        # AnnotatedPolygon(label='', shell=poly_list[i], holes=[])
        {
          'shell': poly_list[i],
          'holes': []
        }
      )
    else:
      holes.append(poly_list[i])

  # Clubbing each hole with the smallest shell
  # that contains it
  for hole in holes:
    # Finding the appropriate shell to associate this hole
    # with
    dest_group = None # the proper destination group to add this hole to
    dest_shell_area = None # the area of the shell of the destination group
    for group in groups:
      shell = group['shell']
      if shell.contains(hole):
        if dest_group == None or shell.area < dest_shell_area:
          dest_group = group
          dest_shell_area = shell.area

    if dest_group != None:
      dest_group['holes'].append(hole)

  # Generating the output list of labelled polygons
  # from the collected shells and holes
  polygons = []
  for group in groups:
    polygons.append(
      AnnotatedPolygon(
        shell = listize_polygon(group['shell']),
        holes = [listize_polygon(hole) for hole in group['holes']],
        label = label
      )
    )

  return polygons


class ImagePolygonizer:
  """
  Defines methods to parse polygons from a raster mask
  """

  def __init__(
    self,
    color_label_map: Callable[[Tuple[int]], str],
    cont_val: float = 0.999,
    poly_tol: float = 1,
    color_min: int = 0,
    color_max: int = 255,
    deci_places: int = 1,
    border: int = 1
  ) -> None:
    """
    Constructor to set config params for image processing
    
    Args:
      color_label_map (Callable[[Tuple[int]], str]): A function that maps image colours to labels.
      cont_val (float): The value to use when finding contours. Defaults to 0.999, should not normally need to be changed.
      poly_tol (float): The tolerance to use for simplifying polygons (removing redundant points that don't represent real vertices). This is the max allowed discrepancy (in pixels) between the originally extracted and simplified polygons. Defaults to 1.
      color_min (int): The minimum value of a color coordinate. Defaults to 0
      color_max (int): The maximum value of a color coordinate. Defaults to 255
      deci_places (int): Number of decimal places to round the polygon coords to. Defaults to 1
      border (int): Thickness (in number of pixels) of the border to add to the image. This is needed internally to simplify processing. Defaults to 1, should not normally need to be changed.
    """
    self.color_label_map = color_label_map
    self.cont_val = cont_val
    self.poly_tol = poly_tol
    self.color_min = color_min
    self.color_max = color_max
    self.deci_places = deci_places
    self.border = border

  def __get_new_color(self, color_list: List[tuple]) -> Union[tuple, None]:
    """
    Returns an (r, g, b) not present in the list of colours given, or None if this list has all possible values as defined by the bounds [by default this would be all the 256^3 values from (0, 0, 0) to (255, 255, 255)]

    Args:
      color_list (List[tuple]): A list of tuples describing colors as RGB values
    """
    min_val = self.color_min
    max_val = self.color_max
    vals = list(range(min_val, max_val + 1))
    for i in vals:
      for j in vals:
        for k in vals:
          color = (i, j, k)
          if color not in color_list:
            return color
    return None

  def __clean_poly_coords(self, poly: AnnotatedPolygon, xshift: float, yshift: float) -> AnnotatedPolygon:
    """
    Cleans up the coords of a polygon (as we define it: shell + holes + label). Shifts its coords and rounds them to a specified number of decimal places.

    Args:
      poly (AnnotatedPolygon): The polygon to be cleaned
      xshift (float): Value to add to all x coords
      yshift (float): Value to add to all y coords
    """

    deci_places = self.deci_places
    rnd = lambda x: round(x, deci_places)

    return AnnotatedPolygon(
      shell = [
        [rnd(point[0] + xshift), rnd(point[1] + yshift)]
        for point in poly.shell
      ],
      holes = [
        [
          [rnd(point[0] + xshift), rnd(point[1] + yshift)]
          for point in hole
        ]
        for hole in poly.holes
      ],
      label = poly.label
    )

  def polygonize_image(self, img: Image.Image) -> List[Dict[str, Any]]:
    """
    Returns the polygons extracted from a PIL Image

    Args:
      img_arr (Image): The RGB image to extract polygons from
    """
    # Setting configs
    border = self.border
    cont_val = self.cont_val
    poly_tol = self.poly_tol

    img_colors = [color_data[1][:3] for color_data in img.getcolors()] # type: ignore
    # ^ extracting image colours as (r, g, b)
    
    # adding border, coords will have to be shifted later
    img = ImageOps.expand(img, border=border, fill=self.__get_new_color(img_colors)) # type: ignore
    img_arr = np.asarray(img)
    img_arr = np.transpose(img_arr, (1, 0, 2))
    # ^ to align with PNG coord sys

    # polygonizing new image, but for colors of original image only
    img_polys = [] # type: List[AnnotatedPolygon]
    for color in img_colors:
      # Building a mask of just the current color
      x_dim, y_dim = img_arr.shape[:2]
      mask_arr = np.zeros((x_dim, y_dim))
      for x in range(x_dim):
        for y in range(y_dim):
          pix = img_arr[x][y]
          if tuple(pix[:3]) == color:
            mask_arr[x][y] = 1
          # else:
          #   mask_arr[x][y] = 0
   
      # Building a list of polygons for the current color
      # and concatenating it to the grand list
      contours = find_contours(mask_arr, cont_val)
      mask_polys = [Polygon(con[:-1]).simplify(poly_tol) for con in contours]
      img_polys += pack_polygon_shells_and_holes(mask_polys, self.color_label_map(color))
   
    # shifting coords back to remove the effects of bordering,
    # and returning annotated polygons in their dict forms
    return [
      self.__clean_poly_coords(poly, -border, -border).as_dict()
      for poly in img_polys
    ]

# TODO: use parallel processing to speed things up
