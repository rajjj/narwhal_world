import numpy as np
from nartools.geometry_utils import geo_utils_2d3d as gu


def test_cuboid_projection_3d_to_2d_undistorted():
    """
    Uses predefined calibration ad cuboid coord data to check projection code
    """

    calib = {
        "rotation_x": 0.439509,
        "rotation_y": -0.509884,
        "rotation_z": 0.551752,
        "rotation_w": -0.492361,
        "x": 0.06277131314550065,
        "y": 1.0560002862463875,
        "z": -0.3176840532565925,
        "f_x": 1561.598388671875,
        "f_y": 1554.842041015625,
        "c_x": 961.2638259343948,
        "c_y": 526.4888530443131,
    }
    width = 1920
    height = 1080

    points_3d = [
        [16.716, -0.646, 1.401],
        [16.045, -0.682, 4.231],
        [16.203, 1.834, 1.326],
        [15.534, 1.792, 4.152],
        [32.09, 2.646, 5.092],
        [31.419, 2.609, 7.922],
        [31.577, 5.126, 5.017],
        [30.908, 5.083, 7.843],
    ]
    points_2d_expected = [
        [916.0364313291681, 514.0186609034274],
        [921.9673002446792, 241.03125566651312],
        [680.0321933631499, 517.0407851652996],
        [680.959728028991, 229.9606459183781],
        [677.7144887864854, 412.93108449976734],
        [677.8882313542027, 269.40326116119587],
        [549.9227571620303, 411.7679951540069],
        [548.7923362256964, 264.54783768861716],
    ]

    conv = gu.Converter2D3D(calib, (width, height))
    points_2d = gu.GeometryUtils.project_shape_3d_to_2d(points_3d, conv)

    assert np.allclose(points_2d, points_2d_expected)
