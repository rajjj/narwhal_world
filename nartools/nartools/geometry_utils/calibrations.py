"""
Utilities to handle lidar pose and projection calibrations

Author: Shaashwat Saraff

For usage example please see:
- Extrinsic matrix to pose dict: nartools/tests/test_calib_parser.py::test_ext_mat_to_pose_dict
- Extrinsic matrix + intrinsic matrix to projection calib dict: nartools/tests/test_calib_parser.py::test_ext_int_mats_to_proj_dict
"""

# TODO: Write unit tests as mentioned above

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import numpy.typing as npt
from pyquaternion import Quaternion
from scipy.spatial.transform import Rotation as R


class Pose:
    """
    Defines a pose object (Python implementation with extra math features of
    pose dict = position + rotation) as per the conventions at Sama
    """

    def __init__(
        self, position_xyz: Union[Tuple[float, float, float], npt.ArrayLike], orientation_quat: Quaternion
    ) -> None:
        """
        Initialises the pose object
        """

        self.position = np.array(
            position_xyz
        )  # TODO: validate array shape and data type (we want 1D array of 3 floats)
        self.orientation = Quaternion(orientation_quat)  # TODO: consider normalising this

    def from_dict(params: Dict[str, float]) -> Pose:
        """
        Creates a Pose object from a pose dictionary
        """

        try:
            x = params["x"]
            y = params["y"]
            z = params["z"]
            rotation_x = params["rotation_x"]
            rotation_y = params["rotation_y"]
            rotation_z = params["rotation_z"]
            rotation_w = params["rotation_w"]
        except KeyError:
            raise ValueError(
                "Dictionary must contain all necessary pose params: "
                "x, y, z, rotation_x, rotation_y, rotation_z, rotation_w"
            )

        position = np.array([x, y, z])
        orientation = Quaternion(
            x=rotation_x,
            y=rotation_y,
            z=rotation_z,
            w=rotation_w,
        )

        return Pose(position, orientation)

    def to_dict(self) -> Dict[str, float]:
        """
        Returns the dict representation of a pose in
        the format ingestible by Sama
        """

        return {
            "x": self.position[0],
            "y": self.position[1],
            "z": self.position[2],
            "rotation_x": self.orientation.x,
            "rotation_y": self.orientation.y,
            "rotation_z": self.orientation.z,
            "rotation_w": self.orientation.w,
        }

    def inverse(self) -> Pose:
        """
        Returns the inverse of the pose object

        Usage: pose2 = pose1.inverse()
        """

        # Following SH3 frontend approach to inversion
        # Flip the position
        inv_position = -self.position
        # Conjugate (invert) the rotation
        inv_orientation = self.orientation.conjugate

        return Pose(inv_position, inv_orientation)

    def combine(self, append_pose: Pose) -> Pose:
        """
        Right-combines a given pose with the current pose and returns
        the resultant pose

        Usage: pose3 = pose1.combine(pose2)
        """

        res_position = self.position + append_pose.position
        res_orientation = self.orientation * append_pose.orientation

        return Pose(res_position, res_orientation)


