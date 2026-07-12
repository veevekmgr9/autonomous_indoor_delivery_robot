from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():

    odom_pkg = os.path.join(
        get_package_share_directory('robot_odometry'),
        'robot_odometry',
        'robot_odometry.py'
    )

    return LaunchDescription([

        Node(
            package='robot_odometry',
            executable='odom_node',
            name='odom_node',
            output='screen',
            parameters=[{'robot_odometry': odom_pkg}]
        )

    ])