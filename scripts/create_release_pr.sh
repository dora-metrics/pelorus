#!/usr/bin/env bash
#
# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

# Script to update versions of the Pelorus operator helm charts and the
# pelorus charts, which follows the SemVer convention.

# Helm charts enforces chart version bump every time those are changed.
# This may lead to the situation that multiple chart version
# bumps are required per one Pelorus release bump.

# The next release is calculated based on the one found in the github
# repository and across local Chart.yaml files for the Release Candidates.

# The following version bump logic is used:
#
#   | Current version |  script flag  | resulting version |
#   |     v2.0.8      |      -x       |       v3.0.0      |
#   |   v2.0.8-rc.4   |      -x       |       v3.0.0      |
#   |     v2.0.8      |      -y       |       v2.1.0      |
#   |   v2.0.8-rc.4   |      -y       |       v2.1.0      |
#   |     v2.0.8      |      -z       |       v2.0.9      |
#   |   v2.0.8-rc.4   |      -z       |       v2.0.8      |
#   |     v2.0.8      |      -n       |     v2.0.9-rc.1   |
#   |   v2.0.8-rc.4   |      -n       |     v2.0.8-rc.5   |

# Required to get the latest released tag
PELORUS_API_URL="https://api.github.com/repos/dora-metrics/pelorus"
PELORUS_LATEST_API_URL="${PELORUS_API_URL}/releases/latest"
PELORUS_MASTER_API_URL="${PELORUS_API_URL}/commits/master"
DEPLOYMENTCONFIG_PATH="charts/pelorus/charts/exporters/templates/_deploymentconfig.yaml"
IMAGESTREAM_PATH="charts/pelorus/charts/exporters/templates/_imagestream_from_image.yaml"
PELORUS_CHART="charts/pelorus/Chart.yaml"
PELORUS_EXPORTERS_CHART="charts/pelorus/charts/exporters/Chart.yaml"
OPERATORS_CHART="charts/operators/Chart.yaml"

INSTALL_DOC="docs/Development.md"

TRUE=1

function print_help() {
    printf "\nUsage: %s [OPTION]...\n\n" "$0"
    printf "\tStartup:\n"
    printf "\t  -h\tprint this help\n"
    printf "\n\tOptions:\n"
    printf "\t  -x\tbump X part of the version (Y and Z are set to 0, so X.0.0)\n"
    printf "\t  -y\tbump Y version (Z will start at 0, so X.Y.0)\n"
    printf "\t  -z\tbump Z version (Z in the X.Y.Z)\n"
    printf "\t  -n\tbump RC number (N in X.Y.Z-rc.N)\n"

    exit 0
}

OPTIONS_COUNTER=0

### Options
OPTIND=1
while getopts "h?xyzn" option; do
    case "$option" in
    h|\?) print_help;;
    x) x_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    y) y_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    z) z_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    n) rc_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    esac
done

if [ $OPTIONS_COUNTER -eq 0 ]; then
    printf "\nERROR: No options were provided.\n"
    exit 1
elif [ $OPTIONS_COUNTER -gt 1 ]; then
    printf "\nERROR: Provide only one option.\n"
    exit 1
fi

# Ensure working branch is based on upstream master branch
UPSTREAM_MASTER_SHA=$(curl -s "${PELORUS_MASTER_API_URL}" | jq -r '.sha')

if [ "$UPSTREAM_MASTER_SHA" == "null" ]; then
    echo "ERROR: Problem with querying GITHUB API (rate limit?), reason:"
    curl -s "${PELORUS_MASTER_API_URL}"
    exit 1
fi

if ! git cat-file -e "$UPSTREAM_MASTER_SHA"; then
    printf "\nERROR: Please ensure your branch is rebased on top of Upstream master.\n"
    echo "Latest master SHA command check: $ git cat-file -e $UPSTREAM_MASTER_SHA"
    exit 1
fi


LAST_RELEASED_TAG=$(curl -s "${PELORUS_LATEST_API_URL}" | jq -r '.tag_name' | sed 's/v//g')
echo "Current released version (upstream): ${LAST_RELEASED_TAG}"
if [ "$LAST_RELEASED_TAG" == "null" ]; then
    echo "ERROR: Problem with querying GITHUB API (rate limit?), reason:"
    curl -s "${PELORUS_LATEST_API_URL}"
    exit 1
fi
# shellcheck disable=SC2207
V_RELEASED=( $(echo "$LAST_RELEASED_TAG" | tr ' . '  '  ') )
# echo "Debug: V_RELEASED (upstream):" "${V_RELEASED[@]}"

V_X_VER=${V_RELEASED[0]}
V_Y_VER=${V_RELEASED[1]}
V_Z_VER=${V_RELEASED[2]}

RC_SUFFIX=""

CHART_FILE_IN_MASTER="$(curl https://raw.githubusercontent.com/dora-metrics/pelorus/master/charts/pelorus/Chart.yaml 2> /dev/null)"
CURRENT_VERSION=$(echo "$CHART_FILE_IN_MASTER" | grep '^version: ' | cut -c 10-)
# shellcheck disable=SC2207
CURRENT_VERSION_ARRAY=( $(echo "$CURRENT_VERSION" | tr ' . '  '  ') )
V_RC_VER=${CURRENT_VERSION_ARRAY[3]}
# echo "Debug: V_RC_VER (local): ${V_RC_VER}"
echo "Current version (upstream): $CURRENT_VERSION"

