@echo off

rem Define Variables
set SEVEN_ZIP="C:\Program Files\7-Zip\7z.exe"

cd "ESLifier MO2 Integration Plugin src"

echo Zipping MO2 Plugin for Distribution
%SEVEN_ZIP% a "ESLifier MO2 Integration Plugin.zip" "ESLifier MO2 Integration"

echo Done