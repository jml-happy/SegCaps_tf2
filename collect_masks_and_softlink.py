'''
Author: Jamie Lea
Script to softlink masks from a directory into a masks directory based on files in the images directory.
The intention is to provide a directory setup that helps Rodney LaLonde's SegCaps.
The LUNA16 dataset is huge, and divided into 10 subsets.  I wanted to run SegCaps on a single subset.
SegCaps expects data stored as:
root_data_dir/
		/imgs
		/masks

But the LUNA16 dataset has all masks in a single archive.  SegCaps however, globs the masks.  I didn't
want to edit SegCaps or reorganize the dataset.  So:

Intended usage:

* extract a single subset (e.g subset0).  Now there is a folder called subset0.
* extrat the masks. Now there is a folder called seg-lungs-LUNA16
* create a root_data_dir
* create a symlink called imgs to subset0 in the root_data_dir
* place this script in the root data dir
* run this script

This script:	
				* creates the masks folder if it doesn't exist.
				* scans the imgs dir and collects the base file names
				* scans the all_masks_dir and collects the base file names
				* takes the set intersection of the two lets
				* creates a masks dir
				* creates a symlink from each file in the all_masks_dir that coresponds to a file in the imgs dir

This way the SegCaps data loader only lists masks corresponding to the image subset used.
'''

from os.path import splitext, split, join, exists
from os import symlink, makedirs, remove
from glob import glob
import argparse

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--all_masks_dir", type=str, action="store", required=True,
	help='''
	Where all the masks are stored.
	''')

arg_parser.add_argument("--print_lists", action="store_true",
	help='''
	Debug option to print the basenames list.
	''')

args = arg_parser.parse_args()

# get image list
this_img_list = glob("imgs/*.raw")
this_img_basename_list = [split(splitext(img_filename)[0])[-1] for img_filename in this_img_list]

# get all masks list
all_masks_list = []

for ext in ["mhd", "zraw"]:
	all_masks_list.extend(glob(join(args.all_masks_dir, "*{}".format(ext))))

# intersect
this_masks_list = [mask_filename for mask_filename in all_masks_list if split(splitext(mask_filename)[0])[-1] in this_img_basename_list]

if args.print_lists:
	print("Image BaseNames:")
	print("\n".join(this_img_list))
	print("\nMask BaseNames:")
	print("\n".join(all_masks_list))
	print("\nNeeded Mask BaseNames:")
	print("\n".join(this_masks_list))
	

# create symlinks
makedirs("masks", exist_ok=True)
for mask in this_masks_list:
	target_name = join("masks", split(mask)[-1])
	if exists(target_name):
		remove(target_name)
	print(target_name)
	symlink(mask, target_name)

# done
print("Created symlinks.  Please check your directory to confirm.")