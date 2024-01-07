from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='MixSub',
    version='0.0.1',
    description='mix multiple sources(eg danmaku) to subtitle',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='reserveword',
    author_email='reserveword@outlook.com',
    url='www.github.com/reserveword/MixSub',
    # packages=find_packages(where="src"),
    platforms='any',
    license='GPLv3+',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Natural Language :: Chinese (Simplified)"
    ],
    package_dir={"": "src"},
    python_requires='>=3.6'
)