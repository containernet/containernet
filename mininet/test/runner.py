#!/usr/bin/env python

"""
Run all mininet core tests
 -v : verbose output
 -quick : skip tests that take more than ~30 seconds
 -d : Dockernet tests only
"""

from unittest import defaultTestLoader, TextTestRunner, TestSuite
import os
import sys
from mininet.util import ensureRoot
from mininet.clean import cleanup
from mininet.log import setLogLevel


def runTests( testDir, verbosity=1, dockeronly=False ):
    "discover and run all tests in testDir"
    # ensure root and cleanup before starting tests
    ensureRoot()
    cleanup()
    # discover all tests in testDir
    testSuite = defaultTestLoader.discover( testDir )
    if dockeronly:
        testSuiteFiltered = [s for s in testSuite if "Docker" in str(s)]
        testSuite = TestSuite()
        testSuite.addTests(testSuiteFiltered)

    # run tests
    TextTestRunner( verbosity=verbosity ).run( testSuite )


def main(thisdir):
    setLogLevel( 'warning' )
    # get the directory containing example tests
    vlevel = 2 if '-v' in sys.argv else 1
    dockeronly = ('-d' in sys.argv)
    runTests( testDir=thisdir, verbosity=vlevel, dockeronly=dockeronly )


if __name__ == '__main__':
    thisdir = os.path.dirname( os.path.realpath( __file__ ) )
    main(thisdir)
