#! /usr/bin/env python

from __future__ import print_function

import argparse
from glob import glob
import os
import re
import requests
import time
import webbrowser

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("media_dir", type=str,
            help="The directory of movies to be scanned")
    parser.add_argument("--metadata_type", default="imdb", choices=["year", "imdb"],
            help="The type of metadata to be appended to the filenames")
    parser.add_argument("--recursive", default=False, action="store_true",
            help="If set, recurse into nested directories in media_dir")
    parser.add_argument("--ignored_only", default=False, action="store_true",
            help="If set, only scan files ignored by CouchPotato (if *.unknown.ignore is present)")
    parser.add_argument("--remove_ignore_files", default=False, action="store_true",
            help="If set, remove CouchPotatos *.unknown.ignore file, signaling a rescan")
    parser.add_argument("--assume_single_result", default=False, action="store_true",
            help="If set, assume queries that return a single result are correct")
    parser.add_argument("--no_confirm", default=False, action="store_true",
            help="If set, do not prompt for confirmation on rename")
    parser.add_argument("--dryrun", default=False, action="store_true",
            help="If set, prompt as normal, but do not alter any files")
    return parser.parse_args()

def omdb_query(name):
    r = requests.get("http://www.omdbapi.com/?r=json&type=movie&s=%s" % name)
    return r.status_code, r.json()

def check_query_success(status_code, results):
    if results and (results.get("Response").lower() == "false"):
        if "Error" in results:
            print("ERROR: %s" % results["Error"])
        else:
            print("ERROR: Unknown")
        return None
    elif status_code < 200 and status_code >= 300:
        print("ERROR: Request failed: %d" % status_code)
    elif not results:
        print("ERROR: Response empty")

    if not results or (results.get("Response").lower() == "false"):
        if "Error" in results:
            print("ERROR: %s" % results["Error"])
        else:
            print("Unknown error")
        return None
    return True

def execute_prompt(existing_file, results, metadata_type):
    choice = None
    while choice is None:
        print()
        for index, option in enumerate(results):
            print("(%d) %s - (%s)" % (index, option["Title"], option["Year"]))
        print("(b0) Open IMDB page for item 0 in your web browser")
        print("(i) Enter IMDB ID manually")
        print("(m) Enter search term manually")
        print("(s) Skip this movie")
        print("(q) Quit")

        # Wait for user input
        user_text = raw_input("Select movie from list, (s)kip, or (q)uit: ")
        if user_text == "q":
            quit(0)
        if user_text == "s":
            return None
        if user_text == "i":
            imdb_id = raw_input("Enter IMDB ID: ")
            if not confirm("Confirm ID \"%s\"?" % imdb_id):
                continue
            else:
                return imdb_id
        if user_text == "m":
            manual = raw_input("Enter manual search query: ")
            manual_status_code, manual_results = omdb_query(manual)
            if not check_query_success(manual_status_code, manual_results):
                print("Manual query unsuccessful.")
            else:
                results = manual_results["Search"]
                status_code = manual_status_code
            continue

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

            selection = results[selection_index]
            if metadata_type == "imdb":
                return selection["imdbID"]
            elif metadata_type == "year":
                return selection["Year"]

        except ValueError:
            print("Invalid selection: \"%s\"" % user_text)
            print("Please select a number 0 - %d, 's' to skip this entry, or 'q' to quit" % (len(results)-1))

def prompt_user(existing_file, metadata_type, assume_single_result):
    # Construct search string from filename
    path_components = file_to_path_components(existing_file)
    query_string = re.sub("\s+", " ", os.path.basename(path_components[0]).replace("_", " ").strip())
    print(os.path.basename(existing_file))
    print("  Search query: \"%s\"" % query_string)

    # Perform OMDB query
    status_code, results = omdb_query(query_string)
    if not check_query_success(status_code, results) and status_code > 400:
        return None

    search_title = query_string
    while results["Response"] == "False":
        print("No results found for \"%s\"" % search_title)
        search_title = raw_input("Enter a title manually, or (s)kip: ")
        if search_title == "s":
            return None
        status_code, results = omdb_query(search_title)
        print(results)

    results = results["Search"]
    print("  Number of search results: %d" % len(results))
    if assume_single_result and len(results) == 1:
        print("  Assuming only result is correct: %s - (%s)" % (results[0]["Title"], results[0]["Year"]))
        metadata = results[0][metadata_type]
    else:
        metadata = execute_prompt(existing_file, results, metadata_type)

    return metadata

def confirm(prompt):
    response = None
    while response not in ["y", "n"]:
        response = raw_input("%s y/[n]: " % prompt).lower()
    return response == "y"

def traverse_directory(directory, recursive=False):
    if not recursive:
        for f in sorted(glob(os.path.join(directory, "*"))):
            yield f
    else:
        for root, directories, files in os.walk(directory):
            for f in sorted(files):
                yield os.path.join(root, f)
            for d in sorted(directories):
                for f in traverse_directory(os.path.join(root, d)):
                    yield f

def file_to_path_components(existing_file):
    return existing_file.rsplit(".", 1)

def file_path_to_renamed_file(existing_file, metadata):
    path_components = file_to_path_components(existing_file)
    return "%s (%s).%s" % (path_components[0],
                           metadata,
                           ".".join(path_components[1:]))

def file_path_to_unknown_file(existing_file):
    path_components = file_to_path_components(existing_file)
    return "%s.unknown.ignore" % path_components[0]

def perform_rename(existing_file,
                   metadata,
                   remove_ignore_files,
                   no_confirm,
                   dryrun):
    path_components = file_to_path_components(existing_file)
    renamed_file = file_path_to_renamed_file(existing_file, metadata)
    unknown_file = file_path_to_unknown_file(existing_file)

    print("Renaming:")
    print("  Old: %s" % existing_file)
    print("  New: %s" % renamed_file)
    if no_confirm or confirm("Confirm rename?"):
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

    files_list = [f for f in traverse_directory(args.media_dir, args.recursive)]
    for existing_file in files_list:
        if existing_file.endswith(".ignore"):
            continue
        unknown_file = file_path_to_unknown_file(existing_file)
        if args.ignored_only and not unknown_file in files_list:
            print("Skipping file (no *.unknown.ignore): %s" % existing_file)
            continue
        if os.path.getsize(existing_file) < 1e6:
            print("Skipping file (less than 1MB): %s" % existing_file)
            continue

        print()
        metadata = prompt_user(existing_file, args.metadata_type, args.assume_single_result)
        if metadata is not None:
            perform_rename(existing_file,
                           metadata,
                           args.remove_ignore_files,
                           args.no_confirm,
                           args.dryrun)
        else:
            print("Skipping %s" % existing_file)
        time.sleep(1)

if __name__ == "__main__":
    main()