class CalibrationParser:
    """
    Supplies methods to read/write calibration data from/to various formats
    """

    def __init__(self) -> None:
        """
        Initialises the parser object with all calibration parameters
        set to default values. After object creation, use one of the
        data loading methods to load custom, values first before
        trying to get the values out of the object (e.g. as a dict).
        """

        # Extrinsic params (relevant for pose and projection calibs)
        self.x = 0
        self.y = 0
        self.z = 0
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.rotation_w = 0

        # Intrinsic params (relevant only for projection calibs)
        self.f_x = 0
        self.f_y = 0
        self.c_x = 0
        self.c_y = 0

        # Internal variables to track object state
        self.__extrinsics_loaded = False
        self.__intrinsics_loaded = False

    def load_intrinsics_from_matrix(self, intrinsic_matrix_3x3: npt.NDArray) -> None:
        """
        Parses a 3x3 intrinsic matrix to load intrinsic params

        Args:
            intrinsic_matrix_3x3 (npt.NDArray): The 3x3 intrinsic matrix as a numpy array
        """

        # Sanity checks
        intrinsic_matrix_3x3 = np.array(intrinsic_matrix_3x3)
        shape = intrinsic_matrix_3x3.shape
        assert shape == (3, 3), f"Intrinsic matrix must have shape (3, 3), received matrix of shape {shape}"

        # Load data based on standard structure of intrinsic matrices
        self.f_x = intrinsic_matrix_3x3[0][0]
        self.f_y = intrinsic_matrix_3x3[1][1]
        self.c_x = intrinsic_matrix_3x3[0][2]
        self.c_y = intrinsic_matrix_3x3[1][2]

        self.__intrinsics_loaded = True

    def load_extrinsics_from_matrix(
        self,
        extrinsic_matrix_4x4: npt.NDArray,
        pose_is_inverse_of_ext: bool = True,
        invert_transformation: bool = True,
        init_rot_deg_XYZ: Tuple[float, float, float] = (0, 0, 0),
    ) -> None:
        """
        Parses a 4x4 extrinsic matrix to load extrinsic params

        Args:
            extrinsic_matrix_4x4 (npt.NDArray): The 4x4 extrinsic matrix as a numpy array
            pose_is_inverse_of_ext (bool): Whether the pose matrix is to be taken as the inverse of the extrinsic matrix supplied. Defaults to True
            invert_transformation (bool): Whether the transformation should be inverted, following SH3 front-end logic. Defaults to True
            init_rot_deg_XYZ (Tuple[float, float, float]): Initial rotation in degrees to apply to the extrinsics. This follows the XYZ Euler angles convention. Defaults to (0, 0, 0)

        Note: In this version, only a (0, 0, 0) initial rotation is supported. Support for initial rotations will be added in a future version.
        """

        # Sanity checks
        extrinsic_matrix_4x4 = np.array(extrinsic_matrix_4x4)
        shape = extrinsic_matrix_4x4.shape
        assert shape == (4, 4), f"Extrinsic matrix must have shape (4, 4), received matrix of shape {shape}"
        assert tuple(init_rot_deg_XYZ) == (0, 0, 0), "Initial rotations are not currently supported"

        if pose_is_inverse_of_ext:
            pose_mat = np.linalg.inv(extrinsic_matrix_4x4)
        else:
            pose_mat = extrinsic_matrix_4x4

        # TODO:
        # Once the `Pose` code is finalised, rewrite this section to use the `Pose` class instead of implementing the logic itself (D.R.Y. principle, yo!)

        # Convert pose from matrix to position + rot quat format
        position_xyz = np.array([pose_mat[0, 3], pose_mat[1, 3], pose_mat[2, 3]])
        rot_quat_xyzw = R.from_matrix(pose_mat[:3, :3]).as_quat()

        if invert_transformation:
            # Replicating SH3 frontend approach to inversion of transformation

            # Flip the position
            position_xyz *= -1

            # Conjugate (invert) the rotation
            quat = Quaternion(
                x=rot_quat_xyzw[0],
                y=rot_quat_xyzw[1],
                z=rot_quat_xyzw[2],
                w=rot_quat_xyzw[3],
            )
            quat = quat.conjugate
            rot_quat_xyzw = [quat.x, quat.y, quat.z, quat.w]

        # Apply the initial rotation: Not sure whether this works properly!
        # This code is never executed thanks to the assertion above.
        # If you can fix/verify this, please be my guest and release it as a new feature. :)
        if init_rot_deg_XYZ != [0, 0, 0]:
            # Build the 'initial rotation' into the quat we generate here
            # Calcing result as output_rot = given_rot * init_rot
            # so that the init_rot is applied to the coords first
            # upon left-multiplication
            init_rot = R.from_euler("XYZ", init_rot_deg_XYZ, degrees=True)
            rot_quat_xyzw = (R.from_quat(rot_quat_xyzw) * init_rot).as_quat()

        self.x = position_xyz[0]
        self.y = position_xyz[1]
        self.z = position_xyz[2]
        self.rotation_x = rot_quat_xyzw[0]
        self.rotation_y = rot_quat_xyzw[1]
        self.rotation_z = rot_quat_xyzw[2]
        self.rotation_w = rot_quat_xyzw[3]

        self.__extrinsics_loaded = True

    def get_pose_dict(self) -> Dict[str, float]:
        """
        Returns the relevant calibration params packed into a Sama-ingestible
        dict, e.g. for lidar fixed world calibrations or camera extrinsics
        """

        if not self.__extrinsics_loaded:
            warnings.warn("Extrinsics were not loaded using the loader methods - pose dict may be invalid")

        pose_dict = {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "rotation_x": self.rotation_x,
            "rotation_y": self.rotation_y,
            "rotation_z": self.rotation_z,
            "rotation_w": self.rotation_w,
        }

        return pose_dict

    def get_projection_dict(self) -> Dict[str, float]:
        """
        Returns the relevant calibration params packed into a Sama-ingestible
        dict for lidar-camera projection calibrations
        """

        if not self.__intrinsics_loaded:
            warnings.warn("Intrinsics were not loaded using the loader methods - projection dict may be invalid")

        proj_dict = self.get_pose_dict()  # Get the extrinsics
        intrinsic_dict = {
            "f_x": self.f_x,
            "f_y": self.f_y,
            "c_x": self.c_x,
            "c_y": self.c_y,
        }
        proj_dict.update(intrinsic_dict)

        return proj_dict
