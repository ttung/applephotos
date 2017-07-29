#!/usr/bin/env python3.6

import appscript
import os
import sys
import time

from contextlib import contextmanager

DEBUG = False

if DEBUG:
    TIMEOUT = 60
    PDB_ENABLED = True
else:
    TIMEOUT = 600
    PDB_ENABLED = False

class PhotosApp(object):
    obj = None

    @staticmethod
    def get(refresh=False):
        if PhotosApp.obj is None or refresh:
            PhotosApp.obj = appscript.app("Photos")

        return PhotosApp.obj

@contextmanager
def ignored(*exceptions):
    try:
        yield
    except exceptions:
        pass

def export_tree_builder(
        disk_path,
        attempts=5,
        timeout=TIMEOUT,
        dry_run=False):
    import mactypes
    import pdb
    import shutil

    def export_tree(path_matcher, path, child):
        child_name = child.name.get().replace("/", ":")
        if path == None:
            current_path = child_name
        else:
            current_path = os.path.join(path, child_name)

        current_disk_path = os.path.join(disk_path, current_path)

        childclass = child.class_.get()
        if path_matcher(
            current_path, childclass == appscript.k.folder) is not True:
            return

        # are we an album?  if so, just export away.
        if child.class_.get() == appscript.k.album:
            for attempt in range(attempts):
                if PDB_ENABLED:
                    pdb.set_trace()
                print("Exporting %s to %s.%s" % (
                    current_path,
                    current_disk_path,
                    "" if attempt == 0 else " [attempt=%d]" % attempt,
                ))
                if dry_run:
                    break
                try:
                    with ignored(EnvironmentError):
                        shutil.rmtree(current_disk_path)
                    with ignored(EnvironmentError):
                        os.makedirs(current_disk_path)
                    PhotosApp.get().export(
                        child.media_items.get(),
                        to=mactypes.Alias(current_disk_path),
                        timeout=timeout,
                        using_originals=True)
                    break
                except Exception:
                    system_events_app = appscript.app('System Events')
                    system_events_app_photos_process = system_events_app.processes['Photos']
                    print("  Trying to dismiss any remaining dialogs...")
                    for _ in range(10):
                        for window in system_events_app_photos_process.windows():
                            with ignored(Exception):
                                window.buttons['OK'].click()
                                break

                        time.sleep(1)

                    print("  Trying to terminate photos...")
                    try:
                        PhotosApp.get().quit()
                    except Exception:
                        print("  Trying to confirm termination...")
                        for _ in range(10):
                            for window in system_events_app_photos_process.windows():
                                for sheet in window.sheets():
                                    with ignored(Exception):
                                        sheet.buttons['Quit'].click()
                                        break

                            time.sleep(1)
                    print("  Waiting for photos to terminate...")
                    while True:
                        try:
                            PhotosApp.get().activate()
                        except Exception:
                            # hey, the app finally closed.
                            break
                        time.sleep(1)
                    print("  Restarting photos...")
                    PhotosApp.get(refresh=True).run()
        elif child.class_.get() == appscript.k.folder:
            for subchild in child.containers.get():
                export_tree(path_matcher, current_path, subchild)

    return export_tree

def find_albums(path_matcher, handler):
    for child in PhotosApp.get().containers.get():
        if child.parent.get() == appscript.k.missing_value:
            handler(path_matcher, None, child)

def match_year_maker(year_start, year_end):
    def match_year(path, isfolder):
        if not isfolder and path <= "2016/10 - Single shots":
            return False

        firstsep = path.find("/")
        if firstsep == -1:
            try:
                year = int(path)
            except ValueError:
                return False
        else:
            try:
                year = int(path[:firstsep])
            except ValueError:
                return False

        if year >= year_start and year <= year_end:
            return True
        return False
    return match_year

def match_2017_02(path, isfolder):
    if path.startswith("2017/03"):
        return True
    elif path.startswith("2017") and isfolder:
        return True
    return False

if __name__ == "__main__":
    find_albums(match_2017_02,
                export_tree_builder("/Users/tonytung/queue/awsbackup")
    )
