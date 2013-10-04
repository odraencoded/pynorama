#!/usr/bin/env python3

from pynorama.application import ImageViewer
import sys, os

# Set preferences directory path to ../preferences/
directory = os.path.dirname(__file__)
parent_directory = os.path.dirname(directory)
preferences_directory = os.path.join(parent_directory, "..", "preferences")
data_directory = os.path.join(parent_directory, "..", "resources")
abs_parent_directory = os.path.abspath(directory)

ImageViewer.PreferencesDirectory = preferences_directory
ImageViewer.DataDirectory = data_directory

application = ImageViewer()
application.run(sys.argv)
