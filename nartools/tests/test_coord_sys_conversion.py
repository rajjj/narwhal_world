import numpy as np
from nartools.geometry_utils.coord_sys_conversion import CoordSysConverter, ECEFCoords, GeodeticCoords


def test_geodetic_to_ecef():
    """
    Here we convert the coordinates of
    Parc des Buttes-Chaumont from geodetic (LLA)
    to ECEF coordinates
    """

    geo_coords = GeodeticCoords(
        lat_degN=48.8800,
        long_degE=2.3831,
        alt_mUp=124.5089,
    )
    expected_x_m = 4198945
    expected_y_m = 174747
    expected_z_m = 4781887

    csc = CoordSysConverter()
    csc.load_coords(geo_coords)
    ecef_coords = csc.convert_to_type(ECEFCoords)

    assert np.allclose([ecef_coords.x, ecef_coords.y, ecef_coords.z], [expected_x_m, expected_y_m, expected_z_m])
