from setuptools import setup, find_packages

setup(
    name="gift-test-practice",
    version="1.0.0",
    description="Aplicação para praticar perguntas em formato GIFT com interface Qt6",
    packages=find_packages(),
    install_requires=[
        "PySide6",
    ],
    entry_points={
        "console_scripts": [
            "gift-test-practice=main:main",
        ],
    },
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
