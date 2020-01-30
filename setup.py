#!/usr/bin/env python

"Setuptools params"

from setuptools import setup, find_packages
from os.path import join

# Get version number from source tree
import sys
sys.path.append( '.' )
from mininet.net import CONTAINERNET_VERSION

scripts = [ join( 'bin', filename ) for filename in [ 'mn' ] ]

modname = distname = 'mininet'

setup(
    name=distname,
    version=CONTAINERNET_VERSION,
    description='Mininet fork that adds Container support.',
    author='Manuel Peuster',
    author_email='manuel.peuster@upb.de',
    packages=[ 'mininet', 'mininet.examples' ],
    long_description="""
        Mininet is a network emulator which uses lightweight
        virtualization to create virtual networks for rapid
        prototyping of Software-Defined Network (SDN) designs
        using OpenFlow. http://mininet.org
        Mininet author: Bob Lantz (rlantz@cs.stanford.edu)
 
        Containernet is a fork of Mininet that allows
        to use Docker containers as hosts in emulated
        networks.
        """,
    classifiers=[
          "License :: OSI Approved :: BSD License",
          "Programming Language :: Python",
          "Development Status :: 5 - Production/Stable",
          "Intended Audience :: Developers",
          "Topic :: System :: Emulators",
    ],
    keywords='networking emulator protocol Internet OpenFlow SDN',
    license='BSD',
    install_requires=[
        'setuptools',
        'urllib3',
        'docker<=4.1.0',
        'python-iptables',
        'pytest',
        # fixes: https://github.com/pytest-dev/pytest/issues/4770
        'more-itertools<=5.0.0'
    ],
    scripts=scripts,
)
