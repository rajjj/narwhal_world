from nartools.format_conv import image_raster_to_vector as r2v
from PIL import Image

TEST_IMAGE_PATH = "tests/assets/raster_to_vector_test_image.png"
POLYS_EXPECTED = [
  {
    "label": "white",
    "shell": [[1057.0, 422.0], [1057.0, -0.0], [-0.0, 0.0], [0.0, 422.0]],
    "holes": [
      [
        [196.0, 285.0],
        [91.0, 284.0],
        [91.0, 199.0],
        [48.0, 198.0],
        [49.0, 51.0],
        [134.0, 51.0],
        [135.0, 145.0],
        [197.0, 146.0],
      ],
      [[730.0, 308.0], [446.0, 308.0], [445.0, 72.0], [730.0, 71.0]],
    ],
  },
  {
    "label": "white",
    "shell": [
      [110.0, 97.0],
      [110.0, 87.0],
      [94.0, 87.0],
      [93.0, 78.0],
      [82.0, 78.0],
      [82.0, 86.0],
      [75.0, 87.0],
      [75.0, 97.0],
      [82.0, 98.0],
      [82.0, 108.0],
      [93.0, 108.0],
      [94.0, 97.0],
    ],
    "holes": [],
  },
  {
    "label": "white",
    "shell": [[152.0, 270.0], [152.0, 229.0], [122.0, 229.0], [122.0, 270.0]],
    "holes": [],
  },
  {
    "label": "grey",
    "shell": [[730.0, 307.0], [730.0, 72.0], [446.0, 72.0], [446.0, 307.0]],
    "holes": [],
  },
  {
    "label": "black",
    "shell": [
      [196.0, 284.0],
      [196.0, 146.0],
      [134.0, 145.0],
      [134.0, 52.0],
      [49.0, 52.0],
      [49.0, 198.0],
      [92.0, 199.0],
      [92.0, 284.0],
    ],
    "holes": [
      [
        [110.0, 98.0],
        [94.0, 98.0],
        [93.0, 109.0],
        [82.0, 109.0],
        [81.0, 98.0],
        [74.0, 97.0],
        [74.0, 87.0],
        [81.0, 86.0],
        [82.0, 77.0],
        [93.0, 77.0],
        [94.0, 86.0],
        [111.0, 87.0],
      ],
      [[152.0, 271.0], [121.0, 270.0], [122.0, 228.0], [153.0, 229.0]],
    ],
  },
]


def color_map(col):
  """
  Color to label mapping function
  """

  if col == (0, 0, 0):
    return "black"
  elif col == (128, 128, 128):
    return "grey"
  elif col == (255, 255, 255):
    return "white"
  else:
    return "OTHER"


def test_r2v():
  """
  Tests the raster to vector solution on a simple sample image
  """

  converter = r2v.ImagePolygonizer(color_map, 0.999, 1, 0, 255, 1, 1)

  img = Image.open(TEST_IMAGE_PATH)
  polys_found = converter.polygonize_image(img)

  assert polys_found == POLYS_EXPECTED
