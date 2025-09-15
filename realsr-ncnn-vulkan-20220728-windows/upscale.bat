pushd %~dp0
move %1 "%~dp0%~nx1"
realsr-ncnn-vulkan.exe -i "%~dp0%~nx1" -o %1
