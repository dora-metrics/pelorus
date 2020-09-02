#!/usr/bin/python3
import getopt
import semver
import sys
import yaml


def bump_patch(chart_path):
    chart_dot_yaml = "%s/Chart.yaml" % chart_path
    chart_file = open(chart_dot_yaml)

    chart = yaml.load(chart_file, Loader=yaml.FullLoader)

    version = semver.VersionInfo.parse(chart['version'])

    print(str(version.bump_patch()))


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "i:", ["increment="])
    except getopt.GetoptError:
        print("bad options")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-i", "-increment"):
            bump_patch(arg)
            sys.exit()


if __name__ == "__main__":
    main(sys.argv[1:])
pelorus_chart = "charts/pelorus"
operator_chart = "charts/operators"

bump_patch(pelorus_chart)
