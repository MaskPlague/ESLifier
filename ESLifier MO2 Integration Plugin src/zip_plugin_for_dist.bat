@echo off

set SEVEN_ZIP="C:\Program Files\7-Zip\7z.exe"

cd "ESLifier MO2 Integration Plugin src"

echo Zipping Plugin translation for Distribution
%SEVEN_ZIP% a "eslifier_mo2_integration_translation.zip" "eslifier_mo2_integration_translation.ts"

echo Zipping MO2 Plugin for Distribution
%SEVEN_ZIP% a "ESLifier MO2 Integration Plugin.zip" "ESLifier MO2 Integration"

echo Done