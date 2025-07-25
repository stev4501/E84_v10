from setuptools import find_packages, setup

setup(
    name='e84_controller',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'transitions',
        'loguru',
        'customtkinter',
    ],
    entry_points={
        'console_scripts': [
            'e84-controller=main:main',
            'e84-controller-single=single_card_main:main',
        ],
    },
)
