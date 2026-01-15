@echo off
echo Building WynnWeightLogic.dll with g++...

g++ -shared -o WynnWeightLogic.dll WynnWeightLogic.cpp -O3

if %errorlevel% neq 0 (
    echo Build Failed!
    pause
    exit /b %errorlevel%
)

echo Build Successful!
