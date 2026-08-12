import os

from launch import LaunchDescription
from launch_ros.actions import Node

from ament_index_python.packages import (
    get_package_share_directory
)


def generate_launch_description():

    config = os.path.join(
        get_package_share_directory(
            'robot_bringup'
        ),
        'config',
        'ekf.yaml'
    )


    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[config]
    )


    return LaunchDescription([
        ekf_node
    ])