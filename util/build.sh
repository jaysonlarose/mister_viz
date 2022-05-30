#!/bin/bash

get_scriptdir() {
	local BACK
	BACK="$( pwd )"
	cd "$( dirname "${BASH_SOURCE[0]}" )"
	echo "$( pwd )"
	cd "$BACK"
}

SCRIPTDIR="$( get_scriptdir )"
if [[ -z "$MISTER_VIZ_ENV" ]]
then
	. "$SCRIPTDIR"/common.sh
fi

\ssh -q "$MISTER_VIZ_BUILDUSER"@"$MISTER_VIZ_BUILDHOST" "$MISTER_VIZ_BUILDFOLDER"\\mister_viz\\util\\build.bat
scp "$MISTER_VIZ_BUILDUSER"@"$MISTER_VIZ_BUILDHOST":"$( convert_slashpath "$MISTER_VIZ_BUILDFOLDER"'\\mister_viz\\dist.tar.gz' )" .
if [[ -e dist.tar.gz ]]
then
	tar xvfz dist.tar.gz
	rm dist.tar.gz
else
	exit 1
fi
