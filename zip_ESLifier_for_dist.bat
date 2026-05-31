@echo off

set SEVEN_ZIP="C:\Program Files\7-Zip\7z.exe"

echo Zipping Translation for Distribution
%SEVEN_ZIP% a "eslifier_translation.zip" "eslifier_translation.ts"

cd "dist"

echo Zipping ESLifier for Distribution
%SEVEN_ZIP% a "ESLifier.zip" "bsarch" "ESLifier.exe"

echo Done