"""
Utilities for 3D and 2D geometry calculations

Author: Shaashwat Saraff
2D<>3D conversion code written in collaboration with Nicolas Duchene

For usage example please see:
- 3D to 2D cuboid projection: nartools/tests/test_cuboid_3d_to_2d_uned.py
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import open3d as o3d
from numpy.linalg import norm


class Converter2D3D:
    """
    Supplies methods to allow conversion between
    camera (2D pixel) and lidar (3D real space)
    coordinates
    """

    def __init__(self, calibration: Dict[str, float], dims: Tuple[int, int]) -> None:
        """
        Constructor to define an object to convert between 2D and 3D using a camera's intrinsic and extrinsic parameters

        Args:
            calibration (Dict[str, float]): Dict of camera calibration params in Sama format (intrinsic: f_x, f_y, c_x, c_y; extrinsic: x, y, z, rotation_x, rotation_y, rotation_z, rotation_w)
            dims (Tuple[int, int]): (width, height) of image in pixels
        """

        self.__init_calibration(calibration)
        # ^ creates the following new instance variables (self.): xyz2rgb, C, rgb2xyz
        self.im_width, self.im_height = dims

    def __init_calibration(self, camera_calibration: Dict[str, float]) -> None:
        """
        Loads the camera calibration into the current object

        Args:
            camera_calibration (Dict[str, float]): Dict of calibration params in Sama format (intrinsic: f_x, f_y, c_x, c_y; extrinsic: x, y, z, rotation_x, rotation_y, rotation_z, rotation_w)
        """

        # construct camera intrinsic matrix
        # [[f_x, 0,   c_x]
        #  [0,   f_y, c_y]
        #  [0,   0,   1  ]]
        camera_intrinsic = np.eye(3)
        camera_intrinsic[0, 0] = camera_calibration["f_x"]
        camera_intrinsic[1, 1] = camera_calibration["f_y"]
        camera_intrinsic[0, 2] = camera_calibration["c_x"]
        camera_intrinsic[1, 2] = camera_calibration["c_y"]

        t_camera_intrinsic = np.insert(camera_intrinsic, 3, 0, axis=1)

        # Construct camera extrinsic matrix. Form:
        # r11   r12   r13   x
        # r21   r22   r23   y
        # r31   r32   r33   z
        #   0     0     0   1
        camera_pose = np.eye(4)
        r_quat_wxyz = [
            camera_calibration["rotation_w"],
            camera_calibration["rotation_x"],
            camera_calibration["rotation_y"],
            camera_calibration["rotation_z"],
        ]
        camera_pose[:3, :3] = o3d.geometry.get_rotation_matrix_from_quaternion(r_quat_wxyz)
        camera_pose[:3, 3] = [camera_calibration["x"], camera_calibration["y"], camera_calibration["z"]]
        camera_extrinsic = np.linalg.inv(camera_pose)

        self.xyz2rgb = t_camera_intrinsic.dot(camera_extrinsic)

        # Here destination is LIDAR and source is camera
        destination_to_source = np.eye(4) @ camera_extrinsic.copy()
        # Homogeneous transform from lidar to cam coords:
        # [R|-R@C] where R is the rotation matrix and C is the center of camera
        R_homo = destination_to_source[:3, :4]
        # Projection matrix:
        # P = K@[R|-R@C] = [M|-M@C]
        P = camera_intrinsic @ R_homo
        # Center of camera:
        # C = -M^-1 @ p_4 where M=K@R and p_4 is 4th column of P
        self.C = -np.linalg.inv(P[:3, :3]) @ P[:, 3]
        # Pseudo-inverse of projection matrix
        self.rgb2xyz = P.T @ np.linalg.inv(P @ P.T)

    def points_to_pixels(self, points: o3d.cpu.pybind.utility.Vector3dVector) -> Tuple[np.array]:
        """
        Given a list of 3D points, returns a list of corresponding pixel coords

        Args:
            points (o3d.cpu.pybind.utility.Vector3dVector): A set of 3D points for which we want the corresponding 2D pixels

        Returns:
            (
                u: np array of pixel x coords (in px),
                v: np array of pixel y coords (in px),
                z: np array of point depths (in m) from camera,
                list of indices of original points array corresponding to points with positive depths
            )

        E.g. Usage for converting a single point:
        Code: converter.points_to_pixels([array([11.42399979, -3.01600003, -0.073     ])])
        Output:
        (
            array([1302.30542756]), # x in px
            array([634.53056064]),  # y in px
            array([11.76634238]),   # depth, can disregard
            array([0])              # indicates that the given point at index 0 was converted into a pixel
        )
        """

        points = np.insert(points, 3, 1, axis=1)
        im_coords = self.xyz2rgb @ points.T
        im_coords[:2] /= im_coords[2, :]
        u, v, z = im_coords

        # # Commenting out the code to restrict output below
        # # (restrictions were relaxed for the sake generality and to allow
        # # pixel coords for all points irrespective of +ve/-ve depth).
        # # Filter points outside the image or behind the camera.
        # u_in_mask = np.logical_and(u >= 0, u < self.im_width)  # image width range filtering
        # v_in_mask = np.logical_and(v >= 0, v < self.im_height)  # image height range filtering
        # z_in_mask = z > 0  # depth filtering
        # inliers_mask = np.logical_and(np.logical_and(u_in_mask, v_in_mask), z_in_mask)  # applies all 3 of the above filters
        # inliers_mask = z_in_mask  # Applies only the depth filter. This is to include all points, even if they are not in the image
        # u, v, z = list(map(lambda p: p[inliers_mask], (u, v, z)))
        # inlier_indices = np.argwhere(inliers_mask.astype(int)).flatten()

        # In the absence of any filtering, inlier indices are
        # the same as the indices of the original list of points,
        # which are the same as the indices of any of the pixel
        # coord arrays (here we take u)
        inlier_indices = list(range(len(u)))

        # Instead of filtering out points behind the camera, we allow them
        # with a warning
        z_in_mask = z > 0
        positive_depth_indices = list(np.argwhere(z_in_mask.astype(int)).flatten())
        if inlier_indices != positive_depth_indices:
            nonpos_depth_indices = [i for i in inlier_indices if i not in positive_depth_indices]
            nonpos_depth_points_3d = points[nonpos_depth_indices][:, :3].tolist()
            nonpos_depth_points_2d = list(zip(u[nonpos_depth_indices], v[nonpos_depth_indices]))
            warnings.warn(
                f"points_to_pixels: All 3D points were converted to 2D, but some of them are behind the camera (non-positive depths). "
                f"Caution is advised. Non-positive depth indices: {nonpos_depth_indices}. "
                f"Non-positive depth 3D points: {nonpos_depth_points_3d}. Non-positive depth 2D points: {nonpos_depth_points_2d}."
            )

        return u, v, z, inlier_indices

    def pixels_to_points(self, pixels: List[Tuple[float]], depths: List[float]) -> List[List[float]]:
        """
        Given a list of 2D image pixels (pixel coords [x, y] in img) and corresponding depths (in m),
        finds the corresponding 3D points

        Args:
            pixels (List[Tuple[float]]): List of pixel [x, y] coords
            depths (List[float]): List of corresponding depth values in m

        Returns:
            List of corresponding 3D points [x, y, z] in metres

        E.g. Usage for a single point:
        Code: converter.pixels_to_points(
            [   # list of px coord pairs [x, y]
                [1302.30542756, 634.53056064]
            ],
            [11.76634238]
        )
        Output: array([[11.13689387, -2.91309784, -0.07918333]])
        """

        rays = self.pixels_to_rays(pixels)
        return self.C[:3] + rays * depths

    def pixels_to_rays(self, pixels: List[Tuple[float]]) -> List[List[float]]:
        """
        Given a list of pixels, returns a list of unit vector directions
        representing rays from the camera towards those pixels

        Args:
            pixels (List[Tuple[float]]): List of pixel [x, y] coords
        """
        bbox_pixels = np.insert(pixels, 2, values=np.ones((1, len(pixels))), axis=1)
        projected_pixels = self.rgb2xyz @ bbox_pixels.T
        projected_pixels /= projected_pixels[3]  # Normalize for homogeneous coords
        proj = projected_pixels.T[:, :3] - self.C[:3]
        proj /= np.linalg.norm(proj, axis=1).reshape((-1, 1))
        return proj

    def backcast_to_plane(
        self,
        pixels: List[Tuple[float, float]],
        normal: Tuple[float, float, float],
        point_in_plane: Tuple[float, float, float],
    ) -> List[Tuple[float, float, float]]:
        """
        Given a list of pixels and a plane defined by a normal and a point,
        returns the points where the pixels' shadows would lie on the plane

        Args:
            pixels (List[Tuple[float, float]]): List of pixel [x, y] coords
            normal (Tuple[float, float, float]): Unit normal vector specifying the orientation of the plane
            point_in_plane (Tuple[float, float, float]): A point in the plane specifying its location

        Returns:
            List of 3D points corresponding to where the given pixels would fall on the given plane as rays from the camera
        """

        def find_intersection(plane_normal, plane_point, ray_direction, ray_point):
            """
            Finds the point of intersection between a plane and a ray
            """

            epsilon = 1e-6  # tolerance for zero dot product (ray perp to plane normal)
            ndotu = plane_normal.dot(ray_direction)
            if abs(ndotu) < epsilon:
                warnings.warn(
                    "backcast_to_plane/find_intersection: Ray either doesn't intersect with plane or lies within it"
                )

            w = ray_point - plane_point
            si = -plane_normal.dot(w) / ndotu
            Psi = w + si * ray_direction + plane_point  # intersections
            return Psi

        rays = self.pixels_to_rays(pixels)

        intersections = []
        for p in rays:
            intersections.append(find_intersection(normal, point_in_plane, p, self.C[:3]))

        return intersections


class GeometryUtils:
    """
    Supplies utilities for 3D and 2D math ops
    """

    def get_rotation_matrix_from_vectors(vec1: np.ndarray, vec2: np.ndarray) -> np.ndarray:
        """
        This function takes two 1D numpy arrays representing 3D vectors and returns a rotation matrix
        (2D numpy array) that aligns vec1 with vec2 (transformation without scaling)

        Args:
            vec1 (np.ndarray): A 3d "source" vector
            vec2 (np.ndarray): A 3d "destination" vector

        Returns:
            A transform matrix (3x3) which when applied to vec1, aligns it with vec2,
            i.e., returns R such that R @ vec1_unitVector = vec2_unitVector
        """

        a, b = (vec1 / norm(vec1)).reshape(3), (vec2 / norm(vec2)).reshape(3)
        v = np.cross(a, b)
        c = np.dot(a, b)
        s = norm(v)
        kmat = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        rotation_matrix = np.eye(3) + kmat + kmat.dot(kmat) * ((1 - c) / (s**2))
        return rotation_matrix

    def project_shape_3d_to_2d(
        points_3d: List[Tuple[float, float, float]], conv: Converter2D3D
    ) -> List[Tuple[float, float]]:
        """
        Accepts the coords of a Sama 3D shape and returns its projected 2D coords in the same order

        For cuboids, the order should conventionally be [FBR, FTR, FBL, FTL, rBR, rTR, rBL, rTL]
        (where F = front, r = rear, B = bottom, T = top, R = right, L = left)
        but it is not technically necessary

        Args:
            points_3d (List[Tuple[float, float, float]]): List of 3D shape (e.g. cuboid) coords in Sama format
            conv (Converter2D3D): Converter object with camera calibrations loaded
        Returns:
            List of projected 2D coords for the cuboid to be overlaid on image (in the same order as the coords supplied)
        """

        x_coords, y_coords, depths, inlier_indices = conv.points_to_pixels(points_3d)
        points_2d = zip(list(x_coords), list(y_coords))

        if list(inlier_indices) != list(range(len(points_3d))):
            warnings.warn(
                f"project_shape_3d_to_2d: Not all 3D points were converted to 2D. 3D points: {points_3d}. Inlier indices: {inlier_indices}."
            )

        return [list(point) for point in points_2d]
