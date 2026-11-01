@echo off
rem 供 Lizzie/KataGo GUI 的引擎命令. 首次运行会做 OpenCL 调优(几分钟), 结果缓存于 KataGoData\opencltuning
"%~dp0engine\katago-v1.18.0-opencl-windows-x64\katago.exe" gtp -model "%~dp0weights\network_file\kata1-tf3-b11c768-s12752M-d6531M.bin.gz" -config "%~dp0engine\katago-v1.18.0-opencl-windows-x64\gtp.cfg"
