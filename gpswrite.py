#!/usr/bin/env

import os
import pdb
import sys

def load_all_points(gpx_filepath):
    import gpxpy
    import pytz

    with open(gpx_filepath, "r") as fh:
        gpx = gpxpy.parse(fh)

    all_points = [point
                  for track in gpx.tracks
                  for segment in track.segments
                  for point in segment.points]
    for point in all_points:
        point.time = point.time.replace(tzinfo=pytz.utc)
    return sorted(all_points, key=lambda point: point.time)

def load_all_photos(albumname):
    import appscript

    app = appscript.app('Photos')

    #if True:
    #    return app.albums[0].media_items.get()

    for album in app.albums[(appscript.its.name == albumname)].get():
        if album.parent.get() == appscript.k.missing_value:
            return album.media_items.get()

def tag_all_photos(points, photos):
    import appscript
    import pytz
    import tzlocal
    import geographiclib.geodesic

    def find_surrounding_points(utc_dt):
        for ix in range(len(points) - 1):
            lpoint = points[ix]
            rpoint = points[ix + 1]
            if utc_dt <= rpoint.time:
                if lpoint.time <= utc_dt:
                    return lpoint, rpoint
                else:
                    break
        return None

    for photo in photos:
        if photo.location.get() != [appscript.k.missing_value, appscript.k.missing_value]:
            print("Skipping %s since it already has a location set" % (photo.filename.get(),))
            continue
        naive_dt = photo.date_.get()
        utc_dt = (naive_dt - tzlocal.get_localzone().utcoffset(naive_dt)).replace(tzinfo=pytz.utc)

        surrounding_points = find_surrounding_points(utc_dt)
        if surrounding_points is None:
            print("Unable to geotag %s" % (photo.filename.get(),))
            continue

        lpoint, rpoint = surrounding_points
        total_time_delta = (rpoint.time - lpoint.time).total_seconds()
        photo_time_delta = (utc_dt - lpoint.time).total_seconds()
        percentage = float(photo_time_delta) / total_time_delta

        line = geographiclib.geodesic.Geodesic.WGS84.InverseLine(
            lpoint.latitude, lpoint.longitude,
            rpoint.latitude, rpoint.longitude)
        coords = line.Position(percentage * line.s13)

        print("Setting %s to %f, %f" % (photo.filename.get(), coords['lat2'], coords['lon2']))

        photo.location.set((coords['lat2'], coords['lon2']))

def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="Process some XMP files into an applescript file to update "
                    "GPS coordinates.")
    parser.add_argument('--gpx', required=True, help='a gpx file to use')
    parser.add_argument('--albumname', required=True, help='album name in photos.app')

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    sorted_points = load_all_points(args.gpx)

    all_photos = load_all_photos(args.albumname)

    tag_all_photos(sorted_points, all_photos)
