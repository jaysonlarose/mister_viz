MISTER_VIZ_BASEDIR="$HOME"/Git/mister_viz

MISTER_VIZ_BUILDHOST=vm10
MISTER_VIZ_BUILDUSER=jayson
MISTER_VIZ_BUILDFOLDER='C:\\Users\\jayson\\Desktop'

MISTER_VIZ_TESTHOST=wedge
MISTER_VIZ_TESTUSER=jayson
MISTER_VIZ_TESTFOLDER='C:\\Users\\jayson\\Desktop'

MISTER_VIZ_ENV=true

convert_slashpath () {
	local RET
	RET="$( echo "$1" | tr '\\' / )"
	echo '/'"$RET"
}
