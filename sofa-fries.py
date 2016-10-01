#! /usr/bin/env python

from __future__ import print_function

import argparse
from glob import glob
import os
import requests
import time
import webbrowser

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("media_dir", type=str,
            help="The directory of movies to be scanned")
    parser.add_argument("--metadata_type", default="imdb", choices=["year", "imdb"],
            help="The type of metadata to be appended to the filenames")
    parser.add_argument("--ignored_only", default=False, action="store_true",
            help="If set, only scan files ignored by CouchPotato (if *.unknown.ignore is present)")
    parser.add_argument("--remove_ignore_files", default=False, action="store_true",
            help="If set, remove CouchPotatos *.unknown.ignore file, signaling a rescan")
    parser.add_argument("--dryrun", default=False, action="store_true",
            help="If set, prompt as normal, but do not alter any files")
    return parser.parse_args()

def omdb_query(name):
    r = requests.get("http://www.omdbapi.com/?type=movie&s=%s" % name)
    if r.status_code < 200 or r.status_code >= 300:
        return None
    else:
        return r.json()

def execute_prompt(existing_file, results):
    choice = None
    while choice is None:
        for index, option in enumerate(results):
            print("(%d) %s - (%s)" % (index, option["Title"], option["Year"]))
        print("(b0) Open IMDB page for item 0 in your web browser")
        print("(s) Skip this movie")
        print("(q) Quit")

        # Wait for user input
        user_text = raw_input("Select movie from list, (s)kip, or (q)uit: ")
        if user_text == "q":
            quit(0)
        if user_text == "s":
            return None

        try:
            operator = None
            user_index = user_text
            if user_text.startswith("b"):
                operator = "b"
                user_index = user_text[1:]
            selection_index = int(user_index)
            if operator == "b":
                print()
                webbrowser.open_new_tab("https://www.imdb.com/title/%s" % results[selection_index]["imdbID"])
                continue
            return selection_index
        except ValueError:
            print("Invalid selection: \"%s\"" % user_text)
            print("Please select a number 0 - %d, 's' to skip this entry, or 'q' to quit" % (len(results)-1))

def prompt_user(existing_file, metadata_type):
    # Construct search string from filename
    path_components = existing_file.rsplit(".", 1)
    movie_name = os.path.basename(path_components[0])
    print(os.path.basename(existing_file))
    print("  Search query: \"%s\"" % movie_name)

    # Perform OMDB query
    results = omdb_query(movie_name)
    if not results or (results.get("Response").lower() == "false"):
        if "Error" in results:
            print("ERROR: %s" % results["Error"])
        else:
            print("Unknown error")
        return None

    results = results["Search"]
    print("  Number of search results: %d" % len(results))

    selection_index = execute_prompt(existing_file, results)
    if selection_index is None:
        return None

    selection = results[selection_index]

    if metadata_type == "imdb":
        return selection["imdbID"]
    elif metadata_type == "year":
        return selection["Year"]

def confirm(prompt):
    response = None
    while response not in ["y", "n"]:
        response = raw_input("%s y/[n]: " % prompt).lower()
    return response == "y"

def traverse_directory(directory):
    for root, directories, files in os.walk(directory):
        for f in sorted(files):
            yield os.path.join(root, f)
        for d in sorted(directories):
            for f in traverse_directory(os.path.join(root, d)):
                yield f

def file_to_path_components(existing_file):
    return existing_file.rsplit(".", 1)

def perform_rename(existing_file, metadata, remove_ignore_files, dryrun):
    path_components = file_to_path_components(existing_file)
    renamed_file = "%s (%s).%s" % (path_components[0],
                                   metadata,
                                   ".".join(path_components[1:]))
    print("Renaming:")
    print("  Old: %s" % existing_file)
    print("  New: %s" % renamed_file)
    if confirm("Confirm rename?"):
        if dryrun:
            print("(dryrun) os.rename(existing_file, renamed_file)")
        else:
            os.rename(existing_file, renamed_file)
        if remove_ignore_files:
            if dryrun:
                print("(dryrun) os.remove(unknown_file)")
            else:
                os.remove(unknown_file)

def main():
    args = parse_args()

    print("Using media directory: %s" % args.media_dir)

    files_list = [f for f in traverse_directory(args.media_dir)]
    for existing_file in files_list:
        if existing_file.endswith(".ignore"):
            continue
        path_components = file_to_path_components(existing_file)
        unknown_file = "%s.unknown.ignore" % path_components[0]
        if args.ignored_only and not unknown_file in files_list:
            print("Skipping file (no *.unknown.ignore): %s" % existing_file)
            continue

        metadata = prompt_user(existing_file, args.metadata_type)
        if metadata is not None:
            perform_rename(existing_file, metadata, args.remove_ignore_files, args.dryrun)
        else:
            print("Skipping %s" % existing_file)
        time.sleep(1)
        print()

if __name__ == "__main__":
    main()
