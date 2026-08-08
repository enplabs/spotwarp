from setuptools import setup, find_packages

setup(
    name="spotwarp",
    version="3.1.1",
    description="Zero-Downtime Spot GPU Failover Guard & AI Acceleration Utility for Vast.ai & RunPod",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="SpotWarp Team",
    author_email="info@gpu-action.com",
    url="https://gpu-action.com",
    project_urls={
        "Documentation": "https://gpu-action.com/docs",
        "Source": "https://github.com/enplabs/spotwarp",
    },
    py_modules=["gpu_action_cli", "runpod_connector"],
    entry_points={
        "console_scripts": [
            "spotwarp=gpu_action_cli:main",
        ],
    },
    install_requires=[
        "requests>=2.25.0",
    ],
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: System :: Monitoring",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
)
