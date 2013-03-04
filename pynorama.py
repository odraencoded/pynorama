#!/usr/bin/python3
# coding=utf-8
 
'''
	This is the launcher file of Pynorama
	The argparser is run here and in case it fails, it fails
	before other modules are loaded
	
	Do not import this, it does nothing when imported.
'''

if __name__ == "__main__":
	from gettext import gettext as _
	
	# Setup argument parser
	import argparse
	
	parser = argparse.ArgumentParser()
	parser.add_argument("file", nargs="*", type=str)
	
	# Get arguments
	args = parser.parse_args()
	
	# Import application here, because argparser can not fail anymore
	from application import Pynorama
	app = Pynorama()
	
	# --open is used to load files
	open_uris = []
		 
	for a_path in args.file:
		if not a_path.startswith(("http://", "https://", "ftp://", "file:")):
			a_path = "file://" + a_path
		
		open_uris.append(a_path)
		
	if open_uris:
		app.load_uris(open_uris)
	
	# Run app
	app.run()
