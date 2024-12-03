from setuptools import find_packages, setup

package_name = 'whack_a_mole'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='PushkarDave',
    maintainer_email='pushkar@u.northwestern.edu',
    description='Making franka play whack a mole',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'swing = whack_a_mole.swing:main'
        ],
    },
)
