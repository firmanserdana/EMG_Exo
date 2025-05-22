from setuptools import setup, find_packages

setup(
    name="emg_exo",
    version="1.0.0",
    packages=find_packages(),
    
    # Dependencies
    install_requires=[
        "numpy>=1.22.0",
        "scipy>=1.8.0",
        "matplotlib>=3.5.0",
        "scikit-learn>=1.0.2",
        "pandas>=1.4.0",
        "h5py>=3.6.0",
        "joblib>=1.1.0",
        "mne>=1.0.0",
        "pyserial>=3.5",
        "pylsl>=1.14.0",
    ],
    extras_require={
        'gui': ["PyQt5>=5.15.0; platform_system != 'Darwin' or platform_machine != 'arm64'",
                "PyQt6>=6.3.0; platform_system == 'Darwin' and platform_machine == 'arm64'"],
    },
    
    # Metadata
    author="EMG_Exo Team",
    author_email="example@example.com",
    description="EMG-Based Exoskeleton Control System",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/username/EMG_Exo",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
      # Entry points
    entry_points={
        'console_scripts': [
            'emg-exo=emg_exo.apps.main_app:main',
            'emg-demo=emg_exo.apps.simple_demo:main',
            'emg-trigno=emg_exo.apps.delsys_trigno_demo:main',
            'emg-train=emg_exo.apps.main_app:main --train',
        ],
    },
    include_package_data=True,
)
