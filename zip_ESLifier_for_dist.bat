@echo off
set SEVEN_ZIP="C:\Program Files\7-Zip\7z.exe"

cd "dist"

echo Zipping ESLifier for Distribution
%SEVEN_ZIP% a "ESLifier.zip" "bsarch" "ESLifier.exe"

echo Done