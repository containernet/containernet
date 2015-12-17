import runner
import os


if __name__ == '__main__':
    thisdir = os.path.dirname( os.path.realpath( __file__ ) )
    runner.main(thisdir)
