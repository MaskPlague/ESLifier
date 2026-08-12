@echo off

set SEVEN_ZIP="C:\Program Files\7-Zip\7z.exe"

echo Zipping Translation for Distribution
%SEVEN_ZIP% a "eslifier_translation.zip" "eslifier_translation.ts"

cd "dist"

echo Zipping ESLifier EXE for Distribution
%SEVEN_ZIP% a "ESLifier.zip" "bsarch" "ESLifier.exe"

::echo Zipping ESLifier One Dir for Distribution
::%SEVEN_ZIP% a "ESLifier_OneDir.zip" "bsarch"
::cd "ESLifier"
::%SEVEN_ZIP% a "..\ESLifier_OneDir.zip" "ESLifier.exe" "_internal"


echo Done