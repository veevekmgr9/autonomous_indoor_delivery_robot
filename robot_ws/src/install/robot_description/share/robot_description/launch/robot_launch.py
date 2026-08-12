import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    
    rsp = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('robot_description'),
                'launch',
                'rsp.launch.py'
            )
        )
    )

    bridge = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('robot_serial'),
                'launch',
                'bridge.launch.py'
            )
        )
    )

    odom = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('robot_odometry'),
                'launch',
                'odom.launch.py'
            )
        )
    )

    safety = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('safety_node'),
                'launch',
                'safety.launch.py'
            )
        )
    )

    teleop = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('teleop_key'),
                'launch',
                'teleop.launch.py'
            )
        )
    )


    ekf = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('robot_bringup'),
                'launch',
                'localization.launch.py'
            )
        )
    )

    rplidar_node = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('rplidar_ros'),
                'launch',
                'rplidar.launch.py'
            )
        )
    )
    # ekf_pkg = get_package_share_directory('robot_bringup')

    # ekf_config = os.path.join(ekf_pkg, 'config', 'ekf.yaml')

    # ---- Launch arguments ----
    # slam_arg = DeclareLaunchArgument(
    #     'slam',
    #     default_value='false',
    #     description='Set true to also launch slam_toolbox for mapping'
    # )

    # use_slam = LaunchConfiguration('slam')
    return LaunchDescription([
        # slam_arg,
        rsp,
        bridge,
        odom,
        safety,
        ekf,
        rplidar_node,
        teleop,
        # slam,
    ])