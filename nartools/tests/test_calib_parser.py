import numpy as np
from nartools.geometry_utils.calibrations import CalibrationParser, Pose
from pyquaternion import Quaternion


def check_calib_dicts_equality(dict1, dict2, tol=1e-6):
    # Assumes that the keys are the same for both dicts
    keys = list(dict1.keys())
    for key in keys:
        assert np.isclose(dict1[key], dict2[key])


def test_ext_mat_to_pose_dict():
    # In this example, we convert an extrinsic matrix into a pose dictionary
    # for the purpose of LiDAR fixed world calibrations. Note that the
    # `pose_is_inverse_of_ext` and `invert_transformation` switches may vary
    # depending on the client's/project's specifications.

    # Inputs
    lidar_ext_mat = [
        [0.9906866903385161, 0.1361612337859681, 0.0, 13190.221884986027],
        [-0.1361612337859681, 0.9906866903385161, 0.0, 2035.5891487898502],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    pose_dict_expected = {
        "x": 13190.221884986027,
        "y": 2035.5891487898502,
        "z": 0.0,
        "rotation_x": 0.0,
        "rotation_y": 0.0,
        "rotation_z": -0.06823968662546698,
        "rotation_w": 0.9976689557008668,
    }

    calib = CalibrationParser()
    calib.load_extrinsics_from_matrix(lidar_ext_mat, pose_is_inverse_of_ext=False, invert_transformation=False)
    pose_dict = calib.get_pose_dict()

    check_calib_dicts_equality(pose_dict, pose_dict_expected)


def test_ext_int_mats_to_proj_dict():
    # In this example, we convert a camera's intrinsic and extrinsic matrices,
    # and a LiDAR sensor's extrinsic matrix, into a projection dictionary
    # for the purpose of LiDAR-camera calibrations. Note that the
    # `pose_is_inverse_of_ext` and `invert_transformation` switches as well
    # as the method of forming the effective extrinsic matrix may vary
    # depending on the client's/project's specifications.

    # Inputs
    cam_int_mat = [[2598.949951171875, 0.0, 4612.0], [0.0, 2598.949951171875, 1672.0], [0.0, 0.0, 1.0]]
    lidar_ext_mat = [
        [0.999716347848037, 0.020942419883356968, 0.01134190878168716, -2.075],
        [-0.02094107224408732, 0.9997806834748455, -0.00023757912101209582, 0.0],
        [-0.011344396795372295, 0.0, 0.9999356502602301, 1.435],
        [0.0, 0.0, 0.0, 1.0],
    ]
    cam_ext_mat = [
        [0.03719363049167067, 0.016807586144820693, 0.9991667222735321, -0.845],
        [-0.9990700138150397, 0.022448929578289364, 0.03681240356734921, 0.18],
        [-0.021811495741132603, -0.9996066979611399, 0.01762691251357191, 0.92],
        [0.0, 0.0, 0.0, 1.0],
    ]
    proj_dict_expected = {
        "x": 1.2317240791987663,
        "y": 0.20571969948200128,
        "z": -0.5010590763243254,
        "rotation_x": -0.5016489380443311,
        "rotation_y": 0.4836047951211863,
        "rotation_z": -0.48677545554118606,
        "rotation_w": 0.5268058475163891,
        "f_x": 2598.949951171875,
        "f_y": 2598.949951171875,
        "c_x": 4612.0,
        "c_y": 1672.0,
    }

    net_ext_mat = np.linalg.inv(cam_ext_mat) @ lidar_ext_mat

    calib = CalibrationParser()
    calib.load_extrinsics_from_matrix(net_ext_mat, invert_transformation=False, pose_is_inverse_of_ext=True)
    calib.load_intrinsics_from_matrix(cam_int_mat)
    proj_dict = calib.get_projection_dict()

    check_calib_dicts_equality(proj_dict, proj_dict_expected)


def test_pose_combination():
    """
    In this example, we use the `combine` method of
    the `Pose` class to combine poses
    """

    client_lidar_pose = {"translation": [0, 0, 0], "quaternion": [0, 0, 0, 1]}
    x, y, z, w = client_lidar_pose["quaternion"]
    lidar_pose = Pose(client_lidar_pose["translation"], Quaternion(w=w, x=x, y=y, z=z))
    client_cam_pose = {
        "translation": [0.0933424, 0.225241, 3.5171],
        "quaternion": [0.00329686, 0.0243397, 0.00187897, 0.999697],
    }
    x, y, z, w = client_cam_pose["quaternion"]
    cam_pose = Pose(client_cam_pose["translation"], Quaternion(w=w, x=x, y=y, z=z))

    pose_dict_expected = {
        "x": 0.0933424,
        "y": 0.225241,
        "z": 3.5171,
        "rotation_x": 0.00329686,
        "rotation_y": 0.0243397,
        "rotation_z": 0.00187897,
        "rotation_w": 0.999697,
    }

    eff_pose = cam_pose.combine(lidar_pose.inverse())

    check_calib_dicts_equality(eff_pose.to_dict(), pose_dict_expected)


def test_pose_combination_inversion():
    """
    Tests that poses obey (a * b)^-1 = b^-1 * a^-1
    """

    client_lidar_pose = {"translation": [0, 0, 0], "quaternion": [0, 0, 0, 1]}
    x, y, z, w = client_lidar_pose["quaternion"]
    lidar_pose = Pose(client_lidar_pose["translation"], Quaternion(w=w, x=x, y=y, z=z))
    client_cam_pose = {
        "translation": [0.0933424, 0.225241, 3.5171],
        "quaternion": [0.00329686, 0.0243397, 0.00187897, 0.999697],
    }
    x, y, z, w = client_cam_pose["quaternion"]
    cam_pose = Pose(client_cam_pose["translation"], Quaternion(w=w, x=x, y=y, z=z))

    eff_pose = cam_pose.combine(lidar_pose.inverse())
    eff_pose_inv = lidar_pose.combine(cam_pose.inverse())

    check_calib_dicts_equality(eff_pose.to_dict(), eff_pose_inv.inverse().to_dict())
