from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():

    bridge_pkg = os.path.join(
        get_package_share_directory('robot_serial'),
        'robot_serial',
        'arduino_bridge.py'
    )

    return LaunchDescription([

        Node(
            package='robot_serial',
            executable='arduino_bridge',
            name='arduino_bridge',
            output='screen',
            parameters=[{'robot_serial': bridge_pkg}]
        )

    ])