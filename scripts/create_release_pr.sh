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
#   |   v2.0.8-rc.4   | -v 4.1.2-rc.7 |     v4.1.2-rc.7   |

# Required to get the latest released tag
PELORUS_API_URL="https://api.github.com/repos/dora-metrics/pelorus"
PELORUS_LATEST_API_URL="${PELORUS_API_URL}/releases/latest"
PELORUS_MASTER_API_URL="${PELORUS_API_URL}/commits/master"
# BUILDCONFIG_PATH="charts/pelorus/charts/exporters/templates/_buildconfig.yaml"
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
    printf "\t  -v\tuse exact version\n"
    printf "\nExample: %s -v 2.0.5-rc.3\n\n" "$0"

    exit 0
}

OPTIONS_COUNTER=0

### Options
OPTIND=1
while getopts "h?xyznv:" option; do
    case "$option" in
    h|\?) print_help;;
    x) x_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    y) y_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    z) z_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    n) rc_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    v) exact_ver=$OPTARG; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
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

# No exact version passed, calculating version
if [ -z ${exact_ver+x} ]; then
  LAST_RELEASED_TAG=$(curl -s "${PELORUS_LATEST_API_URL}" | jq -r '.tag_name')
  echo "Debug: LAST_RELEASED_TAG (upstream): ${LAST_RELEASED_TAG}"
  if [ "$LAST_RELEASED_TAG" == "null" ]; then
      echo "ERROR: Problem with querying GITHUB API (rate limit?), reason:"
      curl -s "${PELORUS_LATEST_API_URL}"
      exit 1
  fi
  # shellcheck disable=SC2207
  V_RELEASED=( $(echo "$LAST_RELEASED_TAG" | sed 's/v//g' | sed 's/-rc//g'  | tr ' . '  '  ') )
  echo "Debug: V_RELEASED (upstream):" "${V_RELEASED[@]}"

  V_X_VER=${V_RELEASED[0]}
  V_Y_VER=${V_RELEASED[1]}
  V_Z_VER=${V_RELEASED[2]}

  # RC found in tag
  V_RC=${V_RELEASED[3]}
  RC_SUFFIX=""

  # From all versions within all Chart.yaml files: X.Y.Z-rc.N find the highest N
  HIGHEST_RC_VER=$(find charts/ -name "Chart.yaml" -type f -exec grep -hoP 'version:\s*v?\d+\.\d+\.\d+-rc.\K\d+' {} \; | sort -rn | head -n 1)
  echo "Debug: HIGHEST_RC_VER (local): ${HIGHEST_RC_VER}"

  echo "Current version (upstream): $LAST_RELEASED_TAG"

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
    if [[ -z "${V_RC}" ]]; then
      V_Z_VER=$(( V_Z_VER +  1 ))
    fi
  elif [[ $rc_ver ]]; then
    if [[ -z "${V_RC}" ]]; then
      # Start from the first RC number of the next Z release
      V_Z_VER=$(( V_Z_VER +  1 ))
      V_RC=1
    else
      V_RC=$(( V_RC +  1 ))
    fi
    RC_SUFFIX="-rc.${V_RC}"
  fi
  SEMVER="$V_X_VER.$V_Y_VER.$V_Z_VER$RC_SUFFIX"
else
  SEMVER="$exact_ver"
fi

echo "Version to be released: v$SEMVER"

# Sed to inject version between the quotes in the line containing:
# .source_ref | default=""
#TBD: Do we need to update _buildconfig.yaml or it should always point to master?
#NEW_VER="v$SEMVER"
# sed -i "/.source_ref | default/s/\"[^\"][^\"]*\"/\"$NEW_VER\"/" "$BUILDCONFIG_PATH"

sed -i "s/^version:.*/version: $SEMVER/g" "$PELORUS_CHART"
sed -i "s/^    version:.*/    version: $SEMVER/g" "$PELORUS_CHART"
sed -i "s/^version:.*/version: $SEMVER/g" "$OPERATORS_CHART"
sed -i "s/^version:.*/version: $SEMVER/g" "$PELORUS_EXPORTERS_CHART"

# Replace version, but only within the line that has the quay.io pointer
# This is, because other versions are either internal OpenShift registry or provided by the user
sed -i "/quay.io/ s/\({{ \.image_tag \| default \)\"[^\"]*\"\( \)\?/\1\"v$SEMVER\"\2/g" "$IMAGESTREAM_PATH"

# Replace deploymentconfig, but only within the line that includes "value"
sed -i "/value/ s/\({{ \.image_tag \| default \)\"[^\"]*\"\( \)\?/\1\"v$SEMVER\"\2/g" "$DEPLOYMENTCONFIG_PATH"

# Update branch in the Development documentation
sed -i "s/\(release number, for example \`\).*\(\`\.\)/\1v$SEMVER\2/g" "$INSTALL_DOC"
sed -i "s/\(image_tag: \).*\( # Specific release\)/\1v$SEMVER\2/g" "$INSTALL_DOC"


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

# docs/Development.md should have exactly 2 places with the updated version
NO_VERSIONS=$(grep -c "v$SEMVER" "$INSTALL_DOC")
if [ "$NO_VERSIONS" -ne 2 ]; then
  echo "ERROR: Unexpected changes in the: $INSTALL_DOC"
  exit 1
fi

# docs/Development.md should have exactly 2 places with the updated version
NO_VERSIONS=$(grep -c "v$SEMVER" "$DEPLOYMENTCONFIG_PATH")
if [ "$NO_VERSIONS" -ne 1 ]; then
  echo "ERROR: Unexpected changes in the: $DEPLOYMENTCONFIG_PATH"
  exit 1
fi

printf "\nIMPORTANT:\n\t Update the operator files using ./scripts/create_pelorus_operator.sh script.\n\n"

if [[ $x_ver ]]; then
  printf "\nIMPORTANT:\n\t Do include \"major release\" text in the first line of your commit message, or label your PR with: \"major\"\n\n"
elif [[ $y_ver ]]; then
  printf "\nIMPORTANT:\n\t Do include \"minor release\" text in the first line of your commit message, or label your PR with: \"minor\"\n\n"
else
  printf "\nIMPORTANT:\n\t If it's minor or major version change do include \"minor release\" or \"major release\" text in the first line of your commit message, or label your PR with: \"minor\" or \"major\" \n\n"
fi