if [[ $x_ver ]]; then
  V_X_VER=$(( V_X_VER +  1 ))
  V_Y_VER="0"
  V_Z_VER="0"
elif [[ $y_ver ]]; then
  V_Y_VER=$(( V_Y_VER +  1 ))
  V_Z_VER="0"
elif [[ $z_ver ]]; then
  # Only bump the Z version if -rc.N was missing
  # Otherwise remove the -rc.N as it's our next release
  if [[ -z "${V_RC_VER}" ]]; then
    V_Z_VER=$(( V_Z_VER +  1 ))
  fi
elif [[ $rc_ver ]]; then
  V_Z_VER=$(( V_Z_VER +  1 ))
  if [[ -z "${V_RC_VER}" ]]; then
    # Start from the first RC number of the next Z release
    V_RC_VER=1
  else
    V_RC_VER=$(( V_RC_VER +  1 ))
  fi
  RC_SUFFIX="-rc.${V_RC_VER}"
fi
SEMVER="$V_X_VER.$V_Y_VER.$V_Z_VER$RC_SUFFIX"

echo "Version to be released: v$SEMVER"

sed -i "s/^version:.*/version: $SEMVER/g" "$PELORUS_CHART"
sed -i "s/^    version:.*/    version: $SEMVER/g" "$PELORUS_CHART"
sed -i "s/^version:.*/version: $SEMVER/g" "$OPERATORS_CHART"
sed -i "s/^version:.*/version: $SEMVER/g" "$PELORUS_EXPORTERS_CHART"

# Replace version, but only within the line that has the quay.io pointer
# This is, because other versions are either internal OpenShift registry or provided by the user
sed -i "/quay.io/ s/\({{ \.image_tag \| default \)\"[^\"]*\"\( \)\?/\1\"v$SEMVER\"\2/g" "$IMAGESTREAM_PATH"

# Replace deploymentconfig, but only within the line that includes "value"
sed -i "/value/ s/\({{ \.image_tag \| default \)\"[^\"]*\"\( \)\?/\1\"v$SEMVER\"\2/g" "$DEPLOYMENTCONFIG_PATH"

if ! [[ $rc_ver ]]; then
  # Update branch in the Development documentation
  sed -i "s/\(release number, for example \`\).*\(\`\.\)/\1v$SEMVER\2/g" "$INSTALL_DOC"
  sed -i "s/\(image_tag: \).*\( # Specific release\)/\1v$SEMVER\2/g" "$INSTALL_DOC"
fi

#### Verification if the changes were actually applied
#### The verification check how many versions are found in the expected files
#### It's not 100% robust (e.g. some additional version collision may happen),
#### when updated version matches other strings in the files, but should catch most of the issues.

# We should have exactly 4 versions matching
NO_VERSIONS=$(find charts/ -name "Chart.yaml" -type f -exec grep -c "$SEMVER" {} + | awk -F ':' '{sum += $2} END {print sum}')
if [ "$NO_VERSIONS" -ne 4 ]; then
  echo "ERROR: Some mismatch in the Chart.yaml versions"
  find charts/ -name "Chart.yaml" -type f -exec grep "version:" {} +
  exit 1
fi

# _imagestream_from_image.yaml should have only one version updated
NO_VERSIONS=$(grep -c "v$SEMVER" "$IMAGESTREAM_PATH")
if [ "$NO_VERSIONS" -ne 1 ]; then
  echo "ERROR: Unexpected changes in the: $IMAGESTREAM_PATH"
  exit 1
fi

if ! [[ $rc_ver ]]; then
  # docs/Development.md should have exactly 2 places with the updated version
  NO_VERSIONS=$(grep -c "v$SEMVER" "$INSTALL_DOC")
  if [ "$NO_VERSIONS" -ne 2 ]; then
    echo "ERROR: Unexpected changes in the: $INSTALL_DOC"
    exit 1
  fi
fi

# _deploymentconfig.yaml should have exactly  only one version updated
NO_VERSIONS=$(grep -c "v$SEMVER" "$DEPLOYMENTCONFIG_PATH")
if [ "$NO_VERSIONS" -ne 1 ]; then
  echo "ERROR: Unexpected changes in the: $DEPLOYMENTCONFIG_PATH"
  exit 1
fi

helm dep update charts/pelorus &> /dev/null
rm -f charts/pelorus/charts/*.tgz

if [[ $x_ver ]]; then
  printf "\nIMPORTANT:\n\t Do label your PR with: \"major\"\n\n"
elif [[ $y_ver ]]; then
  printf "\nIMPORTANT:\n\t Do label your PR with: \"minor\"\n\n"
fi

if ! [[ $rc_ver ]]; then
  printf "\nIMPORTANT:\n\t This change will result in a new release\n\n"
fi

# TODO merge this script with scripts/create_pelorus_operator.sh
