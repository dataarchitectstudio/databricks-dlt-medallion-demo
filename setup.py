from setuptools import find_packages, setup

setup(
    name="orders_medallion",
    version="0.1.0",
    description="Shared reporting logic for the orders medallion demo, packaged as a wheel for Databricks jobs.",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "console_scripts": [
            "main=orders_medallion.main:main",
        ],
    },
)
