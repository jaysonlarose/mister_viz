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
if [[ -e "build" ]]
then
	rm -Rf build
fi

if [[ -e "build.tar.gz" ]]
then
	rm build.tar.gz
fi

if [[ -e "mister_viz Installer.exe" ]]
then
	rm "mister_viz Installer.exe"
fi

if [[ -e "dist" ]]
then
	rm -Rf dist
fi

if [[ -e "dist.tar.gz" ]]
then
	rm dist.tar.gz
fi

\ssh -q -- "$MISTER_VIZ_BUILDUSER"@"$MISTER_VIZ_BUILDHOST" 'powershell -' << __FIN__
\$Folder = '$MISTER_VIZ_BUILDFOLDER\\mister_viz'
echo "Folder is \$Folder"
if (Test-Path -Path "\$Folder") {
	Remove-Item -Recurse -Force "\$Folder"
}
if (Test-Path -Path "\$Folder") {
	echo "\$Folder still seems to exist!"
	exit 1
}

__FIN__
if [[ $? -ne 0 ]]
then
	exit 1
fi

scp -r "$MISTER_VIZ_BASEDIR" "$MISTER_VIZ_BUILDUSER"@"$MISTER_VIZ_BUILDHOST":"$MISTER_VIZ_BUILDFOLDER"
