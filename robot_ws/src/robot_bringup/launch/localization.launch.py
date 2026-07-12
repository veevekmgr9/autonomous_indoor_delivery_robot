from launch import LaunchDescription
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():

    pkg = get_package_share_directory('robot_bringup')
    ekf_file = os.path.join(pkg, 'config', 'ekf.yaml')
    map_file = os.path.join(pkg, 'maps', 'my_map.yaml')
    amcl_file = os.path.join(pkg, 'config', 'amcl.yaml')

    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        prefix='xterm -e',
        parameters=['/home/robot/Project/robot_ws/src/robot_bringup/config/ekf.yaml']
    )

    # slam_node = Node(
    #     package='robot_localization',
    #     executable='slam_toolbox',
    #     name='slam_toolbox',
    #     output='screen',
    #     prefix='xterm -e',
    #     parameters=['/home/robot/Project/robot_ws/src/robot_bringup/config/slam_toolbox.yaml']
    # )

    # map_node = Node(
    #     package='nav2_map_server',
    #     executable='map_server',
    #     output='screen',
    #     parameters=[
    #         {'yaml_filename': map_file}
    #     ]
    # )

    # amcl_node = Node(
    #     package='nav2_amcl',
    #     executable='amcl',
    #     output='screen',
    #     parameters=[amcl_file]
    # )

    # lifecycle = Node(
    #     package='nav2_lifecycle_manager',
    #     executable='lifecycle_manager',
    #     name='lifecycle_manager_localization',
    #     output='screen',
    #     parameters=[{
    #         'autostart': True,
    #         'node_names': [
    #             'map_server',
    #             'amcl'
    #         ]
    #     }]
    # )

    return LaunchDescription([
        ekf_node,
        # slam_node,
        # map_node,
        # amcl_node,
        # lifecycle
    ])