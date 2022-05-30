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

cd "$MISTER_VIZ_BASEDIR"
if [[ -e "mister_viz Installer.exe" ]]
then
	rm "mister_viz Installer.exe"
fi
makensis setup.nsi
