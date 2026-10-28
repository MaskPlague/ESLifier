@echo off

set SEVEN_ZIP="C:\Program Files\7-Zip\7z.exe"

echo Zipping Translation for Distribution
%SEVEN_ZIP% a "eslifier_translation.zip" "eslifier_translation.ts"

cd "dist"

echo Zipping ESLifier EXEs for Distribution
%SEVEN_ZIP% a "ESLifier-SSE.zip" "bsarch" "ESLifier-SSE.exe"
%SEVEN_ZIP% a "ESLifier-FO4.zip" "bsarch" "ESLifier-FO4.exe"

cd ..

echo Zipping ESLifier Vortex State Getter Extension for Distribution
%SEVEN_ZIP% a "ESLifier Vortex State Getter Extension.zip" "ESLifier Vortex State Getter"

::echo Zipping ESLifier One Dir for Distribution
::%SEVEN_ZIP% a "ESLifier_OneDir.zip" "bsarch"
::cd "ESLifier"
::%SEVEN_ZIP% a "..\ESLifier_OneDir.zip" "ESLifier.exe" "_internal"


echo Done