#!/usr/bin/env python 
# Always prefer setuptools over distutils

from setuptools import setup, find_packages 

__doc__ = """ 

To install as system package:  

    python setup.py install   
    
To install as local package:   

    RU=/opt/control
    python setup.py egg_info --egg-base=tmp install --root=$RU/files --no-compile \
    --install-lib=lib/python/site-packages --install-scripts=ds
    
------------------------------------------------------------------------------- 
"""
#print(__doc__)

__MAJOR_VERSION = 1
__MINOR_VERSION = 7

__version = "%d.%d"%(__MAJOR_VERSION,__MINOR_VERSION)

__license = 'GPL-3.0' 

package_data = {
    '': [] #'CHANGES','VERSION','README',
    #'./tools/icon/*','./tools/*ui',],
    } 

setup(name = 'PyHdbppPeriodicArchiver',
    version = __version,
    license = __license,
    description = 'PyHdbppPeriodicArchiver DS for peridical attr insert in HDB++',
    author='Manolo Broseta',
    author_email='mbroseta@cells.es',
    url='git@git.cells.es:controls/PyHdbppPeriodicArchiver.git',      
    packages=find_packages(),
    include_package_data = True,
    package_data = package_data,
    entry_points = {
        'console_scripts': 
            [
            'PyHdbppPeriodicArchiver = PyHdbppPeriodicArchiver.PyHdbppPeriodicArchiver:main',
            ]
        },
    ) 
