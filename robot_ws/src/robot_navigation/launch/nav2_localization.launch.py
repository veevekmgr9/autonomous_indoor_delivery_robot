import os

from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():

    pkg_dir = get_package_share_directory("robot_navigation")

    map_file = os.path.join(
        pkg_dir,
        "config",
        "whole_map.yaml"
    )

    amcl_params = os.path.join(
        pkg_dir,
        "config",
        "amcl.yaml"
    )

    map_server = Node(
        package="nav2_map_server",
        executable="map_server",
        name="map_server",
        output="screen",
        parameters=[{
            "yaml_filename": map_file
        }]
    )

    amcl = Node(
        package="nav2_amcl",
        executable="amcl",
        name="amcl",
        output="screen",
        parameters=[amcl_params],
    )

    lifecycle = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="lifecycle_manager_localization",
        output="screen",
        parameters=[{
            "autostart": True,
            "use_sim_time": False,
            "node_names": [
                "map_server",
                "amcl"
            ]
        }]
    )

    return LaunchDescription([
        map_server,
        amcl,
        lifecycle
    ])