from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():

    teleop_pkg = os.path.join(
        get_package_share_directory('teleop_key'),
        'teleop_key',
        'teleop_key.py'
    )

    return LaunchDescription([

        Node(
            package='teleop_key',
            executable='teleop_key',
            name='teleop_key',
            output='screen',
            prefix='xterm -e',
            parameters=[{'teleop_key': teleop_pkg}]
        )

    ])