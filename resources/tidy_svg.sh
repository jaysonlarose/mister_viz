#!/bin/bash

# BASH script to help me remember how to use HTML Tidy to reformat SVG
# files so that they're easier to edit.

# usage: ./tidy_svg.sh [input_file] > [output_file]
# (then, replace input_file with output_file if you're happy)

tidy -config tidy.config "$1"
