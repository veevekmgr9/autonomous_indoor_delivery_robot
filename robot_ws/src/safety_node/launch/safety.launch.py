from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():

    safety_pkg = os.path.join(
        get_package_share_directory('safety_node'),
        'safety_node',
        'safety_node.py'
    )

    return LaunchDescription([

        Node(
            package='safety_node',
            executable='safety_node',
            name='safety_node',
            output='screen',
            parameters=[{'safety_node': safety_pkg}]
        )

    ])