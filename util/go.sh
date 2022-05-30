#!/bin/bash

runscript () {
	"$@"
	if [[ $? -ne 0 ]]
	then
		exit
	fi
}

runscript util/push.sh
runscript util/build.sh
runscript util/package.sh
runscript util/publish.sh
