"""
This module supplies code for converting the
coordinates of a point between different 3D
coordinate systems

Currently supported conversions:
    - Geodetic (aka LLA) [lat, long, alt] -> ECEF (Cartesian) [x, y, z]

References:
    - https://www.mathworks.com/help/map/choose-a-3-d-coordinate-system.html
"""

import warnings
from typing import Type

import gnss_lib_py as glp


class Coordinates:
    """
    A general class to describe a set of coordinates in some system
    """

    pass


class Coordinates3D(Coordinates):
    """
    A general class to describe a set of 3D coordinates in some system
    """

    pass


class GeodeticCoords(Coordinates3D):
    """
    Defines a 3-tuple of geodetic coordinates
    (latitude, longitude, altitude), aka LLA
    """

    def __init__(self, lat_degN: float, long_degE: float, alt_mUp: float):
        """
        Initialises a GeodeticCoords object

        Args:
            lat_degN: latitude in degrees North
            long_degE: longitude in degrees East
            alt_mUp: altitude in metres upwards (away from the centre of the Earth)
        """

        # TODO: Implement validation of input values and raise ValueError

        self.latitude = lat_degN
        self.longitude = long_degE
        self.altitude = alt_mUp

    def __str__(self) -> str:
        """
        Returns a string representation of the object
        """
        return f"({self.latitude} deg East, {self.longitude} deg North, {self.altitude} m Upwards)"

    def __repr__(self) -> str:
        """
        Returns a string representation of the object
        """
        return f"GeodeticCoords(lat_degN={self.latitude}, long_degE={self.longitude}, alt_mUp={self.altitude})"


class ECEFCoords(Coordinates3D):
    """
    Defines a 3-tuple of ECEF (Earth-Centred Earth-Fixed) coordinates
    (x, y, z), aka Cartesian

    Origin and axis arrangement are as defined in WGS84
    """

    def __init__(self, x_m: float, y_m: float, z_m: float):
        """
        Initialises an ECEFCoords object

        Args:
            x_m: x-coordinate in metres
            y_m: y-coordinate in metres
            z_m: z-coordinate in metres
        """

        # TODO: Implement validation of input values and raise ValueError

        self.x = x_m
        self.y = y_m
        self.z = z_m

    def __str__(self) -> str:
        """
        Returns a string representation of the object
        """
        return f"({self.x} m, {self.y} m, {self.z} m)"

    def __repr__(self) -> str:
        """
        Returns a string representation of the object
        """
        return f"ECEFCoords(x_m={self.x}, y_m={self.y}, z_m={self.z})"


class CoordSysConverter:
    """
    Defines methods for converting between coordinate systems
    """

    def __init__(self):
        """
        Initialises a CoordSysConverter object
        """
        self.coords = Coordinates3D()

    def load_coords(self, coords: Coordinates3D) -> None:
        """
        Loads the coordinates to be converted

        Args:
            coords: the coordinates to be converted
        """
        self.coords = coords

    def convert_to_type(self, target_type: Type[Coordinates3D]) -> Coordinates3D:
        """
        Converts the coordinates to the target type

        Args:
            target_type: the type of coordinates to convert to

        Returns:
            the converted coordinates
        """

        from_type = type(self.coords)

        # Validation: Checking if any coords were even loaded
        if from_type == Coordinates3D:
            # i.e., it's still of the abstract superclass type
            # we need it to be a set of actual coordinates of a specific type
            # (geodetic, ECEF, etc.)
            raise ValueError("No coordinates were loaded before calling the conversion method")

        if from_type == target_type:
            warnings.warn("Specified target type is the same as the native type - returning as-is")
            return self.coords

        # currently_supported_conversions = [
        #     {
        #         'from': GeodeticCoords,
        #         'to': ECEFCoords,
        #     }
        # ]
        if from_type == GeodeticCoords and target_type == ECEFCoords:
            return CoordSysConverter.__get_coords_geodetic_to_ecef(self.coords)
        else:
            raise NotImplementedError(f"Conversion from {from_type} to {target_type}" " is not currently supported")

    @staticmethod
    def __get_coords_geodetic_to_ecef(geo_coords: GeodeticCoords) -> ECEFCoords:
        """
        Converts a given set of geodetic coordinates to ECEF
        """

        gdt_coords_glp = [[geo_coords.latitude], [geo_coords.longitude], [geo_coords.altitude]]
        ecef_coords_glp = glp.geodetic_to_ecef(gdt_coords_glp)
        x, y, z = ecef_coords_glp.flatten()

        return ECEFCoords(x, y, z)
