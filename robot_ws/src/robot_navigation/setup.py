from setuptools import find_packages, setup

package_name = 'robot_navigation'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/robot_navigation']),
        ('share/robot_navigation', ['package.xml']),
        ('share/robot_navigation/launch',
            ['launch/nav2_localization.launch.py']),
        ('share/robot_navigation/config',
            [
                'config/amcl.yaml',
                'config/room.yaml',
                'config/room.pgm'
            ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='robot',
    maintainer_email='veevekmgr9@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
        ],
    },
)
